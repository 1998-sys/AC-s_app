# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : core.processor_factory
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Factory that instantiates the processor class matching a given instrument type.
#                 Fábrica que instancia a classe de processor correspondente a um dado tipo de instrumento.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from processors.secundario_processor import SecundarioProcessor
from processors.placa_processor import PlacaProcessor
from processors.trecho_processor import TrechoProcessor


class ProcessorFactory:

    @staticmethod
    def get_processor(tipo, app):
        """
        Instancia e retorna o processor correspondente ao tipo de instrumento.
        Instantiates and returns the processor corresponding to the instrument type.

        Args:
            tipo (str): Tipo do instrumento / Instrument type.
                        Valores suportados / Supported values: 'secundario', 'placa_orificio', 'trecho'.
                        Obs.: 'ci' e 'cromatografia' são tratados diretamente em
                        gui/pdf_service.py::PdfProcessingService e nunca chegam a este factory.
            app: Referência à instância da aplicação / Reference to the application instance.

        Returns:
            Processor: Instância do processor correspondente / Corresponding processor instance.

        Raises:
            ValueError: Se o tipo não for suportado / If the type is not supported.
        """
        classes = {
            "secundario": SecundarioProcessor,
            "placa_orificio": PlacaProcessor,
            "trecho": TrechoProcessor,
        }

        if tipo not in classes:
            raise ValueError(f"Tipo não suportado: {tipo}")

        return classes[tipo](app)