import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import os
import sys
from pathlib import Path
from PIL import Image

# ================= IMPORTS LOCAIS =================
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos
from xml_model.xml_extractor import extrair_pontos_calibracao_pdf
from xml_model.xml_generator import gerar_xml_calibracao

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
        self.master.geometry("420x650")
        self.master.resizable(False, False)

        self.pontos_calibracao = []
        self.caminho_pdf_atual = None

        # ================= FRAME PRINCIPAL =================
        self.main = ctk.CTkFrame(self, fg_color=ODS_BG, corner_radius=12)
        self.main.pack(fill="both", expand=True)

        # ================= CABEÇALHO =================
        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.pack(pady=20)

        logo = ctk.CTkImage(Image.open("logo/logo.jpg"), size=(110, 55))
        ctk.CTkLabel(header, image=logo, text="").pack()

        ctk.CTkLabel(
            header,
            text="Gerador de Análise Crítica",
            font=ctk.CTkFont(FONT_FAMILY, 24, "bold"),
            text_color=ODS_TEXT
        ).pack(pady=10)

        # ================= BOTÕES =================
        self.btn_pdf = ctk.CTkButton(
            self.main,
            text="Selecionar Certificado PDF",
            width=360,
            height=45,
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            command=self.selecionar_pdf
        )
        self.btn_pdf.pack(pady=5)

        self.btn_consulta = ctk.CTkButton(
            self.main,
            text="Consultar / Editar Instrumento",
            width=360,
            height=45,
            fg_color=ODS_FRAME,
            border_color=ODS_RED,
            border_width=1,
            text_color=ODS_TEXT,
            command=self.abrir_consulta
        )
        self.btn_consulta.pack(pady=5)

        self.lbl_pdf = ctk.CTkLabel(
            self.main,
            text="Nenhum PDF selecionado",
            text_color=ODS_TEXT
        )
        self.lbl_pdf.pack(pady=10)

        # ================= RESULTADOS =================
        self.result_frame = ctk.CTkFrame(self.main, fg_color=ODS_FRAME)
        self.result_frame.pack(fill="x", padx=30, pady=15)

    # =====================================================
    # PDF
    # =====================================================
    def selecionar_pdf(self):
        caminho = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not caminho:
            return

        self.caminho_pdf_atual = caminho
        self.lbl_pdf.configure(text=f"Processando {os.path.basename(caminho)}")

        Thread(
            target=self._processar_pdf_thread,
            args=(caminho,),
            daemon=True
        ).start()

    def _processar_pdf_thread(self, caminho):
        try:
            texto = extrair_texto(caminho)
            dados_pdf = extrair_campos(texto)
            self.pontos_calibracao = extrair_pontos_calibracao_pdf(caminho)

            self.after(0, lambda: self.processar_comparacao(dados_pdf))

        except Exception as e:
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Erro ao processar PDF",
                    str(e)
                )
            )

    # =====================================================
    # VALIDAÇÃO + AC + XML
    # =====================================================
    def processar_comparacao(self, dados_pdf):
        tag = dados_pdf["tag"].upper()
        dados_pdf["tag"] = tag

        registro = buscar_instrumento_por_tag(tag)
        reg_sn = buscar_por_sn_instrumento(
            dados_pdf.get("sn_instrumento")
        )

        ctx = ValidationContext(
            dados_pdf=dados_pdf,
            registro=registro,
            reg_sn=reg_sn,
            tag_base_pdf=extrair_tag_base(tag),
            tag_base_sn=extrair_tag_base(registro["tag"]) if registro else None,
            pontos=self.pontos_calibracao
        )

        engine = ValidationEngine()
        issues = engine.run(ctx)

        ok = True
        for issue in issues:
            if issue.action:
                if messagebox.askyesno(issue.title, issue.message):
                    issue.action()
                else:
                    ok = False
                    if issue.blocking:
                        break
            else:
                messagebox.showwarning(issue.title, issue.message)
                if issue.blocking:
                    ok = False
                    break

        # ================= AC + XML =================
        if ok:
            try:
                caminho_ac, _ = gerar_ac(
                    dados_pdf,
                    self.caminho_pdf_atual
                )

                caminho_xml = Path(caminho_ac).with_suffix(".xml")

                gerar_xml_calibracao(
                    dados_pdf,
                    self.pontos_calibracao,
                    str(caminho_xml),
                    dados_pdf.get("certificado_te_anterior")
                )

                messagebox.showinfo(
                    "Sucesso",
                    f"AC e XML gerados com sucesso:\n\n{caminho_xml}"
                )

            except PermissionError:
                messagebox.showerror(
                    "Arquivo em uso",
                    "⚠ Não foi possível gerar a Análise Crítica.\n\n"
                    "O arquivo PDF está aberto em outro programa.\n\n"
                    "➡ Feche o PDF e tente novamente."
                )
                return

            except Exception as e:
                messagebox.showerror(
                    "Erro inesperado",
                    f"Ocorreu um erro ao gerar a AC:\n\n{e}"
                )
                return

        self.exibir_resultado(dados_pdf, registro)

    # =====================================================
    # RESULTADOS
    # =====================================================
    def exibir_resultado(self, dados_pdf, registro):
        for w in self.result_frame.winfo_children():
            w.destroy()

        if not registro:
            return

        def linha(txt, ok):
            ctk.CTkLabel(
                self.result_frame,
                text=txt,
                text_color=ODS_OK if ok else ODS_ERROR
            ).pack(anchor="w", padx=10, pady=2)

        linha(
            f"TAG: {dados_pdf['tag']} | {registro['tag']}",
            dados_pdf["tag"] == registro["tag"]
        )

        linha(
            f"SN Instr.: {dados_pdf.get('sn_instrumento')} | "
            f"{registro['sn_instrumento']}",
            dados_pdf.get("sn_instrumento") == registro["sn_instrumento"]
        )

    # =====================================================
    # CONSULTA / EDIÇÃO
    # =====================================================
    def abrir_consulta(self):
        win = ctk.CTkToplevel(self)
        win.title("Consulta / Edição")
        win.geometry("420x520")
        win.grab_set()

        campos = {
            "sn_instrumento": ctk.StringVar(),
            "sn_sensor": ctk.StringVar(),
            "min_range": ctk.StringVar(),
            "max_range": ctk.StringVar()
        }

        ctk.CTkLabel(win, text="TAG").pack(pady=(10, 0))
        entry_tag = ctk.CTkEntry(win, width=280)
        entry_tag.pack()

        entries = {}

        for k, var in campos.items():
            ctk.CTkLabel(win, text=k.replace("_", " ").title()).pack(pady=(10, 0))
            e = ctk.CTkEntry(
                win,
                textvariable=var,
                state="readonly",
                width=280
            )
            e.pack()
            entries[k] = e

        def consultar():
            tag = entry_tag.get().upper()
            reg = buscar_instrumento_por_tag(tag)
            if not reg:
                messagebox.showerror("Erro", "TAG não encontrada")
                return

            for k in campos:
                campos[k].set(reg[k])

        def editar():
            for e in entries.values():
                e.configure(state="normal")

        def salvar():
            tag = entry_tag.get().upper()
            min_r = to_float_safe(campos["min_range"].get())
            max_r = to_float_safe(campos["max_range"].get())

            if min_r is None or max_r is None:
                messagebox.showerror("Erro", "Range inválido")
                return

            atualizar_sn(tag, campos["sn_instrumento"].get())
            atualizar_sn_sensor(tag, campos["sn_sensor"].get())
            atualizar_range(tag, min_r, max_r)

            messagebox.showinfo("OK", "Dados atualizados")
            for e in entries.values():
                e.configure(state="readonly")

        ctk.CTkButton(win, text="Consultar", command=consultar).pack(pady=10)
        ctk.CTkButton(win, text="Editar", command=editar).pack(pady=5)
        ctk.CTkButton(win, text="Salvar", command=salvar).pack(pady=10)