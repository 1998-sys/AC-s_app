import tkinter as tk
from tkinter import filedialog, messagebox
from threading import Thread
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos
from data.utils_db import (
    buscar_instrumento_por_tag,
    buscar_por_sn_instrumento
)
from form.utils_print import gerar_ac

from validation.engine import ValidationEngine
from validation.context import ValidationContext


def extrair_tag_base(tag: str) -> str:
    if "-" not in tag:
        return tag
    partes = tag.split("-")
    return "-".join(partes[:-1])


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Análise Crítica de Certificados")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        self.btn_selecionar = tk.Button(
            root,
            text="Selecionar Certificado PDF",
            command=self.selecionar_pdf,
            width=30,
            height=2
        )
        self.btn_selecionar.pack(pady=20)

        self.lbl_pdf = tk.Label(root, text="Nenhum PDF selecionado.")
        self.lbl_pdf.pack()

        self.result_frame = tk.Frame(root)
        self.result_frame.pack(pady=20)

    # ======================================================
    # SELEÇÃO DE PDF (THREAD)
    # ======================================================
    def selecionar_pdf(self):
        caminho_pdf = filedialog.askopenfilename(
            title="Selecione o certificado PDF",
            filetypes=[("Arquivos PDF", "*.pdf")]
        )

        if not caminho_pdf:
            return

        self.lbl_pdf.config(
            text=f"Processando: {os.path.basename(caminho_pdf)} ..."
        )

        Thread(
            target=self._processar_pdf_thread,
            args=(caminho_pdf,),
            daemon=True
        ).start()

    def _processar_pdf_thread(self, caminho_pdf):
        try:
            texto = extrair_texto(caminho_pdf)
            dados_pdf = extrair_campos(texto)

            self.root.after(
                0,
                lambda: self.processar_comparacao(dados_pdf, caminho_pdf)
            )

        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Erro",
                    f"Erro ao processar PDF:\n{e}"
                )
            )

    # ======================================================
    # PROCESSAMENTO PRINCIPAL (MOTOR)
    # ======================================================
    def processar_comparacao(self, dados_pdf, caminho_pdf_original):

        tag_pdf = dados_pdf["tag"]
        sn_pdf = dados_pdf.get("sn_instrumento")

        registro = buscar_instrumento_por_tag(tag_pdf)
        reg_sn = buscar_por_sn_instrumento(sn_pdf) if sn_pdf else None

        tag_base_pdf = extrair_tag_base(tag_pdf)
        tag_base_sn = extrair_tag_base(reg_sn["tag"]) if reg_sn else None

        ctx = ValidationContext(
            dados_pdf=dados_pdf,
            registro=registro,
            reg_sn=reg_sn,
            tag_base_pdf=tag_base_pdf,
            tag_base_sn=tag_base_sn
        )

        engine = ValidationEngine()
        issues = engine.run(ctx)

        dados_ok = True

        # --------------------------------------------------
        # INTERAÇÃO GUI ↔ MOTOR
        # --------------------------------------------------
        for issue in issues:

            if issue.action:
                resposta = messagebox.askyesno(
                    issue.title,
                    f"{issue.message}\n\nDeseja aplicar a correção?"
                )

                if resposta:
                    issue.action()
                else:
                    dados_ok = False
                    if issue.blocking:
                        break
            else:
                messagebox.showwarning(
                    issue.title,
                    issue.message
                )
                if issue.blocking:
                    dados_ok = False
                    break

        # --------------------------------------------------
        # EXIBIÇÃO + GERAÇÃO AC
        # --------------------------------------------------
        registro_final = buscar_instrumento_por_tag(tag_pdf)
        self.exibir_resultado(dados_pdf, registro_final)

        if dados_ok:
            caminho_final, _ = gerar_ac(dados_pdf, caminho_pdf_original)
            messagebox.showinfo(
                "AC Gerada",
                f"Arquivo salvo em:\n{caminho_final}"
            )
        else:
            messagebox.showwarning(
                "AC NÃO GERADA",
                "Existem divergências pendentes."
            )

        self.lbl_pdf.config(text="Processamento concluído.")

    # ======================================================
    # EXIBIÇÃO
    # ======================================================
    def exibir_resultado(self, dados_pdf, registro):
        for w in self.result_frame.winfo_children():
            w.destroy()

        def add(text, ok):
            tk.Label(
                self.result_frame,
                text=text,
                fg="green" if ok else "red"
            ).pack(anchor="w")

        add(
            f"TAG: {dados_pdf['tag']} | {registro['tag']}",
            dados_pdf["tag"] == registro["tag"]
        )

        add(
            f"SN Instrumento: {dados_pdf.get('sn_instrumento')} | {registro['sn_instrumento']}",
            dados_pdf.get("sn_instrumento") == registro["sn_instrumento"]
        )

        if dados_pdf.get("sn_sensor"):
            add(
                f"SN Sensor: {dados_pdf['sn_sensor']} | {registro['sn_sensor']}",
                dados_pdf["sn_sensor"] == registro["sn_sensor"]
            )