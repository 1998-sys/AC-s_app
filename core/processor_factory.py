from processors.secundario_processor import SecundarioProcessor
from processors.placa_processor import PlacaProcessor
from processors.ci_processor import CIProcessor


class ProcessorFactory:

    @staticmethod
    def get_processor(tipo, app):
        """
        Instancia e retorna o processor correspondente ao tipo de instrumento.
        Instantiates and returns the processor corresponding to the instrument type.

        Args:
            tipo (str): Tipo do instrumento / Instrument type.
                        Valores suportados / Supported values: 'secundario', 'placa_orificio', 'ci'.
            app: Referência à instância da aplicação / Reference to the application instance.

        Returns:
            Processor: Instância do processor correspondente / Corresponding processor instance.

        Raises:
            ValueError: Se o tipo não for suportado / If the type is not supported.
        """
        processors = {
            "secundario": SecundarioProcessor(app),
            "placa_orificio": PlacaProcessor(app),
            "ci": CIProcessor(app),
        }

        if tipo not in processors:
            raise ValueError(f"Tipo não suportado: {tipo}")

        return processors[tipo]