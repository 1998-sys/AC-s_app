import openpyxl
import win32com.client as win32
import os
import re
from datetime import datetime
from openpyxl.utils import get_column_letter
from openpyxl.styles import Border, Side
from openpyxl.worksheet.page import PageMargins


def gerar_ac_prio_po(
    dados: dict,
    caminho_pdf_original,
    caminho_template = "TemplateAC_PRIO.xlsx",
    nome_aba = "Template Formulário",
    print_area_fixa: str | None = None,
    linhas_extra_topo: int = 2,
    aplicar_borda_fallback: bool = True,
    cor_faixa_teal_hex = "0099A8"
):

    if not os.path.isfile(caminho_template):
        raise FileNotFoundError(f"Template não encontrado: {os.path.abspath(caminho_template)}")

    wb = openpyxl.load_workbook(caminho_template)

    if nome_aba not in wb.sheetnames:
        raise KeyError(f"Aba '{nome_aba}' não encontrada.")

    ws = wb[nome_aba]

    ws["C5"] = dados.get("local", "")
    ws["C6"] = dados.get("local", "")
    ws["C7"] = dados.get("data_calibracao", "")
    ws["F5"] = dados.get("sn_inst", "")
    ws["F6"] = dados.get("certificado", "")
    ws["F7"] = "ODS Metering Systems"

    ws["G48"] = datetime.now().strftime("%d/%m/%Y")

    if aplicar_borda_fallback:

        titulo = "Análise crítica de calibração de placas de orifício"
        titulo_row = None
        max_col = 1

        for row in ws.iter_rows(min_row=1, max_row=30):

            for cell in row:

                if cell.value not in (None, ""):
                    max_col = max(max_col, cell.column)

                    if isinstance(cell.value, str) and titulo.lower() in cell.value.lower():
                        titulo_row = cell.row

        if titulo_row:

            linha_borda = titulo_row + 1
            teal = cor_faixa_teal_hex.upper()

            border = Border(bottom=Side(style="thick", color=teal))

            for c in range(1, max_col + 1):

                addr = f"{get_column_letter(c)}{linha_borda}"
                ws[addr].border = ws[addr].border + border

    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1

    ws.print_options.horizontalCentered = True

    ws.page_margins = PageMargins(
        top=0.3,
        bottom=0.3,
        left=0.3,
        right=0.3
    )

    if print_area_fixa is None:

        last_row = 1
        last_col = 1

        for row in ws.iter_rows():

            for cell in row:

                if cell.value not in (None, ""):

                    last_row = max(last_row, cell.row)
                    last_col = max(last_col, cell.column)

        last_row += linhas_extra_topo

        ws.print_area = f"A1:{get_column_letter(last_col)}{last_row}"

    else:

        ws.print_area = print_area_fixa


    wb.save(caminho_template)
    wb.close()

    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))

    def sanitize(txt):
        return re.sub(r'[<>:"/\\|?*]+', "-", str(txt or "")).strip()

    certificado = sanitize(dados.get("certificado")).replace(" ", "")
    tag = sanitize(dados.get("tag")).replace(" ", "")

    nome_pdf = f"{certificado}_{tag}_AC.pdf".strip("_")
    pdf_final = os.path.join(pasta_saida, nome_pdf)

    if os.path.exists(pdf_final):
        os.remove(pdf_final)


    excel = None
    wb_excel = None

    try:

        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        wb_excel = excel.Workbooks.Open(os.path.abspath(caminho_template))
        ws_excel = wb_excel.Worksheets(nome_aba)

        ps = ws_excel.PageSetup

        ps.Zoom = False
        ps.FitToPagesWide = 1
        ps.FitToPagesTall = 1

        ps.LeftMargin = excel.InchesToPoints(0.3)
        ps.RightMargin = excel.InchesToPoints(0.3)
        ps.TopMargin = excel.InchesToPoints(0.3)
        ps.BottomMargin = excel.InchesToPoints(0.3)

        ps.CenterHorizontally = True


        wb_excel.ExportAsFixedFormat(
            Type=0,
            Filename=pdf_final,
            Quality=0,
            IncludeDocProperties=True,
            IgnorePrintAreas=False,
            OpenAfterPublish=False
        )

    finally:

        try:
            if wb_excel:
                wb_excel.Close(SaveChanges=False)
        except:
            pass

        try:
            if excel:
                excel.Quit()
        except:
            pass

    return pdf_final