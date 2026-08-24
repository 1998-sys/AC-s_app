import os
import sys

from core.dispatcher import Dispatcher

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gui.dialogs import DialogBridge
from gui.pdf_service import PdfProcessingService
from gui.revision_service import RevisionService
from gui.instrument_service import InstrumentService
from gui.import_export_service import ImportExportService


class Api:
    """Backend exposto para a UI web (webui/) via pywebview. Substitui gui/interface.py.

    É a única classe que o pywebview injeta como `js_api` e o único objeto que os
    `processors/*` conhecem como `self.app` — por isso continua expondo todos os
    métodos/atributos abaixo diretamente. Por dentro, porém, cada responsabilidade
    (diálogos JS, processamento de PDF, revisão/validação, CRUD de instrumento,
    import/export XLSX) vive em uma classe de serviço própria; a Api apenas mantém
    o estado da sessão de revisão e delega.
    """

    def __init__(self):
        # Nome com underscore de propósito: pywebview injeta este objeto como
        # `js_api` e reflete recursivamente sobre todo atributo público não-
        # privado em busca de métodos pra expor ao JS (ver pywebview/util.py
        # `get_functions`). Se `window` (o objeto nativo do WebView2/WinForms)
        # fosse público, essa reflexão desceria pelo grafo de acessibilidade
        # COM nativo — que tem referências circulares reais — e explodiria em
        # RecursionError + acessos cross-thread ao CoreWebView2Controller,
        # travando a janela por vários segundos logo na abertura do app.
        self._window = None
        self.dispatcher = Dispatcher(self)

        # Estado da sessão de revisão em andamento, compartilhado pelos serviços abaixo.
        self.pontos_calibracao = []
        self.caminho_pdf_atual = None
        self.certificado_te_atual = None
        self.pontos_calibracao_petro = None
        self.dados_certificado_atual = None
        self.dados_report_atual = None
        self.dados_dim_tr = None
        self.tipo_instrumento_atual = None

        self._issues_pendentes = {}
        self._dados_pdf_review = None
        self._registro_review = None

        self._dialogs = DialogBridge(self)
        self._pdf_service = PdfProcessingService(self)
        self._revision_service = RevisionService(self)
        self._instrument_service = InstrumentService(self)
        self._import_export_service = ImportExportService(self)

    def set_window(self, window):
        self._window = window

    # ---------- Bridge de diálogos / navegação (usado pela UI e pelos processors) ----------

    def _js(self, expr):
        return self._dialogs.js(expr)

    def confirm(self, title, message):
        return self._dialogs.confirm(title, message)

    def alert(self, title, message, variant="info"):
        return self._dialogs.alert(title, message, variant)

    def prompt(self, title, message, fields):
        return self._dialogs.prompt(title, message, fields)

    def escolher_arquivo(self, titulo, extensoes):
        return self._dialogs.escolher_arquivo(titulo, extensoes)

    def after(self, delay, fn, *args):
        self._dialogs.after(delay, fn, *args)

    def _progress(self, percent, active, done):
        self._dialogs.progress(percent, active, done)

    def _voltar_para_selecao(self):
        self._dialogs.voltar_para_selecao()

    def solicitar_dados_origem(self, dados_pdf, callback):
        return self._pdf_service.solicitar_dados_origem(dados_pdf, callback)

    # ---------- Tela 1 → 2: seleção, leitura e classificação do PDF/XML ----------

    def selecionar_pdf(self):
        return self._pdf_service.selecionar_pdf()

    # ---------- Tela 3: revisar divergências / gerar AC ----------

    def iniciar_revisao(self, dados_pdf):
        return self._revision_service.iniciar_revisao(dados_pdf)

    def resolver_divergencia(self, key, aplicar):
        return self._revision_service.resolver_divergencia(key, aplicar)

    def confirmar_geracao(self):
        return self._revision_service.confirmar_geracao()

    def abrir_arquivo(self, caminho):
        return self._revision_service.abrir_arquivo(caminho)

    # ---------- Tela 5: editar / consultar instrumento ----------

    def buscar_instrumento(self, tag):
        return self._instrument_service.buscar_instrumento(tag)

    def salvar_instrumento(self, payload):
        return self._instrument_service.salvar_instrumento(payload)

    # ---------- Importação / exportação XLSX ----------

    def importar_xlsx(self):
        return self._import_export_service.importar_xlsx()

    def exportar_xlsx(self):
        return self._import_export_service.exportar_xlsx()
