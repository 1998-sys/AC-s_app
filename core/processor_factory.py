from processors.secundario_processor import SecundarioProcessor
from processors.placa_processor import PlacaProcessor


class ProcessorFactory:

    @staticmethod
    def get_processor(tipo, app):

        processors = {
            "secundario": SecundarioProcessor(app),
            "placa_orificio": PlacaProcessor(app)
        }

        if tipo not in processors:
            raise ValueError(f"Tipo não suportado: {tipo}")

        return processors[tipo]