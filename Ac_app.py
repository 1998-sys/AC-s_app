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
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
    return str(base / relative_path)


def main():
    criar_tabela()
    migrar()

    api = Api()
    window = webview.create_window(
        "AC's Generator — CertiFlow",
        _resource(os.path.join("webui", "index.html")),
        js_api=api,
        width=560,
        height=940,
        resizable=False,
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
