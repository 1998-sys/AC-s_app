
from pdf.extrator import extrair_texto
from pdf.parser_certificados import extrair_campos
from pdf.parser_po import extrair_campos_po, extrair_item
from pdf.parser_sgs import extrair_empresa, extrair_campos_cromato
from pdf.parser_UC import extrair_campos_uc, identificar_uc

def select_extract(caminho):
    texto = extrair_texto(caminho)

    if identificar_uc(caminho):
        print('Relatório de Cálculo de Incerteza (CI)')
        dados = extrair_campos_uc(caminho)
        tipo = "ci"

    elif extrair_item(texto) is not None:
        print('Instrumento placa de orificio')
        dados = extrair_campos_po(texto)
        tipo = "placa_orificio"

    elif extrair_empresa(texto) == 'SGS':
        print('Relatório de Cromatografia')
        dados = extrair_campos_cromato(texto)
        tipo = 'cromatografia'

    else:
        print("INSTRUMENTO SECUNDÁRIO")
        dados = extrair_campos(texto)
        tipo = "secundario"

    return dados, tipo

