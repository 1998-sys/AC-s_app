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
        self.api = api

    @property
    def window(self):
        return self.api._window

    def js(self, expr):
        """Dispara JS sem esperar resultado (usado para updates de UI que não retornam nada)."""
        return self.window.evaluate_js(expr)

    def js_await(self, expr, timeout=600):
        """Avalia um script JS que retorna uma Promise e espera ela resolver.

        pywebview só resolve Promises quando um `callback` é passado para evaluate_js —
        sem ele, o valor retornado é a Promise ainda pendente. Usamos um Event para
        transformar isso numa chamada bloqueante (necessário pros modais Dialogs.*
        que substituem os messagebox.askyesno/showerror síncronos de antes).

        O timeout (10 min por padrão) não é para apressar o usuário respondendo o modal —
        é uma rede de segurança contra a Promise nunca resolver (bug de JS, janela
        destruída no meio da chamada), que travaria a thread de fundo para sempre."""
        done = Event()
        resultado = {}

        def _callback(valor):
            resultado["valor"] = valor
            done.set()

        self.window.evaluate_js(expr, callback=_callback)
        if not done.wait(timeout=timeout):
            print(f"[_js_await] timeout aguardando resposta do JS: {expr[:120]!r}")
            return None
        return resultado.get("valor")

    def confirm(self, title, message):
        return bool(self.js_await(f"Dialogs.confirm({json.dumps(title)}, {json.dumps(message)})"))

    def alert(self, title, message, variant="info"):
        # Em modo lote, um alerta de sucesso/erro pararia a fila esperando o
        # usuário clicar OK a cada arquivo — registra o evento e segue.
        pdf_service = self.api._pdf_service
        if pdf_service.em_lote_ativo():
            pdf_service.registrar_evento_lote(title, message, variant)
            return
        self.js_await(f"Dialogs.alert({json.dumps(title)}, {json.dumps(message)}, {json.dumps(variant)})")

    def prompt(self, title, message, fields):
        return self.js_await(f"Dialogs.prompt({json.dumps(title)}, {json.dumps(message)}, {json.dumps(fields)})")

    def escolher_arquivo(self, titulo, extensoes):
        resultado = self.window.create_file_dialog(
            FILE_DIALOG_OPEN, allow_multiple=False, file_types=extensoes
        )
        return resultado[0] if resultado else None

    def escolher_arquivos(self, titulo, extensoes):
        resultado = self.window.create_file_dialog(
            FILE_DIALOG_OPEN, allow_multiple=True, file_types=extensoes
        )
        return list(resultado) if resultado else []

    def after(self, delay, fn, *args):
        """Compat shim para o .after() do tkinter usado pelos processors — pywebview
        não precisa de marshalling de thread para evaluate_js, então só executa direto."""
        fn(*args)

    def progress(self, percent, active, done):
        self.js(f"App.onProgress({percent}, {json.dumps(active)}, {json.dumps(done)})")

    def voltar_para_selecao(self):
        # Em modo lote, este é o ponto de saída de todo item que não passa
        # pela tela de revisão (erro, cancelamento, geração direta de XML) —
        # avancar_fila decide se avança pro próximo item ou fecha o lote.
        if self.api._pdf_service.avancar_fila():
            return
        self.js("App.showView('select')")
        self.js("App.setTracker(1)")
