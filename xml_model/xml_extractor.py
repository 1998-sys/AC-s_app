# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_extractor
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Extracts calibration points (reference, mean, deviation, uncertainty, k) from standard PDF certificate tables (TE, TT, PT, DPT).
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import pdfplumber
from pdf.parser_certificados import extrair_curva_calibracao, aplicar_curva_kpa



def _to_float(v):
    """Converts a table cell value to float, tolerating PDF formats.

    Args:
        v: raw value extracted from the table (str, number or None).

    Returns:
        float | None: converted value, or None if `v` is None, empty, "-",
        "∞" or cannot be converted (comma is treated as the decimal
        separator).
    """
    if v is None:
        return None

    v = str(v).strip()

    if v in ("", "-", "∞"):
        return None

    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _valor_pos_barra(v):
    """Extracts and converts to float the part after the "/" in "a/b"-format values.

    Used in PT/DPT tables where the trend/uncertainty cell comes as
    "valor_ma/valor_kpa"; when there is no "/", converts the whole value.

    Args:
        v: raw cell value (str, number or None).

    Returns:
        float | None: value after the slash (or the whole value, if there
        is no slash) converted to float, or None if it cannot be converted.
    """
    if v is None:
        return None

    v = str(v)

    if "/" in v:
        v = v.split("/")[-1]

    return _to_float(v)




def extrair_pontos_calibracao_pdf(caminho_pdf):
    """Extracts the calibration points from a standard PDF certificate (TE, TT, PT or DPT).

    Reads all tables and text from the PDF, classifies the instrument type
    from the text content (thermoresistance, temperature transmitter,
    pressure transmitter or differential pressure) and interprets the
    points table according to the specific layout of each type (including
    the PT/DPT case with mA reading converted via calibration curve, and
    the case of values in "a/b" format).

    Args:
        caminho_pdf: path of the certificate's PDF file.

    Returns:
        list[dict]: list of calibration points, each with the keys "tipo"
        (TE, TT, PT or DPT), "referencia", "media", "tendencia",
        "incerteza" and "k". Empty list if there are no tables or the
        instrument type is not recognized.
    """
    tabelas = []
    texto = ""

    
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto += (pagina.extract_text() or "") + "\n"

            for tabela in pagina.extract_tables() or []:
                if tabela and len(tabela) > 2:
                    tabelas.append(tabela)

    if not tabelas:
        return []

    texto_upper = texto.upper()
    pontos = []

    # Classification
    is_te = (
        "TERMORRESISTÊNCIA PT-100 - 2 FIOS" in texto_upper or
        "TERMORRESISTÊNCIA PT-100 - 3 FIOS" in texto_upper or
        "TERMORRESISTÊNCIA PT-100 - 4 FIOS" in texto_upper
    )

    is_tt = (
        "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA" in texto_upper or
        "TRANSMISSOR DE TEMPERATURA" in texto_upper or
        "TERMÔMETRO ANALÓGICO" in texto_upper or
        "TERMÔMETRO DIGITAL" in texto_upper
    )

    is_pt = ("TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA" in texto_upper or
            "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA" in texto_upper or
            "MANOMETRO DIGITAL" in texto_upper or
            "MANOMETRO ANALÓGICO" in texto_upper or
            "MANOMETRO DIGITAL ABSOLUTO" in texto_upper
    )

    is_dpt = (
        "DIFFERENTIAL" in texto_upper or
        "DIFERENCIAL" in texto_upper or
        "-DPT" in texto_upper or
        "PDIT" in texto_upper or
        "-FT-" in texto_upper
    )
    
    
    if is_te and not is_tt:
        tabela = tabelas[0]

        for linha in tabela[1:]:
            if len(linha) < 7:
                continue

            referencia = _to_float(linha[2])
            if referencia is None:
                continue

            pontos.append({
                "tipo": "TE",
                "referencia": referencia,
                "media": _to_float(linha[4]),
                "tendencia": _to_float(linha[5]),
                "incerteza": _to_float(linha[6]),
                "k": _to_float(linha[7]) if len(linha) > 7 else None
            })

        return pontos

    
    
    if is_tt:
        tabela = tabelas[0]

        
        cabecalho = " ".join(
            str(c).upper()
            for c in tabela[0]
            if c
        )

        possui_ma_dc = "MA DC" in cabecalho

        for linha in tabela[1:]:
            if len(linha) < 5:
                continue

            referencia = _to_float(linha[0])
            if referencia is None:
                continue

           
            
            if possui_ma_dc:
                media = _to_float(linha[1])        
                tendencia = _to_float(linha[3])    
                incerteza = _to_float(linha[4])    
                k = _to_float(linha[5]) if len(linha) > 5 else None

            
            
            else:
                media = _to_float(linha[1])
                tendencia = _to_float(linha[2])
                incerteza = _to_float(linha[3])
                k = _to_float(linha[4]) if len(linha) > 4 else None

            pontos.append({
                "tipo": "TT",
                "referencia": referencia,
                "media": media,
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    
    
    if (is_pt or is_dpt) and len(tabelas) >= 2:
        tabela = tabelas[1]
        tipo = "DPT" if is_dpt else "PT"

        cabecalho = " ".join(
            str(c).upper()
            for c in tabela[0]
            if c
        )

        media_em_ma = "MA DC" in cabecalho
        curva_calibracao = extrair_curva_calibracao(texto)

        for linha in tabela[1:]:
            if len(linha) < 4:
                continue

            referencia = _to_float(linha[0])
            if referencia is None:
                continue

            media_ma = _to_float(linha[1])
            media_kpa = _to_float(linha[2])

            if media_em_ma and curva_calibracao:
                media = round(aplicar_curva_kpa(media_ma, curva_calibracao), 3)
            else:
                media = media_kpa

            if "/" in str(linha[3]):
                tendencia = _valor_pos_barra(linha[3])
                incerteza = _valor_pos_barra(linha[4]) if len(linha) > 4 else None
            else:
                tendencia = _to_float(linha[3])
                incerteza = _to_float(linha[4]) if len(linha) > 4 else None

            k = _to_float(linha[5]) if len(linha) > 5 else None

            pontos.append({
                "tipo": tipo,
                "referencia": referencia,
                "media": media,
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    return []