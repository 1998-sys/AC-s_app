# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : core.dispatcher
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Resolves the instrument type to its processor and dispatches the extracted data for processing.
#                 Resolve o tipo de instrumento para seu processor e despacha os dados extraídos para processamento.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from core.processor_factory import ProcessorFactory


class Dispatcher:

    def __init__(self, app):
        """Store the reference to the application, used to pass it to the resolved processor on each dispatch."""
        self.app = app

    def dispatch(self, tipo, caminho, dados):
        """Resolve the processor matching the instrument type and run the processing.

        Args:
            tipo: Instrument type (e.g., 'secundario', 'placa_orificio', 'trecho').
            caminho: Path of the file to process.
            dados: Data extracted from the PDF to be processed.
        """
        processor = ProcessorFactory.get_processor(tipo, self.app)
        processor.processar(caminho, dados) 