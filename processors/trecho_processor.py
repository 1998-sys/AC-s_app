from processors.base_processor import BaseProcessor
from tkinter import filedialog, messagebox
from threading import Thread
from pdf.extrator import extrair_texto
from pdf.parser_tr_ER import extrair_campos_er_tr
from processors.utils import fluxo_origem


class TrechoProcessor(BaseProcessor):

    def processar(self, caminho_certificado, dados_pdf):
        """Inicia o fluxo do Gas Meter Run solicitando o Evaluation Report.
        Initiates the Gas Meter Run flow by requesting the Evaluation Report."""
        if not dados_pdf:
            messagebox.showerror(
                "Erro",
                "Dados do relatório dimensional não foram carregados corretamente."
            )
            return

        self.app.dados_certificado_atual = dados_pdf
        self.app.dados_report_atual = None

        self.app.after(0, lambda: self._solicitar_report(caminho_certificado))

    def _solicitar_report(self, caminho_certificado):
        resposta = messagebox.askyesno(
            "Gas Meter Run",
            "Instrumento identificado como Gas Meter Run / Trecho Reto.\n\n"
            "Deseja selecionar o Evaluation Report?"
        )

        if not resposta:
            return

        caminho_report = filedialog.askopenfilename(
            title="Selecionar Evaluation Report",
            filetypes=[("PDF", "*.pdf")]
        )

        if not caminho_report:
            messagebox.showerror("Erro", "Nenhum Evaluation Report selecionado.")
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

            dados_er = extrair_campos_er_tr(texto_report)
            if not dados_er:
                raise ValueError("Não foi possível extrair informações do Evaluation Report.")

            self.app.dados_report_atual = dados_er
            self.app.pontos_calibracao = []

            def continuar(dados):
                self.app.processar_comparacao(dados)

            self.app.after(
                0,
                lambda: fluxo_origem(
                    app=self.app,
                    dados_certificado=self.app.dados_certificado_atual,
                    callback=continuar
                )
            )

        except Exception as e:
            self.app.after(
                0,
                lambda: messagebox.showerror("Erro no Evaluation Report", str(e))
            )
