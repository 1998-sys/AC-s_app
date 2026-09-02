# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ORIGEM
# Created       : 02-01-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Fills the AC ORIGEM Excel template and exports it to PDF via Excel COM automation.
#                 Preenche o template Excel de AC ORIGEM e o exporta para PDF via automação COM do Excel.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import openpyxl
from openpyxl.styles import Alignment
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from datetime import datetime, timedelta
import win32com.client as win32
import os
import shutil
import tempfile
import uuid


def primeira_celula_merge(ws, cell):
    """Resolves the top-left cell of a merged range.

    Necessary because openpyxl only accepts writes to the first cell of a
    merged range.

    Args:
        ws: openpyxl worksheet.
        cell: Cell to resolve.

    Returns:
        The top-left cell of the merge that contains `cell`, or `cell`
        itself if it does not belong to any merge.
    """
    for merged_range in ws.merged_cells.ranges:
        if cell.coordinate in merged_range:
            return ws.cell(
                row=merged_range.min_row,
                column=merged_range.min_col
            )
    return cell


def escrever(ws, endereco, valor, wrap=True, vertical="top"):
    """Writes `valor` into the cell (or merge) at the given address, with default alignment.

    Args:
        ws: openpyxl worksheet.
        endereco: Cell address (e.g. "A6").
        valor: Value to write.
        wrap: If True, enables automatic text wrapping in the cell.
        vertical: Vertical alignment of the text.
    """
    celula = primeira_celula_merge(ws, ws[endereco])
    celula.value = valor
    celula.alignment = Alignment(wrap_text=wrap, vertical=vertical)


def gerar_ac_origem(dados, caminho_pdf_original, dados_xml_petro, excel=None):
    """Fills the AC ORIGEM template and exports it as PDF via Excel COM.

    Marks the instrument-type checkboxes, adjusts the delivery date to the
    next business day, indicates AS FOUND/AS LEFT and assembles the
    observations as rich text (updated range/SN or no change).

    Args:
        dados: Certificate fields.
        caminho_pdf_original: Path of the source PDF, used to determine the
            output folder.
        dados_xml_petro: Petrobras XML data; used to determine whether the
            calibration is AS LEFT (otherwise assumes AS FOUND).
        excel: Already-open Excel COM instance (reused across a batch). If
            None, opens and closes its own instance.

    Returns:
        str: Absolute path of the generated PDF.
    """
    def adicionar_dia_util(data):
        """Adjusts `data` to the next business day, moving forward 2 days if it falls on a Saturday or 1 day if it falls on a Sunday.

        Args:
            data: Date to adjust.

        Returns:
            datetime: `data` unchanged if it is already a business day, or
            pushed forward to the following Monday if it falls on a
            Saturday/Sunday.
        """
        if data.weekday() == 5:  # sábado
            data += timedelta(days=2)
        elif data.weekday() == 6:  # domingo
            data += timedelta(days=1)
        return data

    print(dados)

    caminho_template = "TemplateAC_ORIGEM.xlsx"
    caminho_temp = os.path.join(
        tempfile.gettempdir(),
        f"temp_ac_origem_{uuid.uuid4().hex}.xlsx"
    )
    shutil.copy(caminho_template, caminho_temp)

    wb = openpyxl.load_workbook(caminho_temp)
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
    # F6 (SAP) não é mais preenchido — o campo foi removido do fluxo (ver
    # processors/utils.py::fluxo_origem). Mantém o que já estiver no
    # template pronto; TODO conferir se a célula fica com aparência
    # estranha em branco e, se sim, limpar o rótulo direto no template.
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
        "TRANSMISSOR DE TEMPERATURA",
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
        max_range = dados.get("max_range")
        try:
            max_range_float = float(max_range)
        except (TypeError, ValueError):
            max_range_float = None

        if categoria == "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA" and max_range_float is not None and max_range_float <= 250:
            escrever(ws, "C8", "[ ] Transmissor de pressão estática (PT)")
            escrever(ws, "C9", "[ ✔ ] Transmissor de pressão diferencial (PDT)")
        else:
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

    elif dados_xml_petro and dados_xml_petro.get("tabela2") == "AS LEFT":
            escrever(ws, "F35", "◉", vertical="center")
            ws["F35"].alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            escrever(ws, "H35", "○", vertical="center")
            ws["H35"].alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    else:
            escrever(ws, "H35", "◉", vertical="center")
            ws["H35"].alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            escrever(ws, "F35", "○", vertical="center")
            ws["F35"].alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")

    rich = CellRichText(*blocos) if blocos else ""
    escrever(ws, "A42", rich)

    wb.save(caminho_temp)
    wb.close()

    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    n_ac = dados.get("n_ac", "").replace(" ", "")
    nome_pdf = f"{n_ac}_AC.pdf"
    caminho_pdf_final = os.path.join(pasta_saida, nome_pdf)

    if os.path.exists(caminho_pdf_final):
        os.remove(caminho_pdf_final)

    excel_proprio = excel is None
    if excel_proprio:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

    try:
        wb_excel = excel.Workbooks.Open(os.path.abspath(caminho_temp))
        wb_excel.ExportAsFixedFormat(0, caminho_pdf_final)
        wb_excel.Close(False)
    finally:
        if excel_proprio:
            excel.Quit()
        if os.path.exists(caminho_temp):
            try:
                os.remove(caminho_temp)
            except Exception:
                pass

    return caminho_pdf_final
