# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : core.processor_factory
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Factory that instantiates the processor class matching a given instrument type.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from processors.secundario_processor import SecundarioProcessor
from processors.placa_processor import PlacaProcessor
from processors.trecho_processor import TrechoProcessor


class ProcessorFactory:

    @staticmethod
    def get_processor(tipo, app):
        """Instantiate and return the processor matching the instrument type.

        Args:
            tipo: Instrument type. Supported values: 'secundario', 'placa_orificio', 'trecho'.
            app: Reference to the application instance, passed on to the instantiated processor.

        Returns:
            Processor: Instance of the processor matching the given type.

        Raises:
            ValueError: If the type is not supported.

        Notes:
            'ci' and 'cromatografia' are handled directly in
            gui/pdf_service.py::PdfProcessingService and never reach this factory.
        """
        classes = {
            "secundario": SecundarioProcessor,
            "placa_orificio": PlacaProcessor,
            "trecho": TrechoProcessor,
        }

        if tipo not in classes:
            raise ValueError(f"Tipo não suportado: {tipo}")

        return classes[tipo](app)