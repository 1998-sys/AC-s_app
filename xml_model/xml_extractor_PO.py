# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_extractor_PO
# Created       : 23-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Extracts the measured dimensional values (bore diameter, thickness, flatness, roughness, angles) of an orifice plate inspection PDF.
#                 Extrai os valores dimensionais medidos (diâmetro do furo, espessura, planeza, rugosidade, ângulos) do PDF de inspeção da placa de orifício.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import pdfplumber
import unicodedata
import re
from xml_model.xml_table_extractor import to_valor_eng


def normalizar_unidade(unidade):
    if unidade is None:
        return None
    u = str(unidade).strip()
    if u == "µm Ra":
        return "µm"
    return u


def normalizar_texto(texto):
    if not texto:
        return ""

    texto = texto.lower()
    texto = texto.replace("'", "")
    texto = texto.replace('"', "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def extrair_valores_medidos(caminho_pdf):

    mapa_chaves = {
        "circularity deviation of orifice bore diameter": "desv_circ",
        "orifice bore diameter": "d_int",
        "orifice plate thickness": "exp_po",
        "orifice bore thickness": "comp_tr",
        "flatness": "desv_planeza",
        "orifice plate angled bevel": "ang_chanf",
        "orifice bore and upstream face of orifice plate angle": "ang_of_mont",
        "upstream face roughness": "rug_mont",
        "downstream face roughness": "rug_jus",
        "external diameter": "d_ext"
    }

    resultado = {}

    with pdfplumber.open(caminho_pdf) as pdf:

        for pagina in pdf.pages:

            tabelas = pagina.extract_tables()
            if not tabelas:
                continue

            for tabela in tabelas:

                if not tabela or len(tabela) < 2:
                    continue

               
                cabecalho = " ".join(str(c) for c in tabela[0] if c)
                if "Measured Avg" not in cabecalho:
                    continue

                
                for linha in tabela[1:]:

                    if not linha or len(linha) < 6:
                        continue

                    descricao = normalizar_texto(linha[0])

                   
                    for chave_pdf, chave_final in sorted(
                        mapa_chaves.items(),
                        key=lambda x: len(x[0]),
                        reverse=True
                    ):

                        if chave_pdf in descricao:

                            unidade = normalizar_unidade(linha[1])
                            media = to_valor_eng(linha[2])
                            incerteza = to_valor_eng(linha[3])
                            k = to_valor_eng(linha[4])
                            veff = to_valor_eng(linha[5])

                            resultado[chave_final] = {
                                "unidade": unidade,
                                "media": media,
                                "incerteza": incerteza,
                                "k": k,
                                "veff": veff
                            }

                            break  
     
    
    return resultado