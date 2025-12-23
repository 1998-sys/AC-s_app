import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos

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


ctk.set_appearance_mode("light")

ODS_RED = "#D81F3C"
ODS_RED_HOVER = "#B51A32"
ODS_BG = "#FFFFFF"
ODS_FRAME = "#F0F0F0"
ODS_ENTRY = "#E0E0E0"
ODS_TEXT = "#333333"
ODS_WHITE = "#FFFFFF"
ODS_OK = "#10B981"
ODS_ERROR = "#D81F3C"


def extrair_tag_base(tag: str) -> str:
    if "-" not in tag:
        return tag
    return "-".join(tag.split("-")[:-1])


def to_float_safe(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


class App(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=ODS_BG)
        self.pack(fill="both", expand=True, padx=20, pady=20)

        self.master.title("Análise Crítica de Certificados")
        self.master.geometry("680x480")
        self.master.resizable(False, False)
        self.master.configure(fg_color=ODS_BG)

        # Título
        self.lbl_title = ctk.CTkLabel(
            self,
            text="Gerador de Análise Crítica",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=ODS_TEXT
        )
        self.lbl_title.pack(pady=(10, 25))

        # Botões
        self.btn_pdf = ctk.CTkButton(
            self,
            text="Selecionar Certificado PDF",
            width=300,
            height=44,
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            corner_radius=10,
            command=self.selecionar_pdf
        )
        self.btn_pdf.pack(pady=10)

        self.btn_consultar = ctk.CTkButton(
            self,
            text="Consultar / Atualizar Dados",
            width=300,
            height=44,
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            corner_radius=10,
            command=self.abrir_consulta
        )
        self.btn_consultar.pack(pady=10)

        # Status 
        self.lbl_pdf = ctk.CTkLabel(
            self,
            text="Nenhum PDF selecionado.",
            text_color=ODS_TEXT
        )
        self.lbl_pdf.pack(pady=18)

        # resultados
        self.result_frame = ctk.CTkFrame(
            self,
            fg_color=ODS_FRAME,
            corner_radius=12
        )
        self.result_frame.pack(fill="x", pady=10, padx=10)

    # PDF
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

            self.after(
                0,
                lambda: self.processar_comparacao(dados_pdf, caminho_pdf)
            )

        except Exception as e:
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Erro",
                    f"Erro ao processar PDF:\n{e}"
                )
            )

    # Comparação e validação
    def processar_comparacao(self, dados_pdf, caminho_pdf_original):
        tag_pdf = dados_pdf["tag"].strip().upper()
        dados_pdf["tag"] = tag_pdf

        sn_pdf = dados_pdf.get("sn_instrumento")

        registro = buscar_instrumento_por_tag(tag_pdf)
        reg_sn = buscar_por_sn_instrumento(sn_pdf) if sn_pdf else None

        ctx = ValidationContext(
            dados_pdf=dados_pdf,
            registro=registro,
            reg_sn=reg_sn,
            tag_base_pdf=extrair_tag_base(tag_pdf),
            tag_base_sn=extrair_tag_base(reg_sn["tag"]) if reg_sn else None
        )

        engine = ValidationEngine()
        issues = engine.run(ctx)

        dados_ok = True

        for issue in issues:
            if issue.action:
                resposta = messagebox.askyesno(
                    issue.title,
                    f"{issue.message}\n\nDeseja aplicar a correção/inclusão?"
                )

                if resposta:
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
            try:
                caminho_final, _ = gerar_ac(dados_pdf, caminho_pdf_original)
                messagebox.showinfo(
                    "AC Gerada",
                    f"Arquivo salvo em:\n{caminho_final}"
                )
            except PermissionError as e:
                messagebox.showerror(
                    "Arquivo em uso",
                    str(e)
                )
            except Exception as e:
                messagebox.showerror(
                    "Erro ao gerar AC",
                    f"Ocorreu um erro inesperado:\n{e}"
                )
        else:
            messagebox.showwarning(
                "AC NÃO GERADA",
                "Existem divergências pendentes."
            )

        self.lbl_pdf.configure(text="Processamento concluído.")

    # Resultados
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
                font=ctk.CTkFont(size=13)
            ).pack(anchor="w", padx=15, pady=4)

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

    # Consulta e atualização
    def abrir_consulta(self):
        win = ctk.CTkToplevel(self)
        win.title("Consultar / Atualizar Dados")
        win.geometry("440x480")
        win.configure(fg_color=ODS_BG)
        win.grab_set()

        ctk.CTkLabel(win, text="TAG", text_color=ODS_TEXT).pack(pady=(15, 0))

        entry_tag = ctk.CTkEntry(
            win,
            width=280,
            fg_color=ODS_ENTRY,
            text_color=ODS_TEXT,
            border_color=ODS_RED
        )
        entry_tag.pack()

        campos = {
            "sn_instrumento": ctk.StringVar(),
            "sn_sensor": ctk.StringVar(),
            "min_range": ctk.StringVar(),
            "max_range": ctk.StringVar()
        }

        entries = {}

        for nome, var in campos.items():
            ctk.CTkLabel(
                win,
                text=nome.replace("_", " ").title(),
                text_color=ODS_TEXT
            ).pack(pady=(10, 0))

            e = ctk.CTkEntry(
                win,
                textvariable=var,
                state="readonly",
                width=280,
                fg_color=ODS_ENTRY,
                text_color=ODS_TEXT
            )
            e.pack()
            entries[nome] = e

        def consultar():
            tag = entry_tag.get().strip().upper()
            if not tag:
                messagebox.showerror("Erro", "TAG inválida")
                return

            registro = buscar_instrumento_por_tag(tag)
            if not registro:
                messagebox.showerror("Erro", "TAG não encontrada")
                return

            for k in campos:
                campos[k].set(registro[k])

        def editar():
            for e in entries.values():
                e.configure(state="normal")

        def salvar():
            tag = entry_tag.get().strip().upper()
            if not tag:
                messagebox.showerror("Erro", "TAG inválida")
                return

            min_range = to_float_safe(campos["min_range"].get())
            max_range = to_float_safe(campos["max_range"].get())

            if min_range is None or max_range is None:
                messagebox.showerror("Erro", "Range deve ser numérico")
                return

            atualizar_sn(tag, campos["sn_instrumento"].get())
            atualizar_sn_sensor(tag, campos["sn_sensor"].get())
            atualizar_range(tag, min_range, max_range)

            messagebox.showinfo("Sucesso", "Dados atualizados com sucesso")

            for e in entries.values():
                e.configure(state="readonly")

        ctk.CTkButton(
            win,
            text="Consultar",
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            command=consultar
        ).pack(pady=10)

        ctk.CTkButton(
            win,
            text="Editar",
            fg_color=ODS_FRAME,
            border_width=1,
            border_color=ODS_RED,
            text_color=ODS_TEXT,
            command=editar
        ).pack(pady=5)

        ctk.CTkButton(
            win,
            text="Salvar",
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            command=salvar
        ).pack(pady=10)