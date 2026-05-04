import openpyxl
import os
import win32com.client as win32
import tempfile
import shutil
import uuid
import time
import re


def limpar_nome_arquivo(texto):
    """
    Remove caracteres inválidos para nomes de arquivo e substitui espaços por underscores.
    Removes invalid filename characters and replaces spaces with underscores.

    Args:
        texto (str): Nome original / Original name.

    Returns:
        str: Nome sanitizado / Sanitized name.
    """
    if not texto:
        return ""

    texto = re.sub(r'[\\/*?:"<>|]', "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto.strip()


def gerar_ac_yinson_PO(dados, caminho_pdf_original):
    """
    Preenche o template Excel de AC YINSON PO com os dados fornecidos e exporta como PDF.
    Fills the AC YINSON PO Excel template with the provided data and exports it as PDF.

    O processo cria uma cópia temporária do template, preenche as células com os dados
    do certificado, abre via Excel COM para forçar o recálculo de fórmulas e exporta
    o PDF na mesma pasta do arquivo PDF original.

    The process creates a temporary copy of the template, fills the cells with certificate
    data, opens it via Excel COM to force formula recalculation, and exports the PDF
    to the same folder as the original PDF file.

    Args:
        dados               (dict): Dicionário com os campos do certificado / Dictionary with certificate fields.
            - sn_inst       (str):  Número de série do instrumento / Instrument serial number.
            - certificado   (str):  Número do certificado / Certificate number.
            - data_calibracao(str): Data da calibração / Calibration date.
            - report_date   (str):  Data do relatório / Report date.
            - localizacao   (str):  Localização do instrumento / Instrument location.
            - n_ac          (str):  Número da AC / AC number.
        caminho_pdf_original(str):  Caminho do PDF de origem, usado para definir a pasta de saída.
                                    Path of the source PDF, used to define the output folder.

    Returns:
        str: Caminho absoluto do PDF gerado / Absolute path of the generated PDF.

    Raises:
        PermissionError: Se o PDF de saída já estiver aberto / If the output PDF is already open.
    """
    caminho_template = "TemplateAC_PO_YINSON.xlsx"

    print(dados)

    temp_dir = tempfile.gettempdir()
    caminho_temp = os.path.join(
        temp_dir,
        f"temp_ac_yinson_{uuid.uuid4().hex}.xlsx"
    )

    shutil.copy(caminho_template, caminho_temp)

    wb = openpyxl.load_workbook(caminho_temp)
    ws = wb["Template Formulário"]

    
    ws["A13"] = dados.get("certificado")
    ws["D13"] = dados.get("data_calibracao")
    ws["D56"] = f'Data: {dados.get("report_date")}'
    ws["C6"] = dados.get("local")
    ws["F6"] = dados.get('sn_inst')

    wb.save(caminho_temp)
    wb.close()

    time.sleep(1)
    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))

    n_ac = limpar_nome_arquivo(dados.get("certificado", ""))

    nome_pdf = f"{n_ac}_AC.pdf"
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
