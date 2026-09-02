# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gui.dialogs
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Bridges Python and the CertiFlow web UI's JS dialogs/navigation via window.evaluate_js.
#                 Faz a ponte entre o Python e os diálogos/navegação em JS da UI web do CertiFlow via window.evaluate_js.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import json
from threading import Event

import webview

# webview.FileDialog.OPEN só existe a partir do pywebview 6.x; na 5.x é webview.OPEN_DIALOG.
FILE_DIALOG_OPEN = getattr(getattr(webview, "FileDialog", None), "OPEN", None)
if FILE_DIALOG_OPEN is None:
    FILE_DIALOG_OPEN = webview.OPEN_DIALOG


class DialogBridge:
    """Ponte JS <-> Python para os diálogos customizados (estilo CertiFlow) e
    para navegação/progresso da UI. Único ponto do código que fala com
    `window.evaluate_js` — todo o resto do backend passa por aqui.
    """

    def __init__(self, api):
        """Stores the Api reference to access the window and services."""
        self.api = api

    @property
    def window(self):
        """Returns the current pywebview window (`Api._window`)."""
        return self.api._window

    def js(self, expr):
        """Fires JS without waiting for a result (used for UI updates that return nothing).

        Args:
            expr: JS expression/snippet to evaluate in the window.
        """
        return self.window.evaluate_js(expr)

    def js_await(self, expr, timeout=600):
        """Evaluates a JS script that returns a Promise and waits for it to resolve, blocking the calling thread.

        Args:
            expr: JS expression to evaluate; must return a Promise.
            timeout: maximum wait time in seconds (10 min by default).

        Returns:
            The value the Promise resolved with, or None if the timeout is reached.

        Notes:
            pywebview only resolves Promises when a `callback` is passed to
            evaluate_js — without it, the returned value is the still-pending
            Promise. We use an Event to turn this into a blocking call
            (needed for the Dialogs.* modals that replace the old synchronous
            messagebox.askyesno/showerror). The timeout is not there to rush
            the user into answering the modal — it's a safety net against the
            Promise never resolving (a JS bug, or the window being destroyed
            mid-call), which would otherwise hang the background thread
            forever.
        """
        done = Event()
        resultado = {}

        def _callback(valor):
            """Receives the Promise's resolved value and releases the Event that `js_await` is waiting on."""
            resultado["valor"] = valor
            done.set()

        self.window.evaluate_js(expr, callback=_callback)
        if not done.wait(timeout=timeout):
            print(f"[_js_await] timeout aguardando resposta do JS: {expr[:120]!r}")
            return None
        return resultado.get("valor")

    def confirm(self, title, message):
        """Shows the Dialogs.confirm modal and returns the user's choice.

        Returns:
            True if the user confirmed, False otherwise.
        """
        return bool(self.js_await(f"Dialogs.confirm({json.dumps(title)}, {json.dumps(message)})"))

    def alert(self, title, message, variant="info"):
        """Shows the Dialogs.alert modal, or logs the event without displaying anything if a batch is active.

        Args:
            variant: visual style of the alert (e.g. "info", "success", "error").

        Notes:
            In batch mode, a success/error alert would stall the queue waiting
            for the user to click OK on every file — instead, it logs the
            event (`PdfProcessingService.registrar_evento_lote`) and moves on.
        """
        pdf_service = self.api._pdf_service
        if pdf_service.em_lote_ativo():
            pdf_service.registrar_evento_lote(title, message, variant)
            return
        self.js_await(f"Dialogs.alert({json.dumps(title)}, {json.dumps(message)}, {json.dumps(variant)})")

    def prompt(self, title, message, fields):
        """Shows the Dialogs.prompt modal and returns the filled-in values.

        Args:
            fields: list of form field descriptors (name, label, etc.).

        Returns:
            Dict with the filled-in values, or None if the user cancelled.
        """
        return self.js_await(f"Dialogs.prompt({json.dumps(title)}, {json.dumps(message)}, {json.dumps(fields)})")

    def escolher_arquivo(self, titulo, extensoes):
        """Opens the native single-file selection dialog.

        Returns:
            The chosen path, or None if the user cancelled.
        """
        resultado = self.window.create_file_dialog(
            FILE_DIALOG_OPEN, allow_multiple=False, file_types=extensoes
        )
        return resultado[0] if resultado else None

    def escolher_arquivos(self, titulo, extensoes):
        """Opens the native multi-file selection dialog.

        Returns:
            List of chosen paths (empty if the user cancelled).
        """
        resultado = self.window.create_file_dialog(
            FILE_DIALOG_OPEN, allow_multiple=True, file_types=extensoes
        )
        return list(resultado) if resultado else []

    def after(self, delay, fn, *args):
        """Compat shim for tkinter's .after() used by the processors.

        Args:
            delay: ignored — kept only for signature compatibility.
            fn: function to execute.
            *args: positional arguments passed through to `fn`.

        Notes:
            pywebview doesn't need thread marshalling for evaluate_js, so this
            just runs `fn` directly, without scheduling anything.
        """
        fn(*args)

    def progress(self, percent, active, done):
        """Updates the UI's progress bar/checklist."""
        self.js(f"App.onProgress({percent}, {json.dumps(active)}, {json.dumps(done)})")

    def voltar_para_selecao(self):
        """Navigates back to the selection screen, or advances the batch queue if one is active.

        Notes:
            In batch mode, this is the exit point for every item that doesn't
            go through the review screen (error, cancellation, direct XML
            generation) — `avancar_fila` decides whether to advance to the
            next item or close the batch.
        """
        if self.api._pdf_service.avancar_fila():
            return
        self.js("App.showView('select')")
        self.js("App.setTracker(1)")
