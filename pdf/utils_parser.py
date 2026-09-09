# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.utils_parser
# Created       : 23-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Identifies the certificate/report type from its extracted text and routes it to the matching parser.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos
from pdf.parser_po import extrair_campos_po, extrair_item
from pdf.parser_sgs import extrair_empresa, extrair_campos_cromato
from pdf.parser_origem_cromato import identificar_origem_cromato, extrair_campos_cromato_origem
from pdf.parser_UC import extrair_campos_uc, identificar_uc
from pdf.parser_tr import identificar_tr, extrair_campos_tr

def select_extract(caminho):
    """Identifies the PDF's certificate/report type and delegates to the matching parser.

    Tries, in order, to recognize the extracted text as: Uncertainty Calculation
    Report (CI), Gas Meter Run (Trecho Reto), Orifice Plate, Chromatography
    (SGS or Origem Energia Alagoas); if none match, assumes a secondary instrument.

    Args:
        caminho: Path of the PDF file to be processed.

    Returns:
        tuple: (dados, tipo) pair, where `dados` is the dictionary of fields extracted
        by the chosen parser and `tipo` is a string identifying the detected type
        ("ci", "trecho", "placa_orificio", "cromatografia" or "secundario").
    """
    texto = extrair_texto(caminho)

    if identificar_uc(texto):
        print('Relatório de Cálculo de Incerteza (CI)')
        dados = extrair_campos_uc(caminho, texto)
        tipo = "ci"

    elif identificar_tr(texto):
        print('Gas Meter Run / Trecho Reto')
        dados = extrair_campos_tr(texto)
        tipo = "trecho"

    elif extrair_item(texto) is not None:
        print('Instrumento placa de orificio')
        dados = extrair_campos_po(texto)
        tipo = "placa_orificio"

    elif extrair_empresa(texto) == 'SGS':
        print('Relatório de Cromatografia (SGS)')
        dados = extrair_campos_cromato(texto)
        tipo = 'cromatografia'

    elif identificar_origem_cromato(texto):
        print('Relatório de Cromatografia (Origem Energia Alagoas)')
        dados = extrair_campos_cromato_origem(texto)
        tipo = 'cromatografia'

    else:
        print("INSTRUMENTO SECUNDÁRIO")
        dados = extrair_campos(texto)
        tipo = "secundario"

    return dados, tipo

