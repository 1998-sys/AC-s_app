import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys


sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos

from data.utils_db import (
    buscar_instrumento_por_tag,
    inserir_instrumento,
    atualizar_sn,
    atualizar_sn_sensor,
    buscar_por_sn_instrumento,
    buscar_por_sn_sensor,
    atualizar_tag
)
from form.utils_print import gerar_ac

def extrair_tag_base(tag: str) -> str:
    """
    Remove apenas o último sufixo após o último '-'.
    FIT-1231010T-DPT → FIT-1231010T
    FIT-1231010T-TT  → FIT-1231010T
    """
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


    def selecionar_pdf(self):
        caminho_pdf = filedialog.askopenfilename(
            title="Selecione o certificado PDF",
            filetypes=[("Arquivos PDF", "*.pdf")]
        )

        if not caminho_pdf:
            return

        self.lbl_pdf.config(text=f"PDF selecionado: {os.path.basename(caminho_pdf)}")

        try:
            texto = extrair_texto(caminho_pdf)
            dados_pdf = extrair_campos(texto)
            print(dados_pdf)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao ler PDF:\n{e}")
            return

        self.processar_comparacao(dados_pdf, caminho_pdf)


    
    def processar_comparacao(self, dados_pdf, caminho_pdf_original):

        tag_pdf = dados_pdf["tag"]
        sn_pdf = dados_pdf.get("sn_instrumento")
        sns_pdf = dados_pdf.get("sn_sensor")
        range_min = dados_pdf.get("min_range")
        range_max = dados_pdf.get("max_range")

        dados_ok = True

        registro = buscar_instrumento_por_tag(tag_pdf)
        reg_sn = buscar_por_sn_instrumento(sn_pdf) if sn_pdf else None

        tag_base_pdf = extrair_tag_base(tag_pdf)
        tag_base_sn = extrair_tag_base(reg_sn["tag"]) if reg_sn else None


        mvs=False
        # Tag não encontrada, mas o SN existe -> verifica se é MVS (NS mesmo, Tag mesma base)
        if registro is None and reg_sn is not None:
        
            if tag_base_pdf == tag_base_sn:
                registro = reg_sn
                messagebox.showinfo(
                    "TAG compatível (Família MVS)",
                    f"O NS {sn_pdf} pertence a outro modelo da mesma família.\n\n"
                    f"TAG no banco: {reg_sn['tag']}\n"
                    f"TAG no certificado: {tag_pdf}\n"
                    f"Base comum: {tag_base_pdf}\n\n"
                    "Continuando o processo normalmente."
                )
                inserir_instrumento(tag_pdf, sn_pdf, sns_pdf, range_min, range_max)
                mvs = True
            else:
                
                resposta = messagebox.askyesno(
                    "TAG divergente",
                    f"O NS '{sn_pdf}' já está cadastrado com outra TAG:\n"
                    f"TAG no banco: {reg_sn['tag']}\n"
                    f"TAG no certificado: {tag_pdf}\n\n"
                    "Deseja atualizar a TAG desse instrumento?"
                )

                if resposta:
                    atualizar_tag(sn_pdf, tag_pdf)
                    registro = buscar_instrumento_por_tag(tag_pdf)
                    messagebox.showinfo("Atualizado", "TAG atualizada com sucesso.")
                else:
                    messagebox.showwarning("Cancelado", "Operação cancelada. AC não será gerada.")
                    return


        # Caso 2 - Tag não existe e SN também não → novo instrumento
        if registro is None and reg_sn is None:
            resposta = messagebox.askyesno(
                "TAG não encontrada",
                f"A TAG '{tag_pdf}' não existe no banco.\n\n"
                f"NS Instrumento: {sn_pdf}\n"
                f"NS Sensor: {sns_pdf}\n\n"
                "Deseja adicionar como novo instrumento?"
            )

            if resposta:
                inserir_instrumento(tag_pdf, sn_pdf, sns_pdf, range_min, range_max)
                registro = buscar_instrumento_por_tag(tag_pdf)
                messagebox.showinfo("Inserido", "Instrumento adicionado ao banco.")
            else:
                messagebox.showwarning("Cancelado", "Processo encerrado.")
                return

        # Caso 3 - SN do instrumento divergente
        sn_banco = registro["sn_instrumento"]
        sns_banco = registro["sn_sensor"]
        tag_banco = registro["tag"]

        if sns_pdf:

            # Se for MVS recém-criado → não comparar com registro antigo
            if mvs and not sn_banco:
                registro["sn_sensor"] = sns_pdf
                
            else:
                if sns_pdf != sn_banco:
                    resposta = messagebox.askyesno(
                        "Divergência no SN do Sensor",
                        f"O SN do sensor da TAG {tag_pdf} difere:\n"
                        f"PDF: {sns_pdf}\nBanco: {sn_banco}\n\n"
                        "Deseja atualizar o banco?"
                    )

                    if resposta:
                        atualizar_sn_sensor(tag_pdf, sns_pdf)
                        registro["sn_sensor"] = sns_pdf
                        dados_pdf["sn_atualizado"] = True
                    else:
                        dados_ok = False
        
        # Divergencia do Range
        min_pdf = dados_pdf.get("min_range")
        max_pdf = dados_pdf.get("max_range")

        min_banco = registro.get("min_range")
        max_banco = registro.get("max_range")

        try:
            min_pdf_f = float(min_pdf)
            max_pdf_f = float(max_pdf)
            min_banco_f = float(min_banco)
            max_banco_f = float(max_banco)
        except Exception:
            # fallback em caso de valores inesperados
            min_pdf_f = min_pdf
            max_pdf_f = max_pdf
            min_banco_f = min_banco
            max_banco_f = max_banco

        print(min_banco_f, min_banco_f)
        if not mvs and min_pdf is not None and max_pdf is not None:
            range_diferente = ((min_pdf_f) != (min_banco_f)) or ((max_pdf_f) != (max_banco_f))
            
            if range_diferente:
                resposta = messagebox.askyesno(
                    "Divergência no RANGE do Instrumento",
                    f"O RANGE do instrumento {tag_pdf} difere do registrado no banco.\n\n"
                    f"PDF: {min_pdf} → {max_pdf}\n"
                    f"Banco: {min_banco} → {max_banco}\n\n"
                    f"Deseja atualizar o banco e continuar?"
                )
                if resposta:
                    try:
                        from data.utils_db import atualizar_range
                        atualizar_range(tag_banco, min_pdf, max_pdf)

                        # Atualiza registro em memória
                        registro["min_range"] = min_pdf
                        registro["max_range"] = max_pdf

                        dados_pdf["range_atualizado"] = True

                        messagebox.showinfo(
                            "Range atualizado",
                            f"O range do instrumento {tag_pdf} foi atualizado com sucesso."
                        )

                    except Exception as e:
                        messagebox.showerror("Erro ao atualizar RANGE", str(e))
                        dados_ok = False

                else:
                    messagebox.showwarning(
                        "AC NÃO GERADA",
                        "O usuário optou por não atualizar o RANGE.\n"
                        "A Análise Crítica não será gerada.",
                        "XML não gerado"
                    )
                    return

        


        
        # Exibir resultados
        self.exibir_resultado(dados_pdf, registro)


        
        #Gerar AC e XML
        if dados_ok:
            caminho_pdf_final, tipo = gerar_ac(dados_pdf, caminho_pdf_original)
            #gerar_xml(dados_pdf, tipo, caminho_pdf_final)

            messagebox.showinfo(
                "AC Gerada",
                f"Análise Crítica gerada com sucesso!\n\n"
                f"Arquivo salvo em:\n{caminho_pdf_final}"
            )
        else:
            messagebox.showwarning(
                "AC NÃO GERADA",
                "A Análise Crítica não foi gerada devido a divergências pendentes."
            )


    
    #Exibir diferenças na tela
    def exibir_resultado(self, dados_pdf, registro):
        for w in self.result_frame.winfo_children():
            w.destroy()

        def add(text, ok):
            tk.Label(
                self.result_frame,
                text=text,
                fg="green" if ok else "red",
                font=("Arial", 12, "bold" if not ok else "normal")
            ).pack()

        add(f"TAG → PDF: {dados_pdf['tag']} | Banco: {registro['tag']}",
            dados_pdf["tag"] == registro["tag"])

        add(f"NS Instrumento → PDF: {dados_pdf['sn_instrumento']} | Banco: {registro['sn_instrumento']}",
            dados_pdf["sn_instrumento"] == registro["sn_instrumento"])

        if dados_pdf.get("sn_sensor"):
            add(f"NS Sensor → PDF: {dados_pdf['sn_sensor']} | Banco: {registro['sn_sensor']}",
                dados_pdf["sn_sensor"] == registro["sn_sensor"])


