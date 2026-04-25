from core.processor_factory import ProcessorFactory


class Dispatcher:

    def __init__(self, app):
        self.app = app

    def dispatch(self, tipo, caminho, dados):
        """
        Resolve e executa o processor correspondente ao tipo de instrumento.
        Resolves and executes the processor corresponding to the instrument type.

        Args:
            tipo (str): Tipo do instrumento / Instrument type.
            caminho (str): Caminho do arquivo a processar / File path to process.
            dados (dict): Dados extraídos do PDF / Data extracted from the PDF.
        """
        processor = ProcessorFactory.get_processor(tipo, self.app)
        processor.processar(caminho, dados)