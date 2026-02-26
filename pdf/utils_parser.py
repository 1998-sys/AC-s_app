
from pdf.extrator import extrair_texto  
from pdf.parser_certificados import extrair_campos
from pdf.parser_po import extrair_campos_po, extrair_item
from pdf.parser_sgs import extrair_empresa, extrair_campos_cromato

def select_extract(caminho):
    instrumento = extrair_item(extrair_texto(caminho))
    empresa = extrair_empresa(extrair_texto(caminho))

    texto = extrair_texto(caminho)

    if instrumento is not None:
        print('Instrumento placa de orificio')
        dados = extrair_campos_po(texto)
        tipo = "placa_orificio"

    elif empresa == 'SGS':
        print('Relatório de Cromatografia')
        dados = extrair_campos_cromato(texto)
        tipo = 'cromatografia'
    else:
        print("INSTRUMENTO SECUNDÁRIO")
        dados = extrair_campos(texto)
        tipo = "secundario"

    return dados, tipo

