from processors.base_processor import BaseProcessor
from pdf.parser_po_ER import extrair_campos_er
from xml_model.xml_extractor_PO import extrair_valores_medidos


class PlacaProcessor(BaseProcessor):

    def processar(self, caminho_certificado, dados_pdf):
        self._iniciar_fluxo_com_report(
            caminho_certificado,
            dados_pdf,
            "Dados do certificado não foram carregados corretamente."
        )

    def _titulo_instrumento(self):
        return "Placa de Orifício"

    def _mensagem_confirmacao(self):
        return (
            "Instrumento identificado como Placa de Orifício.\n\n"
            "Deseja selecionar o Report Valuation?"
        )

    def _titulo_selecionar_arquivo(self):
        return "Selecionar Report Valuation"

    def _msg_nenhum_arquivo(self):
        return "Nenhum Report selecionado."

    def _extrair_dados_er(self, texto_report):
        return extrair_campos_er(texto_report)

    def _pos_processar_er(self, caminho_certificado):
        pontos = extrair_valores_medidos(caminho_certificado)
        if not pontos:
            raise ValueError(
                "Não foi possível extrair os pontos de calibração do certificado."
            )
        self.app.pontos_calibracao = pontos

        if not self.app.dados_certificado_atual:
            raise ValueError(
                "Dados do certificado não estão disponíveis para comparação."
            )

    def _titulo_erro_report(self):
        return "Erro no Report"
