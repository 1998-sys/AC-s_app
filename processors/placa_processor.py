# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.placa_processor
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Handles the orifice plate (Placa de Orifício) instrument flow, requesting the Report Valuation and extracting its measured points.
#                 Trata o fluxo do instrumento placa de orifício, solicitando o Report Valuation e extraindo seus pontos medidos.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from processors.base_processor import BaseProcessor
from pdf.parser_po_ER import extrair_campos_er
from xml_model.xml_extractor_PO import extrair_valores_medidos


class PlacaProcessor(BaseProcessor):
    """Processor for the Orifice Plate instrument: requests the Report
    Valuation and extracts the measured calibration points from the
    certificate."""

    def processar(self, caminho_certificado, dados_pdf):
        """Starts the Orifice Plate flow by requesting the Report Valuation.

        Args:
            caminho_certificado: Path to the already-processed certificate PDF.
            dados_pdf: Data extracted from the certificate.
        """
        self._iniciar_fluxo_com_report(
            caminho_certificado,
            dados_pdf,
            "Dados do certificado não foram carregados corretamente."
        )

    def _titulo_instrumento(self):
        """Returns the "Placa de Orifício" title used in the confirmation
        and error dialogs."""
        return "Placa de Orifício"

    def _mensagem_confirmacao(self):
        """Returns the confirmation message for requesting the Report
        Valuation."""
        return (
            "Instrumento identificado como Placa de Orifício.\n\n"
            "Deseja selecionar o Report Valuation?"
        )

    def _titulo_selecionar_arquivo(self):
        """Returns the title of the Report Valuation selection dialog."""
        return "Selecionar Report Valuation"

    def _msg_nenhum_arquivo(self):
        """Returns the error message shown when no Report Valuation is
        selected."""
        return "Nenhum Report selecionado."

    def _extrair_dados_er(self, texto_report):
        """Extracts the fields of the Orifice Plate's Evaluation Report
        (Report Valuation).

        Args:
            texto_report: Text extracted from the Report Valuation PDF.

        Returns:
            Data extracted from the report, as returned by
            `extrair_campos_er`.
        """
        return extrair_campos_er(texto_report)

    def _pos_processar_er(self, caminho_certificado):
        """Extracts the measured calibration points from the certificate and
        validates that the certificate data is available for comparison.

        Args:
            caminho_certificado: Path to the certificate PDF.

        Raises:
            ValueError: If the calibration points cannot be extracted
                from the certificate, or if the certificate data is not
                available.
        """
        pontos = extrair_valores_medidos(caminho_certificado)
        if not pontos:
            raise ValueError(
                "Não foi possível extrair os pontos de calibração do certificado."
            )
        self.app.pontos_calibracao = pontos

        if not self.app.dados_certificado_atual:
            raise ValueError(
                "Dados do certificado não estão disponíveis para comparação."
            )

    def _titulo_erro_report(self):
        """Returns the "Erro no Report" title used in the error dialog."""
        return "Erro no Report"
