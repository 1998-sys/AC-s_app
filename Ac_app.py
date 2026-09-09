# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : Ac_app
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Application entry point: prepares safe console/output encoding, initializes the database and launches the pywebview desktop window.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
import sys
from pathlib import Path
import webview
from gui.api import Api
from data.conexao import criar_tabela, migrar

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# The packaged build runs with console=False (sys.stdout/stderr = None); and even in
# console mode, Windows' default codepage is not UTF-8 and can crash a print() with
# characters outside cp1252 (e.g., "∞" in certificate tables). Make both cases safe.
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(os.devnull, "w")
else:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _resource(relative_path: str) -> str:
    """Resolve the absolute path of a resource, accounting for the packaged app (PyInstaller) or running from source.

    Args:
        relative_path: Path relative to the base resource directory (e.g., "webui/index.html").

    Returns:
        str: Resolved absolute path to the resource.
    """
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
    return str(base / relative_path)


LARGURA_PADRAO = 560
ALTURA_PADRAO = 940
MARGEM_TASKBAR = 80  # reserve space so the taskbar/title bar doesn't cover the window


def _tamanho_janela():
    """Computes the window size to use, capping the design size (560x940) to the primary
    screen's resolution so the window fits on smaller notebook displays.

    Returns:
        tuple: (width, height) to pass to webview.create_window.
    """
    try:
        tela = webview.screens[0]
        largura = min(LARGURA_PADRAO, tela.width - 40)
        altura = min(ALTURA_PADRAO, tela.height - MARGEM_TASKBAR)
        return max(largura, 400), max(altura, 500)
    except Exception:
        return LARGURA_PADRAO, ALTURA_PADRAO


def main():
    """Initialize the database, create the CertiFlow main window and start the pywebview loop."""
    criar_tabela()
    migrar()

    largura, altura = _tamanho_janela()

    api = Api()
    window = webview.create_window(
        "CERTIFLOW",
        _resource(os.path.join("webui", "index.html")),
        js_api=api,
        width=largura,
        height=altura,
        min_size=(400, 500),
        resizable=True,
    )
    api.set_window(window)
    webview.start(icon=_resource(os.path.join("logo", "logo icon.ico")))


if __name__ == "__main__":
    main()
