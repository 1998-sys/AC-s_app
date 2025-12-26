import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import os
import sys
from PIL import Image 

# Seus imports de módulos locais
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
from xml_model.xml_extractor import extrair_pontos_calibracao_pdf

ctk.set_appearance_mode("light")

# Paleta de Cores ODS (Mantendo o visual moderno)
ODS_RED = "#D81F3C"
ODS_RED_HOVER = "#B51A32"
ODS_BG = "#FFFFFF"      # Fundo do painel interno (branco puro)
ODS_FRAME = "#F5F5F5"   # Fundo da janela principal (cinza muito claro para o efeito de "sombra")
ODS_ENTRY = "#E0E0E0"
ODS_TEXT = "#333333"
ODS_WHITE = "#FFFFFF"
ODS_OK = "#10B981"
ODS_ERROR = "#D81F3C"

# Configuração da Fonte
FONT_FAMILY = "Inter" # Fonte moderna e limpa

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
        # O frame principal usa ODS_FRAME para simular o fundo da janela/sombra
        super().__init__(master, fg_color=ODS_FRAME)
        self.pack(fill="both", expand=True, padx=10, pady=10) # Padding para simular a margem externa

        self.master.title("Análise Crítica de Certificados")
        self.master.geometry("400x550") # Tamanho ajustado para o layout compacto e largura aumentada
        self.master.resizable(False, False)
        self.master.configure(fg_color=ODS_FRAME) # Janela principal também usa ODS_FRAME

        # Frame interno que contém todo o conteúdo e o rodapé
        self.main_content_frame = ctk.CTkFrame(self, fg_color=ODS_BG, corner_radius=12)
        self.main_content_frame.pack(fill="both", expand=True)

        # ================= CONFIGURAÇÃO DO GRID PRINCIPAL (PAINEL ÚNICO) =================
        self.main_content_frame.grid_columnconfigure(0, weight=1) # Coluna única, centralizada
        self.main_content_frame.grid_rowconfigure(0, weight=0)    # Linha 0: Logo/Título (não expandível)
        self.main_content_frame.grid_rowconfigure(1, weight=0)    # Linha 1: Botões (não expandível)
        self.main_content_frame.grid_rowconfigure(2, weight=1)    # Linha 2: Resultados (expandível)
        self.main_content_frame.grid_rowconfigure(3, weight=0)    # Linha 3: Rodapé (não expandível)

        # ================= LOGO E TÍTULO (LINHA 0) =================
        
        # Frame para centralizar a logo e o título
        self.header_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(30, 10), sticky="n")
        self.header_frame.grid_columnconfigure(0, weight=1)

        # >>>>>>>>>>>>> LOCAL PARA INSERIR A LOGO <<<<<<<<<<<<<
        # Exemplo de inserção da logo (necessita do arquivo 'logo.jpg' no diretório)
        # Tamanho reduzido para o layout compacto (ex: 100x50)
        self.logo_img = ctk.CTkImage(light_image=Image.open("logo\logo.jpg"), size=(100, 50))
        self.lbl_logo = ctk.CTkLabel(self.header_frame, image=self.logo_img, text="")
        self.lbl_logo.pack(pady=(0, 5))
        
        # Título
        self.lbl_title = ctk.CTkLabel(
            self.header_frame,
            text="Gerador de Análise Crítica",
            font=ctk.CTkFont(family=FONT_FAMILY, size=24, weight="bold"), # Fonte e tamanho ajustados
            text_color=ODS_TEXT
        )
        self.lbl_title.pack(pady=(5, 20))

        # ================= BOTÕES (LINHA 1) =================
        self.buttons_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")
        self.buttons_frame.grid(row=1, column=0, pady=(0, 20), sticky="n")
        self.buttons_frame.grid_columnconfigure(0, weight=1)

        self.btn_pdf = ctk.CTkButton(
            self.buttons_frame,
            text="Selecionar Certificado PDF",
            width=350, # Largura aumentada
            height=48,
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            command=self.selecionar_pdf
        )
        self.btn_pdf.pack(pady=5)

        self.btn_consultar = ctk.CTkButton(
            self.buttons_frame,
            text="Consultar / Atualizar Dados",
            width=350, # Largura aumentada
            height=48,
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            command=self.abrir_consulta
        )
        self.btn_consultar.pack(pady=5)

        # Status (Abaixo dos botões)
        self.lbl_pdf = ctk.CTkLabel(
            self.buttons_frame,
            text="Nenhum PDF selecionado.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=ODS_TEXT
        )
        self.lbl_pdf.pack(pady=(10, 0))

        # ================= RESULTADOS (LINHA 2) =================
        self.result_frame = ctk.CTkFrame(
            self.main_content_frame,
            fg_color=ODS_FRAME, # Usando o cinza claro para o frame de resultados
            corner_radius=12
        )
        # Usa grid para ocupar o espaço restante
        self.result_frame.grid(row=2, column=0, pady=20, padx=50, sticky="nsew") 
        self.result_frame.grid_columnconfigure(0, weight=1)
        self.result_frame.grid_rowconfigure(0, weight=1)

        # Placeholder para o conteúdo do result_frame
        ctk.CTkLabel(
            self.result_frame,
            text="Área de Mensagens Importantes / Resultados",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#888888"
        ).grid(row=0, column=0, padx=20, pady=20, sticky="nsew")


        # ================= RODAPÉ (LINHA 3) =================
        self.footer_label = ctk.CTkLabel(
            self.main_content_frame,
            text="Developed by: M.Bandeira, L. Zambelli, G. Machado",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color="#888888"
        )
        self.footer_label.grid(row=3, column=0, pady=(5, 5), sticky="s")


    # PDF (MÉTODOS DE FUNCIONALIDADE MANTIDOS)
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
            pontos=extrair_pontos_calibracao_pdf(caminho_pdf)
            print(dados_pdf)
            print(pontos)
            

            self.after(
                0,
                lambda: self.processar_comparacao(dados_pdf, caminho_pdf)
            )

        except Exception as e:
            erro=str(e)
            self.after(
                0,
                lambda erro=erro: messagebox.showerror(
                    "Erro",
                    f"Erro ao processar PDF:\n{erro}"
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
                font=ctk.CTkFont(family=FONT_FAMILY, size=13)
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

    # Consulta e atualização (MÉTODOS DE FUNCIONALIDADE MANTIDOS)
    def abrir_consulta(self):
        win = ctk.CTkToplevel(self)
        win.title("Consultar / Atualizar Dados")
        win.geometry("440x480")
        win.configure(fg_color=ODS_FRAME)
        win.grab_set()

        ctk.CTkLabel(win, text="TAG", text_color=ODS_TEXT, font=ctk.CTkFont(family=FONT_FAMILY, size=13)).pack(pady=(15, 0))

        entry_tag = ctk.CTkEntry(
            win,
            width=280,
            fg_color=ODS_ENTRY,
            text_color=ODS_TEXT,
            border_color=ODS_RED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13)
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
                text_color=ODS_TEXT,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13)
            ).pack(pady=(10, 0))

            e = ctk.CTkEntry(
                win,
                textvariable=var,
                state="readonly",
                width=280,
                fg_color=ODS_ENTRY,
                text_color=ODS_TEXT,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13)
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
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            command=consultar
        ).pack(pady=10)

        ctk.CTkButton(
            win,
            text="Editar",
            fg_color=ODS_FRAME,
            border_width=1,
            border_color=ODS_RED,
            text_color=ODS_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            command=editar
        ).pack(pady=5)

        ctk.CTkButton(
            win,
            text="Salvar",
            fg_color=ODS_RED,
            hover_color=ODS_RED_HOVER,
            text_color=ODS_WHITE,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            command=salvar
        ).pack(pady=10)