from processors.base_processor import BaseProcessor


class CIProcessor(BaseProcessor):

    def processar(self, caminho, dados_pdf):
        self.app.dados_certificado_atual = dados_pdf
        self.app.dados_report_atual = None
        self.app.pontos_calibracao = []
        self.app.pontos_calibracao_petro = None

        self.app.after(
            0,
            lambda: self.app.processar_comparacao(dados_pdf)
        )
