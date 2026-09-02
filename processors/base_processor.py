# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.base_processor
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Defines the base processor class and the shared "certificate then Evaluation Report" flow reused by the concrete instrument processors.
#                 Define a classe base dos processors e o fluxo compartilhado "certificado depois Evaluation Report" reutilizado pelos processors concretos de instrumento.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from threading import Thread

from pdf.extrator import extrair_texto
from processors.utils import fluxo_origem


class BaseProcessor:
    """Base class for instrument processors: defines the `processar()` contract that
    each concrete subclass implements and provides the reusable template flow
    "certificate -> request Evaluation Report -> review" via the hooks below."""

    def __init__(self, app):
        self.app = app

    def processar(self, caminho, dados):
        """Processes the instrument's certificate and drives the flow to the review screen.

        Abstract method: each concrete subclass must implement the flow
        specific to its instrument type.

        Args:
            caminho: Path to the certificate PDF file.
            dados: Data already extracted from the certificate.

        Raises:
            NotImplementedError: Always, in the base class — must be overridden
                by subclasses.
        """
        raise NotImplementedError(
            "Cada processor deve implementar o método processar()"
        )

    # ---- Template method: fluxo "certificado -> pedir Evaluation Report -> revisão" ----
    # Usado por processors cujo certificado sozinho não basta para a revisão:
    # o usuário precisa selecionar um segundo PDF (Evaluation Report/Report
    # Valuation) antes de comparar e abrir a tela de revisão. TrechoProcessor
    # e PlacaProcessor configuram esse fluxo via os hooks abaixo em vez de
    # reimplementar o confirm -> file dialog -> thread -> try/except inteiro.

    def _iniciar_fluxo_com_report(self, caminho_certificado, dados_pdf, msg_dados_ausentes):
        """Starts the shared flow of requesting a second document (Evaluation
        Report) before the review.

        Validates whether the certificate data was extracted; if not, alerts
        the user and returns to selection. Otherwise, stores the certificate
        data, clears the current report and the subclass's extra fields
        (via `_reset_extra`) and schedules the report request on the UI
        thread.

        Args:
            caminho_certificado: Path to the already-processed certificate PDF.
            dados_pdf: Data extracted from the certificate; if empty/None, the
                flow is aborted.
            msg_dados_ausentes: Error message shown to the user when
                `dados_pdf` is empty.
        """
        if not dados_pdf:
            self.app.alert("Erro", msg_dados_ausentes, "error")
            self.app._voltar_para_selecao()
            return

        self.app.dados_certificado_atual = dados_pdf
        self.app.dados_report_atual = None
        self._reset_extra()

        self.app.after(0, lambda: self._solicitar_report(caminho_certificado))

    def _solicitar_report(self, caminho_certificado):
        """Asks the user whether they want to select the Evaluation Report
        and, if so, opens the file dialog and triggers processing on a
        separate thread.

        Args:
            caminho_certificado: Path to the certificate PDF, passed along to
                the report processing.

        Notes:
            If the user declines the confirmation or does not select any
            file, the flow returns to the selection screen instead of
            proceeding.
        """
        resposta = self.app.confirm(self._titulo_instrumento(), self._mensagem_confirmacao())

        if not resposta:
            self.app._voltar_para_selecao()
            return

        caminho_report = self.app.escolher_arquivo(
            self._titulo_selecionar_arquivo(),
            ("PDF (*.pdf)",)
        )

        if not caminho_report:
            self.app.alert("Erro", self._msg_nenhum_arquivo(), "error")
            self.app._voltar_para_selecao()
            return

        Thread(
            target=self._processar_report,
            args=(caminho_certificado, caminho_report),
            daemon=True
        ).start()

    def _processar_report(self, caminho_certificado, caminho_report):
        """Extracts and processes the text of the selected Evaluation Report,
        comparing it with the certificate and starting the review.

        Runs on a separate thread (see `_solicitar_report`). Extracts the
        text from the report PDF, delegates field extraction to the
        `_extrair_dados_er` hook, runs the subclass-specific
        post-processing (`_pos_processar_er`) and then triggers the origin
        flow (e.g., ORIGEM client) before opening the review screen. Any
        exception is caught and shown as an alert to the user, returning to
        the selection screen.

        Args:
            caminho_certificado: Path to the certificate PDF.
            caminho_report: Path to the Evaluation Report PDF selected
                by the user.
        """
        try:
            texto_report = extrair_texto(caminho_report)
            if not texto_report:
                raise ValueError("Não foi possível extrair texto do Evaluation Report.")

            dados_er = self._extrair_dados_er(texto_report)
            if not dados_er:
                raise ValueError("Não foi possível extrair informações do Evaluation Report.")

            self.app.dados_report_atual = dados_er
            self._pos_processar_er(caminho_certificado)

            def continuar(dados):
                """Forwards the final data to start the review screen."""
                self.app.iniciar_revisao(dados)

            self.app.after(
                0,
                lambda: fluxo_origem(
                    app=self.app,
                    dados_certificado=self.app.dados_certificado_atual,
                    callback=continuar
                )
            )

        except Exception as e:
            def mostrar_erro():
                """Shows the error that occurred while processing the report
                and returns to the selection screen."""
                self.app.alert(self._titulo_erro_report(), str(e), "error")
                self.app._voltar_para_selecao()

            self.app.after(0, mostrar_erro)

    # Hooks que cada subclasse que usar _iniciar_fluxo_com_report deve implementar.

    def _reset_extra(self):
        """Optional hook to reset subtype-specific extra fields before
        requesting the report.

        Notes:
            Default implementation does nothing; TrechoProcessor overrides
            it to clear `self.app.dados_dim_tr`.
        """
        pass

    def _titulo_instrumento(self):
        """Abstract hook: instrument title used in the confirmation dialog
        and the report error message.

        Returns:
            str: Instrument name, defined by each subclass.
        """
        raise NotImplementedError

    def _mensagem_confirmacao(self):
        """Abstract hook: confirmation message shown to the user before
        requesting the report.

        Returns:
            str: Confirmation message text, defined by each
            subclass.
        """
        raise NotImplementedError

    def _titulo_selecionar_arquivo(self):
        """Abstract hook: title of the report file selection dialog.

        Returns:
            str: Dialog title, defined by each subclass.
        """
        raise NotImplementedError

    def _msg_nenhum_arquivo(self):
        """Abstract hook: error message shown when no report file is
        selected.

        Returns:
            str: Message text, defined by each subclass.
        """
        raise NotImplementedError

    def _extrair_dados_er(self, texto_report):
        """Abstract hook: extracts the relevant fields from the Evaluation
        Report text.

        Args:
            texto_report: Text extracted from the Evaluation Report PDF.

        Returns:
            Data extracted from the report, in a format defined by each
            subclass.
        """
        raise NotImplementedError

    def _pos_processar_er(self, caminho_certificado):
        """Optional hook for extra subtype-specific work after extracting
        the Evaluation Report data.

        Args:
            caminho_certificado: Path to the certificate PDF, available for
                re-extraction if needed.

        Notes:
            Default implementation does nothing. Subclasses use this hook to
            extract additional data (e.g., dimensional data or measured
            calibration points) and may raise ValueError to abort the
            flow with an error message.
        """
        pass

    def _titulo_erro_report(self):
        """Abstract hook: title of the error dialog shown when report
        processing fails.

        Returns:
            str: Error dialog title, defined by each subclass.
        """
        raise NotImplementedError
