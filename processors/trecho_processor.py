# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.trecho_processor
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Handles the Gas Meter Run (straight length/Trecho Reto) instrument flow, requesting the Evaluation Report and extracting its dimensional data.
#                 Trata o fluxo do instrumento Gas Meter Run (trecho reto), solicitando o Evaluation Report e extraindo seus dados dimensionais.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from processors.base_processor import BaseProcessor
from pdf.parser_tr_ER import extrair_campos_er_tr
from xml_model.xml_extractor_TR import extrair_dados_dim_tr


class TrechoProcessor(BaseProcessor):

    def processar(self, caminho_certificado, dados_pdf):
        """Inicia o fluxo do Gas Meter Run solicitando o Evaluation Report.
        Initiates the Gas Meter Run flow by requesting the Evaluation Report."""
        self._iniciar_fluxo_com_report(
            caminho_certificado,
            dados_pdf,
            "Dados do relatório dimensional não foram carregados corretamente."
        )

    def _reset_extra(self):
        self.app.dados_dim_tr = None

    def _titulo_instrumento(self):
        return "Gas Meter Run"

    def _mensagem_confirmacao(self):
        return (
            "Instrumento identificado como Gas Meter Run / Trecho Reto.\n\n"
            "Deseja selecionar o Evaluation Report?"
        )

    def _titulo_selecionar_arquivo(self):
        return "Selecionar Evaluation Report"

    def _msg_nenhum_arquivo(self):
        return "Nenhum Evaluation Report selecionado."

    def _extrair_dados_er(self, texto_report):
        return extrair_campos_er_tr(texto_report)

    def _pos_processar_er(self, caminho_certificado):
        self.app.dados_dim_tr = extrair_dados_dim_tr(caminho_certificado)
        self.app.pontos_calibracao = []

    def _titulo_erro_report(self):
        return "Erro no Evaluation Report"
