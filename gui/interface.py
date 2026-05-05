import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import os
import sys
from pathlib import Path
from PIL import Image
from pdf.utils_parser import select_extract
from core.dispatcher import Dispatcher
from xml_model.xml_uc_generator import gerar_xml_uc
import traceback
from xml_model.xml_cromato import xml_cromatografia

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def _resource(relative_path: str) -> str:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    return str(base / relative_path)

try:
    from pdf.extrator import extrair_texto
    from pdf.parser_certificados import extrair_campos
    from xml_model.xml_extractor import extrair_pontos_calibracao_pdf
    from xml_model.xml_generator import gerar_xml_calibracao, normalizar_certificado, tag_te
    from xml_model.xml_table_extractor import processar_pdf
    from data.utils_db import (
        buscar_instrumento_por_tag,
        buscar_por_sn_instrumento,
        atualizar_sn,
        atualizar_sn_sensor,
        atualizar_range,
        atualizar_sn_placa,
    )
    from importer.importador import ler_xlsx, executar
    from importer.relatorio import gerar as gerar_relatorio
    from xml_model.xml_extractor_PO import extrair_valores_medidos
    from xml_model.xml_petro_po import gerar_xml_certificado_po
    from form.utils_print import gerar_ac_escolha , obter_caminho_ac
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

        self.dispatcher = Dispatcher(self)

        # Configurações de Janela
        self.title("Ac's Generator")
        self.geometry("420x800")
        self.resizable(False, False)
        self.configure(fg_color=ODS_BG)


        self._definir_logo_janela()

        self.pontos_calibracao = []
        self.caminho_pdf_atual = None
        self.certificado_te_atual = None
        self.pontos_calibracao_petro = None
        self.dados_certificado_atual = None
        self.dados_report_atual = None
        self.tipo_instrumento_atual = None


        self._build_ui()

    def _definir_logo_janela(self):
        """Carrega a imagem PNG e a define como ícone da janela e barra de tarefas"""
        try:
            caminho_logo = _resource(os.path.join("logo", "ods-logo2.png"))
            if os.path.exists(caminho_logo):
                img_icon = Image.open(caminho_logo)
                self.img_icon_tk = ctk.CTkImage(light_image=img_icon, dark_image=img_icon)
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
            text="ODS ENERGY SOLUTIONS", 
            text_color="white", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold")
        ).pack(pady=(0, 5))

        
        self.content_frame = ctk.CTkFrame(self, fg_color=ODS_BG, corner_radius=0)
        self.content_frame.pack(fill="both", expand=True, padx=25)

       
        try:
            img_dog = Image.open(_resource("logo/logo.jpg"))
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

    def confirmar_sobrescrita(self, caminho_pdf):
        if not os.path.exists(caminho_pdf):
            return True

        return messagebox.askyesno(
            "Arquivo já existe",
            f"O arquivo abaixo já existe:\n\n{os.path.basename(caminho_pdf)}\n\nDeseja sobrescrever?"
        )
    
    def selecionar_pdf(self):
        caminho = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not caminho: return
        self.caminho_pdf_atual = caminho
        self.lbl_pdf.configure(text=f"Processando: {os.path.basename(caminho)}", font=(FONT_FAMILY, 11, "bold"), text_color=ODS_TEXT)
        Thread(target=self._processar_pdf_thread, args=(caminho,), daemon=True).start()

    def _processar_pdf_thread(self, caminho):
       
        try:
            dados_pdf, tipo = select_extract(caminho)

            if tipo == "cromatografia":
                xml_path = xml_cromatografia(caminho, dados_pdf)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"XML de Cromatografia gerado:\n{xml_path}"))
                self.after(0, lambda: self.exibir_resultado(dados_pdf, None))
                return

            if tipo == "ci":
                numero_ci = dados_pdf.get("numero_ci", "NI")
                xml_path = os.path.splitext(caminho)[0] + ".xml"
                gerar_xml_uc(numero_ci, dados_pdf, xml_path)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"XML de Incerteza gerado:\n{xml_path}"))
                self.after(0, lambda: self.exibir_resultado(dados_pdf, None))
                return

            self.dispatcher.dispatch(tipo, caminho, dados_pdf)

        except Exception as e:
                traceback.print_exc()
                self.after(0, lambda e=e: messagebox.showerror("Erro no PDF", str(e)))
        
    def solicitar_dados_origem(self, dados_pdf, callback):
        win = ctk.CTkToplevel(self)
        win.title("Dados Complementares")
        win.geometry("420x420")
        win.resizable(False, False)
        win.configure(fg_color=ODS_BG)
        win.grab_set()

        try:
            caminho_logo = _resource(os.path.join("logo", "ods-logo2.png"))
            if os.path.exists(caminho_logo):
                from tkinter import PhotoImage
                win.icon_img = PhotoImage(file=caminho_logo)  
                win.wm_iconphoto(False, win.icon_img)
        except Exception as e:
            print("Erro ao carregar ícone:", e)

        sub_h = ctk.CTkFrame(win, fg_color=ODS_RED, height=48, corner_radius=0)
        sub_h.pack(fill="x")
        sub_h.pack_propagate(False)

        ctk.CTkLabel(
            sub_h,
            text="DADOS COMPLEMENTARES",
            text_color="white",
            font=(FONT_FAMILY, 13, "bold")
        ).pack(expand=True)

        container = ctk.CTkFrame(win, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=25)

        var_localizacao = ctk.StringVar()
        var_sap = ctk.StringVar()
        var_nac = ctk.StringVar()

        def campo(label, var):
            ctk.CTkLabel(container, text=label, font=(FONT_FAMILY, 11)).pack(anchor="w")
            e = ctk.CTkEntry(container, textvariable=var, width=340, height=34)
            e.pack(pady=(0, 15))
            return e

        campo("Localização", var_localizacao)
        campo("SAP", var_sap)
        campo("Nº AC", var_nac)

        def salvar():
            if not var_localizacao.get().strip():
                messagebox.showerror("Erro", "Localização é obrigatória.")
                return

            dados_pdf["localizacao"] = var_localizacao.get().strip()
            dados_pdf["sap"] = var_sap.get().strip()
            dados_pdf["n_ac"] = var_nac.get().strip()

            win.destroy()
            callback(dados_pdf)

        ctk.CTkButton(
            container,
            text="SALVAR",
            fg_color=ODS_OK,
            hover_color="#059669",
            height=38,
            font=(FONT_FAMILY, 12, "bold"),
            command=salvar
        ).pack(fill="x", pady=(10, 0))

    def processar_comparacao(self, dados_pdf):
        if not dados_pdf:
            messagebox.showerror("Erro interno", "Dados do certificado estão vazios.")
            return
        is_placa = dados_pdf.get("instrumento") == "Placa de Orificio"
        tipo_instrumento = "PO" if is_placa else "SEC"

        tag = dados_pdf.get("tag")

        if not is_placa:
            if not tag:
                messagebox.showerror("Erro", "TAG não encontrada no certificado.")
                return
            tag = tag.upper()
            dados_pdf["tag"] = tag
        else:
           
            if tag:
                dados_pdf["tag"] = tag.upper()

        
        registro = None
        reg_sn = None
        if not is_placa:
            registro = buscar_instrumento_por_tag(tag)
            reg_sn = buscar_por_sn_instrumento(dados_pdf.get("sn_instrumento"))

        if tag_te(dados_pdf.get("tag")):
            self.certificado_te_atual = normalizar_certificado(dados_pdf.get("certificado"))

        
        ctx = ValidationContext(
            dados_pdf=dados_pdf,
            registro=registro,
            reg_sn=reg_sn,
            tag_base_pdf=extrair_tag_base(tag) if tag else None,
            tag_base_sn=extrair_tag_base(registro["tag"]) if registro else None,
            pontos=self.pontos_calibracao,
            tipo_instrumento=tipo_instrumento,
            dados_report=self.dados_report_atual,
            valores_medidos = extrair_valores_medidos(self.caminho_pdf_atual)
        )

        engine = ValidationEngine()
        issues = engine.run(ctx)


        ok = True
        for issue in issues:
            if issue.action:
                if messagebox.askyesno(issue.title, f"{issue.message}\n\nDeseja aplicar a correção/inclusão?"):
                    issue.action()
                    issue.resolved = True
                    dados_pdf["_novo_instrumento_inserido"] = True
                else:
                    ok = False
            if issue.blocking:
                messagebox.showerror(issue.title, issue.message)
                ok = False
                break
            else:
                messagebox.showwarning(issue.title, issue.message)
                if issue.blocking:
                    ok = False
                    break

        if ok:
            try:
                if not self.caminho_pdf_atual:
                    messagebox.showerror("Erro", "Caminho do PDF não encontrado.")
                    return

                caminho_ac = obter_caminho_ac(dados_pdf, self.caminho_pdf_atual)

                if not self.confirmar_sobrescrita(caminho_ac):
                    messagebox.showinfo("Operação cancelada", "A Análise Crítica não foi sobrescrita.")
                    self.exibir_resultado(dados_pdf, registro)
                    return

                gerar_ac_escolha(
                    dados_pdf,
                    self.caminho_pdf_atual,
                    self.pontos_calibracao,
                    self.certificado_te_atual,
                    self.pontos_calibracao_petro,
                    self.dados_report_atual
                )

                messagebox.showinfo("Sucesso", "Processo concluído com sucesso!")

                if dados_pdf.get("tag") and "TT" in dados_pdf.get("tag").upper():
                    self.certificado_te_atual = None

                self.dados_report_atual = None

            except Exception as e:
                messagebox.showerror("Erro", f"Erro na geração: {e}")
                import traceback
                traceback.print_exc()

            finally:
                self.exibir_resultado(dados_pdf, registro)


    def exibir_resultado(self, dados_pdf, registro):
        for w in self.result_frame.winfo_children():
            w.destroy()
        if not registro:
            return

        def linha(txt, ok):
            ctk.CTkLabel(
                self.result_frame,
                text=txt,
                text_color=ODS_OK if ok else ODS_ERROR,
                font=(FONT_FAMILY, 12, "bold")
            ).pack(anchor="w", pady=1)

        linha(f"N° CERTIFICADO: {normalizar_certificado(dados_pdf.get('certificado'))}", ok=True)
        tag_ok = dados_pdf["tag"] == registro["tag"]
        tag_text = f"TAG: {dados_pdf['tag']}"
        if not tag_ok:
            tag_text = f"TAG PDF: {dados_pdf['tag']} | TAG DB: {registro['tag']}"
        linha(tag_text, tag_ok)

        range_ok = (to_float_safe(dados_pdf.get("min_range")) == registro["min_range"] and
                    to_float_safe(dados_pdf.get("max_range")) == registro["max_range"])
        tag_text = f"RANGE CAL: {dados_pdf.get('min_range')} a {dados_pdf.get('max_range')}"
        if not range_ok:
            tag_text = f"RANGE CAL PDF: {dados_pdf.get('min_range')} a {dados_pdf.get('max_range')} | RANGE CAL DB: {registro['min_range']} a {registro['max_range']}"
        linha(tag_text, range_ok)

        
        if dados_pdf.get('inmin_range') != None and dados_pdf.get('inmax_range') != None:
            rangein_ok = (to_float_safe(dados_pdf.get("inmin_range")) <= to_float_safe(dados_pdf.get("min_range")) and
                    to_float_safe(dados_pdf.get("inmax_range")) >= to_float_safe(dados_pdf.get("max_range")))
        

            tag_text = f"RANGE CAL: {dados_pdf.get('min_range')} a {dados_pdf.get('max_range')} | RANGE IND.: {dados_pdf.get('inmin_range')} a {dados_pdf.get('inmax_range')}"
            if not rangein_ok:
                tag_text = f"RANGE CAL: {dados_pdf.get('min_range')} a {dados_pdf.get('max_range')} | RANGE IND.: {dados_pdf.get('inmin_range')} a {dados_pdf.get('inmax_range')}"
            linha(tag_text, rangein_ok)

        sn_pdf = dados_pdf.get("sn_instrumento")
        sn_db = registro.get("sn_instrumento")
        sn_ok = sn_pdf == sn_db
        sn_text = f"SN: {sn_pdf}"
        if not sn_ok:
            sn_text = f" SN PDF: {sn_pdf} | SN DB: {sn_db}"
        linha(sn_text, sn_ok)
        linha(f"DATA CALIBRAÇÃO: {dados_pdf.get('data')}", ok=True)
        linha(f"LOCAL: {dados_pdf.get('local')}", ok=True)
        linha(f"SISTEMA: {dados_pdf.get('sistema')}", ok=True)

        


    def abrir_consulta(self):
        win = ctk.CTkToplevel(self)
        win.title("Consulta de Instrumento")
        win.geometry("400x550")
        win.resizable(False, False)
        win.configure(fg_color=ODS_BG)
        win.grab_set()
        
        try:
            caminho_logo = _resource(os.path.join("logo", "ods-logo2.png"))
            if os.path.exists(caminho_logo):
                win.after(200, lambda: win.wm_iconphoto(False, self._load_icon_native(caminho_logo)))
        except: pass

        sub_h = ctk.CTkFrame(win, fg_color=ODS_RED, height=50, corner_radius=0)
        sub_h.pack(fill="x")
        ctk.CTkLabel(sub_h, text="EDITAR DADOS TÉCNICOS", text_color="white", font=(FONT_FAMILY, 14, "bold")).pack(expand=True)
        container = ctk.CTkFrame(win, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=20)

        tipo_atual = [None]
        campos = {
            "sn_instrumento": ctk.StringVar(),
            "sn_sensor":      ctk.StringVar(),
            "min_range":      ctk.StringVar(),
            "max_range":      ctk.StringVar(),
        }
        entries = {}

        # TAG
        ctk.CTkLabel(container, text="TAG do Instrumento", font=(FONT_FAMILY, 11, "bold")).pack(anchor="w")
        entry_tag = ctk.CTkEntry(container, width=340, height=35)
        entry_tag.pack(pady=(0, 15))

        # SN instrumento — sempre visível
        ctk.CTkLabel(container, text="Sn Instrumento", font=(FONT_FAMILY, 11)).pack(anchor="w")
        e_sn = ctk.CTkEntry(container, textvariable=campos["sn_instrumento"], state="readonly", width=340, height=32, fg_color=ODS_FRAME_LIGHT)
        e_sn.pack(pady=(0, 10))
        entries["sn_instrumento"] = e_sn

        # Campos exclusivos de instrumento secundário
        frame_sec = ctk.CTkFrame(container, fg_color="transparent")
        for k in ["sn_sensor", "min_range", "max_range"]:
            ctk.CTkLabel(frame_sec, text=k.replace("_", " ").title(), font=(FONT_FAMILY, 11)).pack(anchor="w")
            e = ctk.CTkEntry(frame_sec, textvariable=campos[k], state="readonly", width=340, height=32, fg_color=ODS_FRAME_LIGHT)
            e.pack(pady=(0, 10))
            entries[k] = e

        # Botão consultar — referência guardada para uso como âncora de pack
        btn_consultar = ctk.CTkButton(container, text="CONSULTAR", fg_color=ODS_DARK, height=35)
        btn_consultar.pack(fill="x", pady=5)
        btn_grid = ctk.CTkFrame(container, fg_color="transparent")
        btn_grid.pack(fill="x", pady=5)

        def consultar():
            tag = entry_tag.get().upper()
            reg = buscar_instrumento_por_tag(tag)
            if not reg:
                messagebox.showerror("Erro", "TAG não encontrada.")
                return
            tipo_atual[0] = reg.get("tipo", "SEC")
            campos["sn_instrumento"].set(reg.get("sn_instrumento") or "")
            if tipo_atual[0] == "PO":
                frame_sec.pack_forget()
            else:
                campos["sn_sensor"].set(reg.get("sn_sensor") or "")
                campos["min_range"].set("" if reg.get("min_range") is None else str(reg["min_range"]))
                campos["max_range"].set("" if reg.get("max_range") is None else str(reg["max_range"]))
                frame_sec.pack(fill="x", before=btn_consultar)

        def editar():
            entries["sn_instrumento"].configure(state="normal", fg_color="#FFFFFF")
            if tipo_atual[0] != "PO":
                for k in ["sn_sensor", "min_range", "max_range"]:
                    entries[k].configure(state="normal", fg_color="#FFFFFF")

        def salvar():
            tag = entry_tag.get().upper()
            if tipo_atual[0] == "PO":
                atualizar_sn_placa(tag, campos["sn_instrumento"].get())
            else:
                min_r = to_float_safe(campos["min_range"].get())
                max_r = to_float_safe(campos["max_range"].get())
                if min_r is None or max_r is None:
                    messagebox.showerror("Erro", "Ranges inválidos.")
                    return
                atualizar_sn(tag, campos["sn_instrumento"].get())
                atualizar_sn_sensor(tag, campos["sn_sensor"].get())
                atualizar_range(tag, min_r, max_r)
            messagebox.showinfo("Sucesso", "Dados salvos.")
            for e in entries.values():
                e.configure(state="readonly", fg_color=ODS_FRAME_LIGHT)

        btn_consultar.configure(command=consultar)
        ctk.CTkButton(btn_grid, text="EDITAR", fg_color=ODS_RED, command=editar, width=160, height=35).pack(side="left")
        ctk.CTkButton(btn_grid, text="SALVAR", fg_color=ODS_OK, command=salvar, width=160, height=35).pack(side="right")
        ctk.CTkButton(container, text="IMPORTAR XLSX", fg_color=ODS_DARK, command=self.abrir_importacao_xlsx, height=35).pack(fill="x", pady=(10, 0))

    def abrir_importacao_xlsx(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar planilha de instrumentos",
            filetypes=[("Excel", "*.xlsx")]
        )
        if not caminho:
            return

        try:
            resultado = ler_xlsx(caminho)
        except ValueError as e:
            messagebox.showerror("Erro na planilha", str(e))
            return

        # Se há divergentes, exibe modal para cada um
        sobrescrever = []
        pulados = []
        for item in resultado["divergente"]:
            resposta = messagebox.askyesno(
                "NS divergente",
                f"TAG: {item['tag']}\n\n"
                f"NS no banco : {item['sn_banco']}\n"
                f"NS no xlsx  : {item['sn']}\n\n"
                "Deseja sobrescrever o NS no banco?"
            )
            if resposta:
                sobrescrever.append(item)
            else:
                pulados.append(item)

        executar(resultado, sobrescrever)
        caminho_txt = gerar_relatorio(resultado, pulados, caminho)

        total_ins  = len(resultado["inserir"])
        total_sob  = len(sobrescrever)
        total_mant = len(resultado["mantido"])
        total_prob = len(resultado["bloqueado"]) + len(resultado["aviso"]) + len(pulados)

        msg = (
            f"Importação concluída.\n\n"
            f"Inseridos   : {total_ins}\n"
            f"Sobrescritos: {total_sob}\n"
            f"Mantidos    : {total_mant}\n"
            f"Problemas   : {total_prob}"
        )
        if caminho_txt:
            msg += f"\n\nRelatório gerado em:\n{caminho_txt}"

        messagebox.showinfo("Importação", msg)

