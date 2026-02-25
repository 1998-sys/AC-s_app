class BaseProcessor:

    def __init__(self, app):
        self.app = app

    def processar(self, caminho, dados):
        raise NotImplementedError(
            "Cada processor deve implementar o método processar()"
        )