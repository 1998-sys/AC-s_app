# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.html_to_pdf
# Created       : 25-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Renders an HTML string to PDF headlessly via WebView2 (Chromium's print engine), reusing the same pythonnet/WinForms stack pywebview already bundles — no window is ever shown to the user.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
import shutil
import tempfile
import threading
import uuid

import clr

clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Threading")

from webview.util import interop_dll_path

clr.AddReference(interop_dll_path("Microsoft.Web.WebView2.Core.dll"))
clr.AddReference(interop_dll_path("Microsoft.Web.WebView2.WinForms.dll"))

import System.Windows.Forms as WinForms
from System import Action
from System.Threading import ApartmentState, Thread, ThreadStart
from System.Threading.Tasks import Task
from Microsoft.Web.WebView2.WinForms import CoreWebView2CreationProperties, WebView2

# A fresh, unique user-data folder per session (instead of one shared folder,
# or pywebview's own — which is only valid while the main window is alive)
# keeps this exporter independent of the GUI's lifecycle (it can run even
# when no pywebview window is open, e.g. a CLI/batch run) and, importantly,
# avoids a real lock conflict found in testing: WebView2 keeps its browser
# process warm in the background after a session ends (by design, for fast
# reuse), so a second *session* reusing the SAME folder while that process is
# still alive fails to initialize with HRESULT 0x8007139F ("the group or
# resource is not in the correct state"). A unique folder per session
# sidesteps this — see `SessaoHtmlParaPdf.encerrar` for the (best-effort)
# cleanup. Within one session, every `exportar()` call reuses the same
# already-warm WebView2 environment (see the module docstring below for why
# that matters).
_PASTA_BASE_TEMP = os.path.join(tempfile.gettempdir(), "certiflow_html_to_pdf")

TIMEOUT_PADRAO_S = 30


class HtmlParaPdfError(RuntimeError):
    """Raised when the HTML could not be rendered to PDF (WebView2 initialization
    failure, navigation failure, or the safety timeout being hit)."""


