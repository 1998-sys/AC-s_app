from processors.base_processor import BaseProcessor
from tkinter import filedialog, messagebox
from threading import Thread
from pdf.extrator import extrair_texto
from pdf.parser_po_ER import extrair_campos_er
from xml_model.xml_extractor_PO import extrair_valores_medidos


class PlacaProcessor(BaseProcessor):

    def processar(self, caminho_certificado, dados_pdf):

        if not dados_pdf:
            messagebox.showerror(
                "Erro",
                "Dados do certificado não foram carregados corretamente."
            )
            return

        self.app.dados_certificado_atual = dados_pdf
        print(dados_pdf)
        self.app.dados_report_atual = None

        self.app.after(
            0,
            lambda: self._solicitar_report(caminho_certificado)
        )

    def _solicitar_report(self, caminho_certificado):

        resposta = messagebox.askyesno(
            "Placa de Orifício",
            "Instrumento identificado como Placa de Orifício.\n\n"
            "Deseja selecionar o Report Valuation?"
        )

        if not resposta:
            return

        caminho_report = filedialog.askopenfilename(
            title="Selecionar Report Valuation",
            filetypes=[("PDF", "*.pdf")]
        )

        if not caminho_report:
            messagebox.showerror("Erro", "Nenhum Report selecionado.")
            return

        Thread(
            target=self._processar_report,
            args=(caminho_certificado, caminho_report),
            daemon=True
        ).start()

    # ✅ AGORA ESTÁ DENTRO DA CLASSE
    def _processar_report(self, caminho_certificado, caminho_report):
        try:
            texto_report = extrair_texto(caminho_report)
            if not texto_report:
                raise ValueError(
                    "Não foi possível extrair texto do Evaluation Report."
                )

            dados_er = extrair_campos_er(texto_report)
            if not dados_er:
                raise ValueError(
                    "Não foi possível extrair informações do Evaluation Report."
                )

            self.app.dados_report_atual = dados_er
            print(dados_er)

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

            self.app.after(
                0,
                lambda: self.app.processar_comparacao(
                    self.app.dados_certificado_atual
                )
            )

        except Exception as e:
            erro_msg = str(e)
            self.app.after(
                0,
                messagebox.showerror,
                "Erro no Report",
                erro_msg
            )