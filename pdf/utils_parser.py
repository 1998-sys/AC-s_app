
from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos
from pdf.parser_po import extrair_campos_po, extrair_item
from pdf.parser_sgs import extrair_empresa, extrair_campos_cromato
from pdf.parser_origem_cromato import identificar_origem_cromato, extrair_campos_cromato_origem
from pdf.parser_UC import extrair_campos_uc, identificar_uc
from pdf.parser_tr import identificar_tr, extrair_campos_tr

def select_extract(caminho):
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

