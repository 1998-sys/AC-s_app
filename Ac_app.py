# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : Ac_app
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Application entry point: prepares safe console/output encoding, initializes the database and launches the pywebview desktop window.
#                 Ponto de entrada da aplicação: prepara a codificação segura do console/saída, inicializa o banco de dados e inicia a janela desktop do pywebview.
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

# Build empacotado roda com console=False (sys.stdout/stderr = None); e mesmo em modo
# console, o codepage padrão do Windows não é UTF-8 e pode derrubar um print() com
# caracteres fora do cp1252 (ex.: "∞" em tabelas de certificado). Torna ambos os casos seguros.
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


def main():
    """Initialize the database, create the CertiFlow main window and start the pywebview loop."""
    criar_tabela()
    migrar()

    api = Api()
    window = webview.create_window(
        "CERTIFLOW",
        _resource(os.path.join("webui", "index.html")),
        js_api=api,
        width=560,
        height=940,
        resizable=False,
    )
    api.set_window(window)
    webview.start(icon=_resource(os.path.join("logo", "logo icon.ico")))


if __name__ == "__main__":
    main()
