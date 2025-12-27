import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import os
import sys
from PIL import Image 

# ================= IMPORTS LOCAIS =================
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos
from xml_model.xml_extractor import extrair_pontos_calibracao_pdf

from data.utils_db import (
    buscar_instrumento_por_tag,
    buscar_por_sn_instrumento,
    atualizar_sn,
    atualizar_sn_sensor,
    atualizar_range
)

from form.utils_print import gerar_ac
from validation.engine import ValidationEngine
from validation.context import ValidationContext

# ================= CONFIGURAÇÃO VISUAL =================
ctk.set_appearance_mode("light")

ODS_RED = "#D81F3C"
ODS_RED_HOVER = "#B51A32"
ODS_BG = "#FFFFFF"
ODS_FRAME = "#F5F5F5"
ODS_ENTRY = "#E0E0E0"
ODS_TEXT = "#333333"
ODS_WHITE = "#FFFFFF"
ODS_OK = "#10B981"
ODS_ERROR = "#D81F3C"

FONT_FAMILY = "Inter"


# ================= FUNÇÕES AUXILIARES =================
def extrair_tag_base(tag: str) -> str:
    if "-" not in tag:
        return tag
    return "-".join(tag.split("-")[:-1])


def to_float_safe(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


# ================= APLICAÇÃO =================
class App(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=ODS_FRAME)
        self.pack(fill="both", expand=True, padx=10, pady=10)

        self.master.title("Análise Crítica de Certificados")
        self.master.geometry("400x550")
        self.master.resizable(False, False)
        self.master.configure(fg_color=ODS_FRAME)

        # ✅ NOVO: armazenar pontos de calibração
        self.pontos_calibracao = []

        # ================= FRAME PRINCIPAL =================
        self.main_content_frame = ctk.CTkFrame(
            self, fg_color=ODS_BG, corner_radius=12
        )
        self.main_content_frame.pack(fill="both", expand=True)

        self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.main_content_frame.grid_rowconfigure(2, weight=1)

        # ================= CABEÇALHO =================
        self.header_frame = ctk.CTkFrame(
            self.main_content_frame, fg_color="transparent"
        )
        self.header_frame.grid(row=0, column=0, pady=(30, 10))

        self.logo_img = ctk.CTkImage(
            light_image=Image.open("logo/logo.jpg"),
            size=(100, 50)
        )
        ctk.CTkLabel(
            self.header_frame, image=self.logo_img, text=""
        ).pack(pady=(0, 5))

        ctk.CTkLabel(
            self.header_frame,
            text="Gerador de Análise Crítica",
            font=ctk.CTkFont(
                family=FONT_FAMILY, size=24, weight="bold"
            ),
            text_color=ODS_TEXT
        ).pack(pady=(5, 20))

        # ================= BOTÕES =================
        self.buttons_frame = ctk.CTkFrame(
            self.main_content_frame, fg_color="transparent"
        )
        self.buttons_frame.grid(row=1, column=0, pady=(0, 20))

        self.btn_pdf = ctk.CTkButton(
            self.buttons_frame,
            text="Selecionar Certificado PDF",
            width=350,
            height=48,
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            font=ctk.CTkFont(
                family=FONT_FAMILY, size=14, weight="bold"
            ),
            command=self.selecionar_pdf
        )
        self.btn_pdf.pack(pady=5)

        self.lbl_pdf = ctk.CTkLabel(
            self.buttons_frame,
            text="Nenhum PDF selecionado.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=ODS_TEXT
        )
        self.lbl_pdf.pack(pady=(10, 0))

        # ================= RESULTADOS =================
        self.result_frame = ctk.CTkFrame(
            self.main_content_frame,
            fg_color=ODS_FRAME,
            corner_radius=12
        )
        self.result_frame.grid(
            row=2, column=0, pady=20, padx=50, sticky="nsew"
        )

        # ================= RODAPÉ =================
        ctk.CTkLabel(
            self.main_content_frame,
            text="Developed by: M. Bandeira, L. Zambelli, G. Machado",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color="#888888"
        ).grid(row=3, column=0, pady=(5, 5))

    # ================= PDF =================
    def selecionar_pdf(self):
        caminho_pdf = filedialog.askopenfilename(
            title="Selecione o certificado PDF",
            filetypes=[("Arquivos PDF", "*.pdf")]
        )

        if not caminho_pdf:
            return

        self.lbl_pdf.configure(
            text=f"Processando: {os.path.basename(caminho_pdf)}..."
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
            print(dados_pdf)

            # ✅ NOVO: extrair e armazenar pontos
            self.pontos_calibracao = extrair_pontos_calibracao_pdf(caminho_pdf)
            print(self.pontos_calibracao)

            self.after(
                0,
                lambda: self.processar_comparacao(
                    dados_pdf, caminho_pdf
                )
            )

        except Exception as e:
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Erro", f"Erro ao processar PDF:\n{e}"
                )
            )

    # ================= VALIDAÇÃO =================
    def processar_comparacao(self, dados_pdf, caminho_pdf_original):
        tag_pdf = dados_pdf["tag"].strip().upper()
        dados_pdf["tag"] = tag_pdf

        sn_pdf = dados_pdf.get("sn_instrumento")

        registro = buscar_instrumento_por_tag(tag_pdf)
        reg_sn = buscar_por_sn_instrumento(sn_pdf) if sn_pdf else None

        # ✅ NOVO: pontos passam para o contexto
        ctx = ValidationContext(
            dados_pdf=dados_pdf,
            registro=registro,
            reg_sn=reg_sn,
            tag_base_pdf=extrair_tag_base(tag_pdf),
            tag_base_sn=extrair_tag_base(reg_sn["tag"]) if reg_sn else None,
            pontos=self.pontos_calibracao
        )

        engine = ValidationEngine()
        issues = engine.run(ctx)

        dados_ok = True

        for issue in issues:
            if issue.action:
                resp = messagebox.askyesno(
                    issue.title,
                    f"{issue.message}\n\nDeseja aplicar?"
                )
                if resp:
                    issue.action()
                else:
                    dados_ok = False
                    if issue.blocking:
                        break
            else:
                messagebox.showwarning(issue.title, issue.message)
                if issue.blocking:
                    dados_ok = False
                    break

        registro_final = buscar_instrumento_por_tag(tag_pdf)
        self.exibir_resultado(dados_pdf, registro_final)

        if dados_ok:
            caminho_final, _ = gerar_ac(
                dados_pdf, caminho_pdf_original
            )
            messagebox.showinfo(
                "AC Gerada", f"Arquivo salvo em:\n{caminho_final}"
            )
        else:
            messagebox.showwarning(
                "AC NÃO GERADA", "Existem divergências pendentes."
            )

        self.lbl_pdf.configure(text="Processamento concluído.")

    # ================= RESULTADOS =================
    def exibir_resultado(self, dados_pdf, registro):
        for w in self.result_frame.winfo_children():
            w.destroy()

        if not registro:
            return

        def add(text, ok):
            ctk.CTkLabel(
                self.result_frame,
                text=text,
                text_color=ODS_OK if ok else ODS_ERROR,
                font=ctk.CTkFont(
                    family=FONT_FAMILY, size=13
                )
            ).pack(anchor="w", padx=15, pady=4)

        add(
            f"TAG: {dados_pdf['tag']} | {registro['tag']}",
            dados_pdf["tag"] == registro["tag"]
        )

        add(
            f"SN Instrumento: {dados_pdf.get('sn_instrumento')} | "
            f"{registro['sn_instrumento']}",
            dados_pdf.get("sn_instrumento") == registro["sn_instrumento"]
        )