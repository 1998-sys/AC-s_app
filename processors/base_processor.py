# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.base_processor
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Defines the base processor class and the shared "certificate then Evaluation Report" flow reused by the concrete instrument processors.
#                 Define a classe base dos processors e o fluxo compartilhado "certificado depois Evaluation Report" reutilizado pelos processors concretos de instrumento.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from threading import Thread

from pdf.extrator import extrair_texto
from processors.utils import fluxo_origem


class BaseProcessor:

    def __init__(self, app):
        self.app = app

    def processar(self, caminho, dados):
        raise NotImplementedError(
            "Cada processor deve implementar o método processar()"
        )

    # ---- Template method: fluxo "certificado -> pedir Evaluation Report -> revisão" ----
    # Usado por processors cujo certificado sozinho não basta para a revisão:
    # o usuário precisa selecionar um segundo PDF (Evaluation Report/Report
    # Valuation) antes de comparar e abrir a tela de revisão. TrechoProcessor
    # e PlacaProcessor configuram esse fluxo via os hooks abaixo em vez de
    # reimplementar o confirm -> file dialog -> thread -> try/except inteiro.

    def _iniciar_fluxo_com_report(self, caminho_certificado, dados_pdf, msg_dados_ausentes):
        if not dados_pdf:
            self.app.alert("Erro", msg_dados_ausentes, "error")
            self.app._voltar_para_selecao()
            return

        self.app.dados_certificado_atual = dados_pdf
        self.app.dados_report_atual = None
        self._reset_extra()

        self.app.after(0, lambda: self._solicitar_report(caminho_certificado))

    def _solicitar_report(self, caminho_certificado):
        resposta = self.app.confirm(self._titulo_instrumento(), self._mensagem_confirmacao())

        if not resposta:
            self.app._voltar_para_selecao()
            return

        caminho_report = self.app.escolher_arquivo(
            self._titulo_selecionar_arquivo(),
            ("PDF (*.pdf)",)
        )

        if not caminho_report:
            self.app.alert("Erro", self._msg_nenhum_arquivo(), "error")
            self.app._voltar_para_selecao()
            return

        Thread(
            target=self._processar_report,
            args=(caminho_certificado, caminho_report),
            daemon=True
        ).start()

    def _processar_report(self, caminho_certificado, caminho_report):
        try:
            texto_report = extrair_texto(caminho_report)
            if not texto_report:
                raise ValueError("Não foi possível extrair texto do Evaluation Report.")

            dados_er = self._extrair_dados_er(texto_report)
            if not dados_er:
                raise ValueError("Não foi possível extrair informações do Evaluation Report.")

            self.app.dados_report_atual = dados_er
            self._pos_processar_er(caminho_certificado)

            def continuar(dados):
                self.app.iniciar_revisao(dados)

            self.app.after(
                0,
                lambda: fluxo_origem(
                    app=self.app,
                    dados_certificado=self.app.dados_certificado_atual,
                    callback=continuar
                )
            )

        except Exception as e:
            def mostrar_erro():
                self.app.alert(self._titulo_erro_report(), str(e), "error")
                self.app._voltar_para_selecao()

            self.app.after(0, mostrar_erro)

    # Hooks que cada subclasse que usar _iniciar_fluxo_com_report deve implementar.

    def _reset_extra(self):
        """Hook opcional para resetar campos extras específicos do subtipo
        (ex.: TrechoProcessor zera self.app.dados_dim_tr)."""
        pass

    def _titulo_instrumento(self):
        raise NotImplementedError

    def _mensagem_confirmacao(self):
        raise NotImplementedError

    def _titulo_selecionar_arquivo(self):
        raise NotImplementedError

    def _msg_nenhum_arquivo(self):
        raise NotImplementedError

    def _extrair_dados_er(self, texto_report):
        raise NotImplementedError

    def _pos_processar_er(self, caminho_certificado):
        """Hook para trabalho extra específico do subtipo após extrair o ER
        (ex.: extrair dados dimensionais/pontos de calibração medidos). Pode
        levantar ValueError para abortar o fluxo com uma mensagem de erro."""
        pass

    def _titulo_erro_report(self):
        raise NotImplementedError
