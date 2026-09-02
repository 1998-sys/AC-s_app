# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.trecho_processor
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Handles the Gas Meter Run (straight length/Trecho Reto) instrument flow, requesting the Evaluation Report and extracting its dimensional data.
#                 Trata o fluxo do instrumento Gas Meter Run (trecho reto), solicitando o Evaluation Report e extraindo seus dados dimensionais.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from processors.base_processor import BaseProcessor
from pdf.parser_tr_ER import extrair_campos_er_tr
from xml_model.xml_extractor_TR import extrair_dados_dim_tr


class TrechoProcessor(BaseProcessor):
    """Processor for the Gas Meter Run (straight length) instrument: requests
    the Evaluation Report and extracts the dimensional data from the
    certificate."""

    def processar(self, caminho_certificado, dados_pdf):
        """Starts the Gas Meter Run flow by requesting the Evaluation Report.

        Args:
            caminho_certificado: Path to the already-processed certificate PDF.
            dados_pdf: Data extracted from the certificate.
        """
        self._iniciar_fluxo_com_report(
            caminho_certificado,
            dados_pdf,
            "Dados do relatório dimensional não foram carregados corretamente."
        )

    def _reset_extra(self):
        """Clears the previous straight-length dimensional data before
        requesting a new Evaluation Report."""
        self.app.dados_dim_tr = None

    def _titulo_instrumento(self):
        """Returns the "Gas Meter Run" title used in the confirmation and
        error dialogs."""
        return "Gas Meter Run"

    def _mensagem_confirmacao(self):
        """Returns the confirmation message for requesting the Evaluation
        Report."""
        return (
            "Instrumento identificado como Gas Meter Run / Trecho Reto.\n\n"
            "Deseja selecionar o Evaluation Report?"
        )

    def _titulo_selecionar_arquivo(self):
        """Returns the title of the Evaluation Report selection dialog."""
        return "Selecionar Evaluation Report"

    def _msg_nenhum_arquivo(self):
        """Returns the error message shown when no Evaluation Report is
        selected."""
        return "Nenhum Evaluation Report selecionado."

    def _extrair_dados_er(self, texto_report):
        """Extracts the fields of the Gas Meter Run's Evaluation Report.

        Args:
            texto_report: Text extracted from the Evaluation Report PDF.

        Returns:
            Data extracted from the report, as returned by
            `extrair_campos_er_tr`.
        """
        return extrair_campos_er_tr(texto_report)

    def _pos_processar_er(self, caminho_certificado):
        """Extracts the straight length's dimensional data from the
        certificate and clears the calibration points (not applicable to
        this instrument).

        Args:
            caminho_certificado: Path to the certificate PDF.
        """
        self.app.dados_dim_tr = extrair_dados_dim_tr(caminho_certificado)
        self.app.pontos_calibracao = []

    def _titulo_erro_report(self):
        """Returns the "Erro no Evaluation Report" title used in the error
        dialog."""
        return "Erro no Evaluation Report"
