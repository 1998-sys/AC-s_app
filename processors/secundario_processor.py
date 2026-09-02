# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.secundario_processor
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Handles the flow for secondary instruments, extracting calibration points directly from the certificate before starting the review.
#                 Trata o fluxo dos instrumentos secundários, extraindo os pontos de calibração direto do certificado antes de iniciar a revisão.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from processors.base_processor import BaseProcessor
from processors.utils import fluxo_origem
from xml_model.xml_extractor import extrair_pontos_calibracao_pdf
from xml_model.xml_table_extractor import processar_pdf


class SecundarioProcessor(BaseProcessor):
    """Processor for secondary instruments: extracts the calibration points
    directly from the certificate, without requesting an additional
    Evaluation Report."""

    def processar(self, caminho, dados_pdf):
        """Processes a secondary instrument's certificate and starts the
        review.

        Extracts the calibration points (standard format and Petrobrás
        format) directly from the certificate and triggers the origin flow
        (e.g., ORIGEM client) before opening the review screen.

        Args:
            caminho: Path to the certificate PDF.
            dados_pdf: Data extracted from the certificate.
        """

        self.app.pontos_calibracao = extrair_pontos_calibracao_pdf(caminho)
        self.app.pontos_calibracao_petro = processar_pdf(caminho)

        def continuar(dados):
            """Forwards the final data to start the review screen."""
            self.app.iniciar_revisao(dados)

        self.app.after(
            0,
            lambda: fluxo_origem(
                app=self.app,
                dados_certificado=dados_pdf,
                callback=continuar
            )
        )
