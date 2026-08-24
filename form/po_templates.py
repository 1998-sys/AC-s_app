import openpyxl
import os
import re
import shutil
import tempfile
import time
import uuid
import win32com.client as win32


def limpar_nome_arquivo(texto):
    """
    Remove caracteres inválidos para nomes de arquivo e substitui espaços por underscores.
    Removes invalid filename characters and replaces spaces with underscores.
    """
    if not texto:
        return ""

    texto = re.sub(r'[\\/*?:"<>|]', "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto.strip()


def gerar_ac_po(config, dados, caminho_pdf_original):
    """Preenche um template Excel de AC de placa de orifício (variante PO) e
    exporta como PDF via Excel COM.

    ORIGEM_PO, YINSON_PO e YINSON_ATLANTA_PO usam exatamente este mesmo fluxo —
    copiar o template para um arquivo temporário, escrever um punhado de campos,
    abrir via Excel COM pra recalcular fórmulas e exportar o PDF — diferindo
    apenas no template usado e em quais campos vão em quais células (`config`).

    Args:
        config (dict): 'template', 'prefixo_temp', 'campos' (cel -> chave em
            `dados`), 'data_cell' (célula do "Data: {report_date}"),
            'nome_arquivo_campo' (chave em `dados` usada no nome do PDF final).
        dados (dict): Campos do certificado.
        caminho_pdf_original (str): Caminho do PDF de origem, usado para
            definir a pasta de saída.

    Returns:
        str: Caminho absoluto do PDF gerado.

    Raises:
        PermissionError: Se o PDF de saída já estiver aberto.
    """
    caminho_template = config["template"]

    caminho_temp = os.path.join(
        tempfile.gettempdir(),
        f"{config['prefixo_temp']}{uuid.uuid4().hex}.xlsx"
    )
    shutil.copy(caminho_template, caminho_temp)

    wb = openpyxl.load_workbook(caminho_temp)
    ws = wb["Template Formulário"]

    for celula, campo in config["campos"].items():
        ws[celula] = dados.get(campo)

    ws[config["data_cell"]] = f'Data: {dados.get("report_date")}'

    wb.save(caminho_temp)
    wb.close()

    time.sleep(1)
    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))

    nome_base = limpar_nome_arquivo(dados.get(config["nome_arquivo_campo"], ""))
    nome_pdf = f"{nome_base}_AC.pdf"
    caminho_pdf_final = os.path.join(pasta_saida, nome_pdf)

    if os.path.exists(caminho_pdf_final):
        try:
            os.remove(caminho_pdf_final)
        except PermissionError:
            raise PermissionError(
                f"⚠ O PDF está aberto:\n{caminho_pdf_final}"
            )

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        wb_excel = excel.Workbooks.Open(os.path.abspath(caminho_temp))

        time.sleep(1)

        excel.Calculate()
        wb_excel.ExportAsFixedFormat(
            0,
            os.path.abspath(caminho_pdf_final)
        )

        wb_excel.Close(False)

    finally:
        excel.Quit()
        if os.path.exists(caminho_temp):
            try:
                os.remove(caminho_temp)
            except Exception:
                pass

    return caminho_pdf_final


CONFIG_ORIGEM_PO = {
    "template": "TemplateAC_PO_ORIGEM.xlsx",
    "prefixo_temp": "temp_ac_origem_",
    "campos": {
        "A6": "sn_inst",
        "A13": "certificado",
        "D13": "data_calibracao",
        "C6": "localizacao",
        "F6": "n_ac",
    },
    "data_cell": "D57",
    "nome_arquivo_campo": "n_ac",
}

CONFIG_YINSON_PO = {
    "template": "TemplateAC_PO_YINSON.xlsx",
    "prefixo_temp": "temp_ac_yinson_",
    "campos": {
        "A13": "certificado",
        "D13": "data_calibracao",
        "C6": "local",
        "F6": "sn_inst",
    },
    "data_cell": "D56",
    "nome_arquivo_campo": "certificado",
}

CONFIG_YINSON_ATLANTA_PO = {
    "template": "TemplateAC_PO_YINSON - ATLANTA.xlsx",
    "prefixo_temp": "temp_ac_yinson_atlanta_",
    "campos": {
        "A13": "certificado",
        "D13": "data_calibracao",
        "C6": "local",
        "F6": "sn_inst",
    },
    "data_cell": "D56",
    "nome_arquivo_campo": "certificado",
}


def gerar_ac_origem_PO(dados, caminho_pdf_original):
    """Preenche o template Excel de AC Origem PO e exporta como PDF via Excel COM."""
    return gerar_ac_po(CONFIG_ORIGEM_PO, dados, caminho_pdf_original)


def gerar_ac_yinson_PO(dados, caminho_pdf_original):
    """Preenche o template Excel de AC YINSON PO e exporta como PDF via Excel COM."""
    return gerar_ac_po(CONFIG_YINSON_PO, dados, caminho_pdf_original)


def gerar_ac_yinson_atlanta_PO(dados, caminho_pdf_original):
    """Preenche o template Excel de AC YINSON ATLANTA PO e exporta como PDF via Excel COM."""
    return gerar_ac_po(CONFIG_YINSON_ATLANTA_PO, dados, caminho_pdf_original)