class SessaoHtmlParaPdf:
    """Reusable WebView2 session: pay the (real, measured) ~cold-start cost of
    spinning up a fresh browser process tree only once, then export as many
    PDFs as needed against that same warm environment.

    Motivation: a certificate's full report flow (Linearização → Falha
    Presumida → AC de Medidor Primário) used to call the module-level
    `html_para_pdf` three times, each spinning up its *own* full WebView2
    process tree (main browser + crashpad-handler + gpu-process +
    network-service + storage-service + renderer — 6 processes) from a
    brand-new, empty profile folder. Measured end to end: ~30s per report,
    ~90s total for the 3 reports of a single certificate — almost
    certainly dominated by that repeated cold environment creation (a
    bare WebView2 init+navigate+print with no report content behaved the
    same way in isolation). Reusing one session across the 3 reports pays
    that cost once instead of three times.

    Usage:
        sessao = SessaoHtmlParaPdf()
        sessao.iniciar()
        try:
            sessao.exportar(html_linearizacao, caminho1)
            sessao.exportar(html_falha_presumida, caminho2)
            sessao.exportar(html_ac_primario, caminho3)
        finally:
            sessao.encerrar()

    Not thread-safe for concurrent `exportar()` calls — call it
    sequentially from one thread per session (matches how the report flow
    already runs, one report at a time, in `gui/pdf_service.py`).
    """

    def __init__(self, timeout_s: float = TIMEOUT_PADRAO_S):
        self._timeout_s = timeout_s
        self._thread = None
        self._webview = None
        self._form = None
        self._pasta_usuario = None
        self._pronta = threading.Event()
        self._erro_inicializacao = None

    def iniciar(self) -> None:
        """Starts the WebView2 environment on a dedicated STA thread and blocks until it's ready.

        Raises:
            HtmlParaPdfError: if WebView2 fails to initialize, or takes
                longer than `timeout_s`.
        """
        self._pasta_usuario = os.path.join(_PASTA_BASE_TEMP, uuid.uuid4().hex)
        os.makedirs(self._pasta_usuario, exist_ok=True)

        self._thread = Thread(ThreadStart(self._loop))
        self._thread.SetApartmentState(ApartmentState.STA)
        self._thread.Start()

        if not self._pronta.wait(timeout=self._timeout_s):
            raise HtmlParaPdfError(f"Timeout ({self._timeout_s}s) inicializando o WebView2.")
        if self._erro_inicializacao:
            raise HtmlParaPdfError(self._erro_inicializacao)

    def _loop(self):
        # See form.html_to_pdf.html_para_pdf's docstring/comment for why every
        # "stop the message loop" call here is ExitThread(), never Exit() —
        # Exit() tears down the message loop on EVERY thread in the process,
        # which would silently kill the main CertiFlow window too.
        form = WinForms.Form()
        form.ShowInTaskbar = False
        form.WindowState = WinForms.FormWindowState.Minimized
        # form.Show() is intentionally never called — stays fully offscreen.
        self._form = form

        webview = WebView2()
        props = CoreWebView2CreationProperties()
        props.UserDataFolder = self._pasta_usuario
        webview.CreationProperties = props
        form.Controls.Add(webview)
        self._webview = webview

        def on_webview_ready(sender, args):
            if not args.IsSuccess:
                self._erro_inicializacao = f"Falha ao inicializar o WebView2: {args.InitializationException}"
            self._pronta.set()

        webview.CoreWebView2InitializationCompleted += on_webview_ready
        webview.EnsureCoreWebView2Async(None)

        # Runs until encerrar() posts Application.ExitThread() onto this same
        # thread via Invoke — stays alive across every exportar() call in
        # between, which is the whole point of this class.
        WinForms.Application.Run()

        webview.Dispose()
        form.Dispose()

    def exportar(self, html: str, caminho_pdf: str) -> None:
        """Renders `html` and saves it as `caminho_pdf`, reusing this session's already-warm WebView2 environment.

        Args:
            html: Full HTML document to render (self-contained — inline
                `<style>`, no external resources that would need network access).
            caminho_pdf: Destination path of the PDF file. Overwritten if
                it already exists (removed first, so a locked/open file
                surfaces as `PermissionError` instead of a silent stale PDF).

        Raises:
            HtmlParaPdfError: if navigation fails, `PrintToPdfAsync` itself
                fails, or the export takes longer than this session's `timeout_s`.
            PermissionError: if `caminho_pdf` already exists and is locked
                (e.g. open in a PDF viewer) and cannot be removed.
        """
        if os.path.exists(caminho_pdf):
            os.remove(caminho_pdf)

        concluido = threading.Event()
        resultado = {"ok": False, "erro": None}
        webview = self._webview

        def on_pdf_done(task):
            try:
                resultado["ok"] = bool(task.Result)
                if not resultado["ok"]:
                    resultado["erro"] = "PrintToPdfAsync retornou False."
            except Exception as e:  # noqa: BLE001 — surfaced via HtmlParaPdfError below
                resultado["erro"] = str(e)
            finally:
                concluido.set()

        def on_navigation_completed(sender, args):
            webview.CoreWebView2.NavigationCompleted -= on_navigation_completed
            if not args.IsSuccess:
                resultado["erro"] = f"Falha ao carregar o HTML: {args.WebErrorStatus}"
                concluido.set()
                return
            try:
                webview.CoreWebView2.PrintToPdfAsync(caminho_pdf, None).ContinueWith(
                    Action[Task[bool]](on_pdf_done)
                )
            except Exception as e:  # noqa: BLE001
                resultado["erro"] = str(e)
                concluido.set()

        def _navegar():
            # Runs on the session's STA thread (marshalled via Invoke, the
            # standard WinForms cross-thread call pattern) — exportar() itself
            # is called from the caller's own thread, not the STA thread.
            webview.CoreWebView2.NavigationCompleted += on_navigation_completed
            webview.CoreWebView2.NavigateToString(html)

        webview.Invoke(Action(_navegar))

        if not concluido.wait(timeout=self._timeout_s):
            raise HtmlParaPdfError(f"Timeout ({self._timeout_s}s) exportando o PDF.")
        if not resultado["ok"]:
            raise HtmlParaPdfError(resultado["erro"] or "Falha desconhecida exportando o PDF.")

    def encerrar(self) -> None:
        """Shuts down the WebView2 environment and removes its temporary profile folder.

        Safe to call even if `iniciar()` failed partway through.
        """
        if self._webview is not None:
            try:
                self._webview.Invoke(Action(WinForms.Application.ExitThread))
            except Exception:  # noqa: BLE001 — best-effort shutdown
                pass
        if self._thread is not None:
            self._thread.Join()
        if self._pasta_usuario:
            shutil.rmtree(self._pasta_usuario, ignore_errors=True)


def html_para_pdf(html: str, caminho_pdf: str, timeout_s: float = TIMEOUT_PADRAO_S) -> None:
    """Renders a single HTML string to PDF, using WebView2's native print-to-PDF.

    Convenience wrapper around `SessaoHtmlParaPdf` for one-off exports —
    opens a session, exports once, closes it. Generating more than one
    report in the same flow (e.g. Linearização + Falha Presumida + AC de
    Medidor Primário for the same certificate) should use
    `SessaoHtmlParaPdf` directly instead and share one session across all
    of them: each session pays a real, measured ~cold-start cost to spin
    up its WebView2 environment, so opening a new one per report multiplies
    that cost for no benefit.

    Args:
        html: Full HTML document to render (self-contained — inline `<style>`,
            no external resources that would need network access).
        caminho_pdf: Destination path of the PDF file. Overwritten if it
            already exists (removed first, so a locked/open file surfaces as
            `PermissionError` instead of a silent stale PDF).
        timeout_s: Maximum time to wait for initialization + navigation +
            PDF export to complete before giving up.

    Raises:
        HtmlParaPdfError: If WebView2 fails to initialize, navigation fails,
            `PrintToPdfAsync` itself fails, or `timeout_s` is exceeded.
        PermissionError: If `caminho_pdf` already exists and is locked
            (e.g. open in a PDF viewer) and cannot be removed.
    """
    sessao = SessaoHtmlParaPdf(timeout_s=timeout_s)
    sessao.iniciar()
    try:
        sessao.exportar(html, caminho_pdf)
    finally:
        sessao.encerrar()
