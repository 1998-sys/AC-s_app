
from pdf.extrator import extrair_texto  
from pdf.parser_certificados import extrair_campos
from pdf.parser_po import extrair_campos_po, extrair_item


def select_extract(caminho):
    instrumento = extrair_item(extrair_texto(caminho))
    texto = extrair_texto(caminho)

    if instrumento is not None:
        print('Instrumento placa de orificio')
        dados = extrair_campos_po(texto)
        tipo = "placa_orificio"
    else:
        print("INSTRUMENTO SECUNDÁRIO")
        dados = extrair_campos(texto)
        tipo = "secundario"

    return dados, tipo

