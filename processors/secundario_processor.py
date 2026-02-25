from processors.base_processor import BaseProcessor
from xml_model.xml_extractor import extrair_pontos_calibracao_pdf
from xml_model.xml_table_extractor import processar_pdf


class SecundarioProcessor(BaseProcessor):

    def processar(self, caminho, dados_pdf):

        # Extração de pontos
        self.app.pontos_calibracao = extrair_pontos_calibracao_pdf(caminho)
        self.app.pontos_calibracao_petro = processar_pdf(caminho)

        def continuar(dados):
            self.app.processar_comparacao(dados)

        if "ORIGEM" in (dados_pdf.get("local") or "").upper():
            self.app.after(
                0,
                lambda: self.app.solicitar_dados_origem(dados_pdf, continuar)
            )
        else:
            self.app.after(
                0,
                lambda: continuar(dados_pdf)
            )