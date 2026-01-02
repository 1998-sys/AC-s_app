import openpyxl
from openpyxl.styles import Alignment
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from datetime import datetime, timedelta
import win32com.client as win32
import os


# ==========================================================
# FUNÇÕES AUXILIARES – MERGE SAFE
# ==========================================================

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


# ==========================================================
# FUNÇÃO PRINCIPAL – AC ORIGEM
# ==========================================================

def gerar_ac_origem(dados, caminho_pdf_original):

    def adicionar_dia_util(data):
        data += timedelta(days=1)
        if data.weekday() == 5:  # sábado
            data += timedelta(days=2)
        elif data.weekday() == 6:  # domingo
            data += timedelta(days=1)
        return data

    caminho_template = "TemplateAC_ORIGEM.xlsx"
    wb = openpyxl.load_workbook(caminho_template)
    ws = wb["Template Formulário"]

    # =============================
    # CONFIGURAÇÃO DE PÁGINA
    # =============================
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.orientation = "portrait"
    ws.page_margins.top = 0.3
    ws.page_margins.bottom = 0.3
    ws.page_margins.left = 0.3
    ws.page_margins.right = 0.3

    # =============================
    # DADOS BÁSICOS
    # =============================
    escrever(ws, "A6",  dados.get("tag"))
    escrever(ws, "A13", dados.get("certificado"))
    escrever(ws, "D13", dados.get("data"))

    # =============================
    # IDENTIFICAÇÃO DO TIPO
    # =============================
    tipo = ""
    tag = (dados.get("tag") or "").upper()

    if (
        tag.startswith("TE") or
        tag.endswith("-TE") or
        "-TE-" in tag
    ):
        escrever(ws, "F8", "[ X ] Termorresistência (TE)")
        escrever(ws, "C8", "[ ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ ] Transmissor de temperatura (TT)")
        tipo = "TE"

    elif (
        tag.startswith(("TT", "TIT", "TI")) or
        tag.endswith(("-TT", "-TIT", "-TI")) or
        any(x in tag for x in ("-TT-", "-TIT-", "-TI-"))
    ):
        escrever(ws, "C8", "[ ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ X ] Transmissor de temperatura (TT)")
        escrever(ws, "F8", "[ ] Termorresistência (TE)")
        tipo = "TT"

    elif (
        tag.startswith(("PT", "PIT")) or
        tag.endswith(("-PT", "-PIT")) or
        any(x in tag for x in ("-PT-", "-PIT-"))
    ):
        escrever(ws, "C8", "[ X ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ ] Transmissor de temperatura (TT)")
        escrever(ws, "F8", "[ ] Termorresistência (TE)")

        tipo = "PT"

    else:
        escrever(ws, "C8", "[ ] Transmissor de pressão estática (PT)")
        escrever(ws, "C9", "[ X ] Transmissor de pressão diferencial (PDT)")
        escrever(ws, "C10", "[ ] Transmissor de temperatura (TT)")
        escrever(ws, "F8", "[ ] Termorresistência (TE)")

        tipo = "DPT"

    # =============================
    # REPORT DATE (+1 dia útil)
    # =============================
    if dados.get("report_date"):
        dt = datetime.strptime(dados["report_date"], "%d/%m/%Y")
        dt_util = adicionar_dia_util(dt)
        texto_data = f"Data: {dt_util.strftime('%d/%m/%Y')}"
        escrever(
            ws,
            "H45",
            texto_data,
            wrap=False,
            vertical="center"
        )

    # =============================
    # OBSERVAÇÕES – RICH TEXT
    # =============================
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

    # =============================
    # SALVAR TEMPLATE
    # =============================
    wb.save(caminho_template)

    # =============================
    # EXPORTAR PARA PDF
    # =============================
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

    return caminho_pdf_final, tipo

