from processors.base_processor import BaseProcessor
from processors.utils import fluxo_origem
from xml_model.xml_extractor import extrair_pontos_calibracao_pdf
from xml_model.xml_table_extractor import processar_pdf


class SecundarioProcessor(BaseProcessor):

    def processar(self, caminho, dados_pdf):

        self.app.pontos_calibracao = extrair_pontos_calibracao_pdf(caminho)
        self.app.pontos_calibracao_petro = processar_pdf(caminho)

        def continuar(dados):
            self.app.iniciar_revisao(dados)

        self.app.after(
            0,
            lambda: fluxo_origem(
                app=self.app,
                dados_certificado=dados_pdf,
                callback=continuar
            )
        )