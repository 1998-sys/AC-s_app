import openpyxl
from openpyxl.styles import Alignment
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from datetime import datetime, timedelta
import win32com.client as win32
import os




def primeira_celula_merge(ws, cell):
    """
    Retorna a célula superior esquerda do merge,
    ou a própria célula se não estiver mesclada.
    """
    for merged_range in ws.merged_cells.ranges:
        if cell.coordinate in merged_range:
            return ws.cell(
                row=merged_range.min_row,
                column=merged_range.min_col
            )
    return cell


def escrever(ws, endereco, valor, wrap=True, vertical="top"):
    """
    Escreve valor em célula considerando merge automaticamente.
    """
    celula = primeira_celula_merge(ws, ws[endereco])
    celula.value = valor
    celula.alignment = Alignment(wrap_text=wrap, vertical=vertical)



def gerar_ac_origem(dados, caminho_pdf_original):
    def adicionar_dia_util(data):
        if data.weekday() == 5:  # sábado
            data += timedelta(days=2)
        elif data.weekday() == 6:  # domingo
            data += timedelta(days=1)
        return data
    
    
    caminho_template = "TemplateAC_ORIGEM.xlsx"
    wb = openpyxl.load_workbook(caminho_template)
    ws = wb["Template Formulário"]

   
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1

    ws.page_setup.horizontalCentered = True
    ws.page_setup.verticalCentered = True

    ws.page_margins.top = 0.5
    ws.page_margins.bottom = 0.5
    ws.page_margins.left = 0.8
    ws.page_margins.right = 0.5
   
    escrever(ws, "A6",  dados.get("tag"))
    escrever(ws, "C6",  dados.get("localizacao"))
    escrever(ws, "F6", f"SAP: {dados.get('sap', '')}")
    escrever(ws, "G6", f"CE: {dados.get('n_ac', '')}")
    escrever(ws, "A13", dados.get("certificado"))
    escrever(ws, "D13", dados.get("data"))
    

    
    categoria = (dados.get('categoria') or "").upper()
    sensor = (dados.get("sn_sensor") or "").upper()

    if categoria in (
        "TERMORRESISTÊNCIA PT-100 - 2 FIOS",
        "TERMORRESISTÊNCIA PT-100 - 3 FIOS",
        "TERMORRESISTÊNCIA PT-100 - 4 FIOS",
    ):
        escrever(ws, "F8", "[ ✔ ] Termorresistência (TE)")
        escrever(ws, "C8", "[ ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ ] Transmissor de temperatura (TT)")
        

    elif categoria in (
        "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA",
        "TERMÔMETRO ANALÓGICO",
        "TERMÔMETRO DIGITAL"
    ):
        
        escrever(ws, "C8", "[ ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ ✔ ] Transmissor de temperatura (TT)")

        if sensor:
            escrever(ws, "F8", "[ ✔ ] Termorresistência (TE)")
        else:
            escrever(ws, "F8", "[ ] Termorresistência (TE)")


    elif categoria in (
        "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA",
        "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA",
        "MANOMETRO DIGITAL",
        "MANOMETRO ANALÓGICO",
        "MANOMETRO DIGITAL ABSOLUTO",
    ):
        
        escrever(ws, "C8", "[ ✔ ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ ] Transmissor de temperatura (TT)")
        escrever(ws, "F8", "[ ] Termorresistência (TE)")

        

    elif categoria in (
        "MANOMETRO DIFERENCIAL DIGITAL",
        "MANOMETRO DIFERENCIAL ANALÓGICO",
    ):
        escrever(ws, "C8", "[ ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ ✔ ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ ] Transmissor de temperatura (TT)")
        escrever(ws, "F8", "[ ] Termorresistência (TE)")

        

  
    if dados.get("report_date"):
        dt = datetime.strptime(dados["report_date"], "%d/%m/%Y")
        dt_util = adicionar_dia_util(dt)
        texto_data = f"Data: {dt_util.strftime('%d/%m/%Y')}"
        escrever(
            ws,
            "D45",
            texto_data,
            wrap=False,
            vertical="center"
        )

   
    blocos = []

    if dados.get("range_atualizado"):
        blocos.append(
            TextBlock(
                text="Novo range e alarmes alterados no computador de vazão\n",
                font=InlineFont(b=True)
            )
        )

    elif dados.get("sn_atualizado"):
        blocos.append(
            TextBlock(
                text="Novo NS alterado no computador de vazão / XML / SFP\n",
                font=InlineFont(b=True)
            )
        )

    rich = CellRichText(*blocos) if blocos else ""
    escrever(ws, "A42", rich)

    
    wb.save(caminho_template)

    
    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    certificado = dados.get("certificado", "").replace(" ", "")
    tag_limpa = dados.get("tag", "").replace(" ", "")
    nome_pdf = f"{certificado}_{tag_limpa}_AC.pdf"
    caminho_pdf_final = os.path.join(pasta_saida, nome_pdf)

    if os.path.exists(caminho_pdf_final):
        os.remove(caminho_pdf_final)

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        wb_excel = excel.Workbooks.Open(os.path.abspath(caminho_template))
        wb_excel.ExportAsFixedFormat(0, caminho_pdf_final)
        wb_excel.Close(False)
    finally:
        excel.Quit()

    return caminho_pdf_final

