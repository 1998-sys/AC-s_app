from core.processor_factory import ProcessorFactory


class Dispatcher:

    def __init__(self, app):
        self.app = app

    def dispatch(self, tipo, caminho, dados):
        processor = ProcessorFactory.get_processor(tipo, self.app)
        processor.processar(caminho, dados)