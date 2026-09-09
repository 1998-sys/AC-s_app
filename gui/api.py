# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gui.api
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Exposes the facade class injected into pywebview as js_api, delegating each UI action to its dedicated gui service.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

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
        """Initializes the review-session state (ongoing review and batch queue) and instantiates the delegated services.

        Notes:
            `_window` starts as None and is only set in `set_window`; see the
            explanation there of why this reference must stay private.
        """
        # Name has a leading underscore on purpose: pywebview injects this object as
        # `js_api` and recursively reflects over every public (non-underscore)
        # attribute looking for methods to expose to JS (see pywebview/util.py
        # `get_functions`). If `window` (the native WebView2/WinForms object)
        # were public, that reflection would walk down the native COM
        # accessibility graph — which has real circular references — and blow up
        # with a RecursionError plus cross-thread access to CoreWebView2Controller,
        # hanging the window for several seconds right at app startup.
        self._window = None
        self.dispatcher = Dispatcher(self)

        # State of the review session in progress, shared by the services below.
        self.pontos_calibracao = []
        self.caminho_pdf_atual = None
        # TE (temperature element) → TT/TIT (transmitter) uses the same
        # certificate number as the TE that measures it; matched by the TAG part
        # without the type prefix (see xml_model.xml_generator.chave_par_te).
        # A dict per pair avoids that, with several TE+TT pairs in the same batch,
        # a TT would mistakenly pick up the certificate of another instrument's
        # TE — which would happen with a single "last TE seen" value (a real
        # bug found in this session). It lives for the whole app session (it is
        # not reset per reading), since the user may process the TE and the
        # TT in separate actions, not necessarily in the same batch.
        self.certificados_te_por_par = {}
        self.pontos_calibracao_petro = None
        self.dados_certificado_atual = None
        self.dados_report_atual = None
        self.dados_dim_tr = None
        self.tipo_instrumento_atual = None

        self._issues_pendentes = {}
        self._dados_pdf_review = None
        self._registro_review = None

        # State of the batch processing queue (Phase 5 — multiple PDFs).
        # Shared between PdfProcessingService (which feeds and advances it) and
        # RevisionService (which appends a result each time an AC is generated).
        self.fila_processamento = []
        self.indice_fila = 0
        self.resultados_lote = []
        self.eventos_lote = []

        # Phase 6: aggregated batch review — one item per certificate read
        # successfully (data/record/divergences), filled in by
        # RevisionService.coletar_revisao_lote while the queue is read without
        # pausing, and consumed by the aggregated divergences screen/gerar_lote
        # only after all queue items have finished being read.
        self.instrumentos_lote = []

        self._dialogs = DialogBridge(self)
        self._pdf_service = PdfProcessingService(self)
        self._revision_service = RevisionService(self)
        self._instrument_service = InstrumentService(self)
        self._import_export_service = ImportExportService(self)

    def set_window(self, window):
        """Registers the created pywebview window, used by DialogBridge to call evaluate_js."""
        self._window = window

    # ---------- Dialog bridge / navigation (used by the UI and by the processors) ----------

    def _js(self, expr):
        """Delegates to `DialogBridge.js`."""
        return self._dialogs.js(expr)

    def confirm(self, title, message):
        """Delegates to `DialogBridge.confirm`."""
        return self._dialogs.confirm(title, message)

    def alert(self, title, message, variant="info"):
        """Delegates to `DialogBridge.alert`."""
        return self._dialogs.alert(title, message, variant)

    def prompt(self, title, message, fields):
        """Delegates to `DialogBridge.prompt`."""
        return self._dialogs.prompt(title, message, fields)

    def escolher_arquivo(self, titulo, extensoes):
        """Delegates to `DialogBridge.escolher_arquivo`."""
        return self._dialogs.escolher_arquivo(titulo, extensoes)

    def escolher_arquivos(self, titulo, extensoes):
        """Delegates to `DialogBridge.escolher_arquivos`."""
        return self._dialogs.escolher_arquivos(titulo, extensoes)

    def after(self, delay, fn, *args):
        """Delegates to `DialogBridge.after`."""
        self._dialogs.after(delay, fn, *args)

    def _progress(self, percent, active, done):
        """Delegates to `DialogBridge.progress`."""
        self._dialogs.progress(percent, active, done)

    def _voltar_para_selecao(self):
        """Delegates to `DialogBridge.voltar_para_selecao`."""
        self._dialogs.voltar_para_selecao()

    def solicitar_dados_origem(self, dados_pdf, callback):
        """Delegates to `PdfProcessingService.solicitar_dados_origem`."""
        return self._pdf_service.solicitar_dados_origem(dados_pdf, callback)

    def dados_origem_automaticos(self, tag):
        """Delegates to `PdfProcessingService.dados_origem_automaticos`."""
        return self._pdf_service.dados_origem_automaticos(tag)

    # ---------- Screen 1 → 2: PDF/XML selection, reading and classification ----------

    def escolher_arquivos_pdf(self):
        """Delegates to `PdfProcessingService.escolher_arquivos_pdf`."""
        return self._pdf_service.escolher_arquivos_pdf()

    def receber_arquivos_soltos(self, arquivos):
        """Delegates to `PdfProcessingService.receber_arquivos_soltos`."""
        return self._pdf_service.receber_arquivos_soltos(arquivos)

    def iniciar_leitura(self, itens):
        """Delegates to `PdfProcessingService.iniciar_leitura`."""
        return self._pdf_service.iniciar_leitura(itens)

    def cancelar_leitura(self):
        """Delegates to `PdfProcessingService.cancelar_leitura`."""
        return self._pdf_service.cancelar_leitura()

    # ---------- Screen 3: review divergences / generate AC ----------

    def iniciar_revisao(self, dados_pdf):
        """Delegates to `RevisionService.iniciar_revisao`."""
        return self._revision_service.iniciar_revisao(dados_pdf)

    def resolver_divergencia(self, key, aplicar):
        """Delegates to `RevisionService.resolver_divergencia`."""
        return self._revision_service.resolver_divergencia(key, aplicar)

    def desfazer_divergencia(self, key):
        """Delegates to `RevisionService.desfazer_divergencia`."""
        return self._revision_service.desfazer_divergencia(key)

    def voltar_da_revisao(self):
        """Delegates to `RevisionService.voltar_da_revisao`."""
        return self._revision_service.voltar_da_revisao()

    def confirmar_geracao(self):
        """Delegates to `RevisionService.confirmar_geracao`."""
        return self._revision_service.confirmar_geracao()

    def abrir_arquivo(self, caminho):
        """Delegates to `RevisionService.abrir_arquivo`."""
        return self._revision_service.abrir_arquivo(caminho)

    # ---------- Screen 3 (Phase 6): aggregated batch review ----------

    def resolver_divergencia_lote(self, tag, key, aplicar):
        """Delegates to `RevisionService.resolver_divergencia_lote`."""
        return self._revision_service.resolver_divergencia_lote(tag, key, aplicar)

    def desfazer_divergencia_lote(self, tag, key):
        """Delegates to `RevisionService.desfazer_divergencia_lote`."""
        return self._revision_service.desfazer_divergencia_lote(tag, key)

    def pular_instrumento_lote(self, tag):
        """Delegates to `RevisionService.pular_instrumento_lote`."""
        return self._revision_service.pular_instrumento_lote(tag)

    def confirmar_geracao_lote(self):
        """Delegates to `RevisionService.confirmar_geracao_lote`."""
        return self._revision_service.confirmar_geracao_lote()

    # ---------- Screen 5: edit / look up instrument ----------

    def buscar_instrumento(self, tag):
        """Delegates to `InstrumentService.buscar_instrumento`."""
        return self._instrument_service.buscar_instrumento(tag)

    def salvar_instrumento(self, payload):
        """Delegates to `InstrumentService.salvar_instrumento`."""
        return self._instrument_service.salvar_instrumento(payload)

    # ---------- XLSX import / export ----------

    def importar_xlsx(self):
        """Delegates to `ImportExportService.importar_xlsx`."""
        return self._import_export_service.importar_xlsx()

    def exportar_xlsx(self):
        """Delegates to `ImportExportService.exportar_xlsx`."""
        return self._import_export_service.exportar_xlsx()
