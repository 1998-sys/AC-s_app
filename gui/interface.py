import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import os
import sys
from pathlib import Path
from PIL import Image


sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
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
except ImportError as e:
    print(f"Aviso: Módulos internos não encontrados. Erro: {e}")

ctk.set_appearance_mode("light")

ODS_RED = "#D81F3C"
ODS_RED_HOVER = "#B51A32"
ODS_BG = "#FFFFFF"
ODS_DARK = "#343A40"
ODS_TEXT = "#1A1A1A"
ODS_FRAME_LIGHT = "#F8F9FA"
ODS_OK = "#10B981"
ODS_ERROR = "#D81F3C"

FONT_FAMILY = "Segoe UI" 


def extrair_tag_base(tag: str) -> str:
    return "-".join(tag.split("-")[:-1]) if "-" in tag else tag

def to_float_safe(value):
    try: return float(str(value).replace(",", "."))
    except: return None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurações de Janela
        self.title("Ac's Generator")
        self.geometry("420x800")
        self.resizable(False, False)
        self.configure(fg_color=ODS_BG)


        self._definir_logo_janela()

        self.pontos_calibracao = []
        self.caminho_pdf_atual = None

        self._build_ui()

    def _definir_logo_janela(self):
        """Carrega a imagem PNG e a define como ícone da janela e barra de tarefas"""
        try:
            caminho_logo = os.path.join("logo", "ods-logo2.png")
            if os.path.exists(caminho_logo):
                # Carregamos com PIL
                img_icon = Image.open(caminho_logo)
                # Convertemos para um formato que o Tkinter entende (importante manter a referência)
                self.img_icon_tk = ctk.CTkImage(light_image=img_icon, dark_image=img_icon)
                
                # Usamos o método nativo iconphoto através de um pequeno delay para garantir que a janela já exista
                self.after(200, lambda: self.wm_iconphoto(False, self._load_icon_native(caminho_logo)))
        except Exception as e:
            print(f"Erro ao carregar ícone: {e}")

    def _load_icon_native(self, path):
        """Função auxiliar para converter PNG em PhotoImage nativo do Tkinter"""
        from tkinter import PhotoImage
        return PhotoImage(file=path)

    def _build_ui(self):
        self.header_frame = ctk.CTkFrame(self, fg_color=ODS_RED, height=100, corner_radius=0)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)

        logo_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        logo_container.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            logo_container, 
            text="AC'S GENERATOR", 
            text_color="white", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=26, weight="bold")
        ).pack(pady=0)

        ctk.CTkLabel(
            logo_container, 
            text="ODS METERING SYSTEMS", 
            text_color="white", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold")
        ).pack(pady=(0, 5))

        
        self.content_frame = ctk.CTkFrame(self, fg_color=ODS_BG, corner_radius=0)
        self.content_frame.pack(fill="both", expand=True, padx=25)

       
        try:
            img_dog = Image.open("logo/logo.jpg")
            logo_dog = ctk.CTkImage(img_dog, size=(150, 150))
            self.dog_label = ctk.CTkLabel(self.content_frame, image=logo_dog, text="")
            self.dog_label.pack(pady=(40, 30))
        except: pass

    
        button_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        button_container.pack(fill="x", pady=5)

        self.btn_pdf = ctk.CTkButton(
            button_container,
            text="GERAR\nRELATÓRIO",
            width=175, height=70,
            fg_color=ODS_RED, hover_color=ODS_RED_HOVER,
            font=(FONT_FAMILY, 13, "bold"), corner_radius=12,
            command=self.selecionar_pdf
        )
        self.btn_pdf.pack(side="left", padx=(0, 10), expand=True)

        self.btn_consulta = ctk.CTkButton(
            button_container,
            text="EDITAR\nINSTRUMENTO",
            width=175, height=70,
            fg_color=ODS_RED, hover_color=ODS_RED_HOVER,
            font=(FONT_FAMILY, 13, "bold"), corner_radius=12,
            command=self.abrir_consulta
        )
        self.btn_consulta.pack(side="right", expand=True)

        
        self.status_container = ctk.CTkFrame(
            self.content_frame, 
            fg_color=ODS_FRAME_LIGHT, 
            corner_radius=15, 
            border_width=1, 
            border_color="#E0E0E0"
        )
        self.status_container.pack(fill="both", expand=True, pady=(30, 30))

        self.lbl_pdf = ctk.CTkLabel(
            self.status_container,
            text="Aguardando seleção de PDF...",
            font=(FONT_FAMILY, 12, "italic"),
            text_color="#7F8C8D", wraplength=320
        )
        self.lbl_pdf.pack(pady=20)

        self.result_frame = ctk.CTkFrame(self.status_container, fg_color="transparent")
        self.result_frame.pack(fill="both", expand=True, padx=15)

        
        self.footer = ctk.CTkFrame(self, fg_color=ODS_DARK, height=38, corner_radius=0)
        self.footer.pack(fill="x", side="bottom")
        ctk.CTkLabel(
            self.footer, 
            text="Developed By: M.Bandeira, L. Zambelli, G. Machado © 2025", 
            text_color="#BDC3C7", 
            font=(FONT_FAMILY, 10)
        ).pack(expand=True)

    
    def selecionar_pdf(self):
        caminho = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not caminho: return
        self.caminho_pdf_atual = caminho
        self.lbl_pdf.configure(text=f"Processando: {os.path.basename(caminho)}", font=(FONT_FAMILY, 11, "bold"), text_color=ODS_TEXT)
        Thread(target=self._processar_pdf_thread, args=(caminho,), daemon=True).start()

    def _processar_pdf_thread(self, caminho):
        try:
            texto = extrair_texto(caminho)
            dados_pdf = extrair_campos(texto)
            self.pontos_calibracao = extrair_pontos_calibracao_pdf(caminho)
            self.after(0, lambda: self.processar_comparacao(dados_pdf))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro no PDF", str(e)))

    def processar_comparacao(self, dados_pdf):
        tag = dados_pdf["tag"].upper()
        dados_pdf["tag"] = tag
        registro = buscar_instrumento_por_tag(tag)
        reg_sn = buscar_por_sn_instrumento(dados_pdf.get("sn_instrumento"))
        ctx = ValidationContext(dados_pdf=dados_pdf, registro=registro, reg_sn=reg_sn, 
                                tag_base_pdf=extrair_tag_base(tag), 
                                tag_base_sn=extrair_tag_base(registro["tag"]) if registro else None, 
                                pontos=self.pontos_calibracao)
        engine = ValidationEngine()
        issues = engine.run(ctx)
        ok = True
        for issue in issues:
            if issue.action:
                if messagebox.askyesno(issue.title, issue.message): issue.action()
                else:
                    ok = False
                    if issue.blocking: break
            else:
                messagebox.showwarning(issue.title, issue.message)
                if issue.blocking: ok = False; break
        if ok:
            try:
                caminho_ac, _ = gerar_ac(dados_pdf, self.caminho_pdf_atual)
                caminho_xml = Path(str(caminho_ac).replace("_AC", "")).with_suffix(".xml")
                gerar_xml_calibracao(dados_pdf, self.pontos_calibracao, str(caminho_xml), dados_pdf.get("certificado_te_anterior"))
                messagebox.showinfo("Sucesso", "Análise e XML concluídos!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro na geração: {e}")
        self.exibir_resultado(dados_pdf, registro)

    def exibir_resultado(self, dados_pdf, registro):
        for w in self.result_frame.winfo_children(): w.destroy()
        if not registro: return
        def linha(txt, ok):
            ctk.CTkLabel(self.result_frame, text=txt, text_color=ODS_OK if ok else ODS_ERROR, font=(FONT_FAMILY, 12, "bold")).pack(anchor="w", pady=2)
        linha(f"TAG: {dados_pdf['tag']} | DB: {registro['tag']}", dados_pdf["tag"] == registro["tag"])
        linha(f"SN Instr.: {dados_pdf.get('sn_instrumento')} | DB: {registro['sn_instrumento']}", 
              dados_pdf.get("sn_instrumento") == registro["sn_instrumento"])

    def abrir_consulta(self):
        win = ctk.CTkToplevel(self)
        win.title("Consulta de Instrumento")
        win.geometry("400x550")
        win.configure(fg_color=ODS_BG)
        win.grab_set()
        
        
        try:
            caminho_logo = os.path.join("logo", "ods-logo2.png")
            if os.path.exists(caminho_logo):
                win.after(200, lambda: win.wm_iconphoto(False, self._load_icon_native(caminho_logo)))
        except: pass

        sub_h = ctk.CTkFrame(win, fg_color=ODS_RED, height=50, corner_radius=0)
        sub_h.pack(fill="x")
        ctk.CTkLabel(sub_h, text="EDITAR DADOS TÉCNICOS", text_color="white", font=(FONT_FAMILY, 14, "bold")).pack(expand=True)
        container = ctk.CTkFrame(win, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=20)
        campos = {"sn_instrumento": ctk.StringVar(), "sn_sensor": ctk.StringVar(), "min_range": ctk.StringVar(), "max_range": ctk.StringVar()}
        ctk.CTkLabel(container, text="TAG do Instrumento", font=(FONT_FAMILY, 11, "bold")).pack(anchor="w")
        entry_tag = ctk.CTkEntry(container, width=340, height=35)
        entry_tag.pack(pady=(0, 15))
        entries = {}
        for k, var in campos.items():
            ctk.CTkLabel(container, text=k.replace("_", " ").title(), font=(FONT_FAMILY, 11)).pack(anchor="w")
            e = ctk.CTkEntry(container, textvariable=var, state="readonly", width=340, height=32, fg_color=ODS_FRAME_LIGHT)
            e.pack(pady=(0, 10))
            entries[k] = e
        def consultar():
            tag = entry_tag.get().upper()
            reg = buscar_instrumento_por_tag(tag)
            if not reg:
                messagebox.showerror("Erro", "TAG não encontrada.")
                return
            for k in campos: campos[k].set(reg[k])
        def editar():
            for e in entries.values(): e.configure(state="normal", fg_color="#FFFFFF")
        def salvar():
            tag = entry_tag.get().upper()
            min_r, max_r = to_float_safe(campos["min_range"].get()), to_float_safe(campos["max_range"].get())
            if min_r is None or max_r is None:
                messagebox.showerror("Erro", "Ranges inválidos.")
                return
            atualizar_sn(tag, campos["sn_instrumento"].get())
            atualizar_sn_sensor(tag, campos["sn_sensor"].get())
            atualizar_range(tag, min_r, max_r)
            messagebox.showinfo("Sucesso", "Dados salvos.")
            for e in entries.values(): e.configure(state="readonly", fg_color=ODS_FRAME_LIGHT)
        ctk.CTkButton(container, text="CONSULTAR", fg_color=ODS_DARK, command=consultar, height=35).pack(fill="x", pady=5)
        btn_grid = ctk.CTkFrame(container, fg_color="transparent")
        btn_grid.pack(fill="x", pady=5)
        ctk.CTkButton(btn_grid, text="EDITAR", fg_color=ODS_RED, command=editar, width=160, height=35).pack(side="left")
        ctk.CTkButton(btn_grid, text="SALVAR", fg_color=ODS_OK, command=salvar, width=160, height=35).pack(side="right")

