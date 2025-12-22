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
    buscar_por_sn_instrumento,
    atualizar_sn,
    atualizar_sn_sensor,
    atualizar_range
)

from form.utils_print import gerar_ac

from validation.engine import ValidationEngine
from validation.context import ValidationContext




def extrair_tag_base(tag: str) -> str:
    """
    Docstring for extrair_tag_base MVS
    
    :param tag: Description
    :type tag: str
    :return: Description
    :rtype: str
    """
    if "-" not in tag:
        return tag
    partes = tag.split("-")
    return "-".join(partes[:-1])



class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Análise Crítica de Certificados")
        self.root.geometry("600x420")
        self.root.resizable(False, False)

        self.btn_selecionar = tk.Button(
            root,
            text="Selecionar Certificado PDF",
            command=self.selecionar_pdf,
            width=30,
            height=2
        )
        self.btn_selecionar.pack(pady=15)

        self.btn_consultar = tk.Button(
            root,
            text="Consultar / Atualizar Dados",
            command=self.abrir_consulta,
            width=30
        )
        self.btn_consultar.pack(pady=5)

        self.lbl_pdf = tk.Label(root, text="Nenhum PDF selecionado.")
        self.lbl_pdf.pack(pady=10)

        self.result_frame = tk.Frame(root)
        self.result_frame.pack(pady=10)


   
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
            print(dados_pdf)

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


   
    def processar_comparacao(self, dados_pdf, caminho_pdf_original):
        """Processa a comparação entre os dados do PDF e os registros no banco."""
        tag_pdf = dados_pdf["tag"]
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
                    f"{issue.message}\n\nDeseja aplicar a correção?"
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


    def exibir_resultado(self, dados_pdf, registro):
        """Exibe o resultado da comparação na interface."""
        for w in self.result_frame.winfo_children():
            w.destroy()

        def add(text, ok):
            tk.Label(
                self.result_frame,
                text=text,
                fg="green" if ok else "red"
            ).pack(anchor="w")

        add(f"TAG: {dados_pdf['tag']} | {registro['tag']}",
            dados_pdf["tag"] == registro["tag"])

        add(f"SN Instrumento: {dados_pdf.get('sn_instrumento')} | {registro['sn_instrumento']}",
            dados_pdf.get("sn_instrumento") == registro["sn_instrumento"])

        if dados_pdf.get("sn_sensor"):
            add(f"SN Sensor: {dados_pdf['sn_sensor']} | {registro['sn_sensor']}",
                dados_pdf["sn_sensor"] == registro["sn_sensor"])


    
    def abrir_consulta(self):
        """Abre a janela de consulta e atualização de dados."""
        win = tk.Toplevel(self.root)
        win.title("Consultar / Atualizar Dados")
        win.geometry("420x360")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="TAG").pack(pady=(10, 0))
        entry_tag = tk.Entry(win, width=30)
        entry_tag.pack()

        campos = {
            "sn_instrumento": tk.StringVar(),
            "sn_sensor": tk.StringVar(),
            "min_range": tk.StringVar(),
            "max_range": tk.StringVar()
        }

        entries = {}

        for nome, var in campos.items():
            tk.Label(win, text=nome.replace("_", " ").title()).pack(pady=(8, 0))
            e = tk.Entry(win, textvariable=var, state="readonly", width=30)
            e.pack()
            entries[nome] = e

        def consultar():
            tag = entry_tag.get().strip().upper()
            registro = buscar_instrumento_por_tag(tag)

            if not registro:
                messagebox.showerror("Erro", "TAG não encontrada")
                return

            campos["sn_instrumento"].set(registro["sn_instrumento"])
            campos["sn_sensor"].set(registro["sn_sensor"])
            campos["min_range"].set(registro["min_range"])
            campos["max_range"].set(registro["max_range"])

        def editar():
            for e in entries.values():
                e.config(state="normal")

        def salvar():
            try:
                atualizar_sn(entry_tag.get(), campos["sn_instrumento"].get())
                atualizar_sn_sensor(entry_tag.get(), campos["sn_sensor"].get())
                atualizar_range(
                    entry_tag.get(),
                    float(campos["min_range"].get()),
                    float(campos["max_range"].get())
                )
            except ValueError:
                messagebox.showerror("Erro", "Range deve ser numérico")
                return

            messagebox.showinfo("Sucesso", "Dados atualizados")

            for e in entries.values():
                e.config(state="readonly")

        tk.Button(win, text="Consultar", command=consultar).pack(pady=5)
        tk.Button(win, text="Editar", command=editar).pack(pady=5)
        tk.Button(win, text="Salvar", command=salvar).pack(pady=10)