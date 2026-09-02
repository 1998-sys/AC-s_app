# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_table_extractor
# Created       : 20-01-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Extracts and classifies the calibration tables (AS FOUND/AS LEFT/RESULTS) from the PDF per instrument category into structured records.
#                 Extrai e classifica as tabelas de calibração (AS FOUND/AS LEFT/RESULTADOS) do PDF por categoria de instrumento em registros estruturados.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import pdfplumber
import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pdf.parser_certificados import extrair_categoria_intrumento



def to_float(valor):
    """Converts a table cell value to float, normalizing minus signs and decimal comma.

    Args:
        valor: raw value extracted from the table (str, number or None).

    Returns:
        float | None: converted value, or None if `valor` is None or
        cannot be converted.
    """
    if valor is None:
        return None

    try:
        v = str(valor).strip()

        v = (
            v.replace("−", "-")
             .replace("–", "-")
             .replace("‐", "-")
        )

        return float(v.replace(",", "."))
    except ValueError:
        return None


def to_valor_eng(valor):
    """Converts an "engineering" value (uncertainty, k, deviation, veff) while preserving special markers.

    Unlike `to_float`, keeps the texts "INFINITO" and "NI" (not informed)
    instead of returning None when the value is not numeric.

    Args:
        valor: raw value extracted from the table (str, number or None).

    Returns:
        float | str | None: converted numeric value; "INFINITO" if the
        value represents infinity ("∞", "INFINITO", "infinito"); "NI" if
        it is a not-informed marker ("-", "--", "- / -", "NI") or cannot be
        converted; None if `valor` is None.
    """
    if valor is None:
        return None

    v = str(valor).strip()

    v = (
        v.replace("−", "-")
         .replace("–", "-")
         .replace("‐", "-")
    )

    if v in ("∞", "INFINITO", "infinito"):
        return "INFINITO"

    if v in ("-", "--", "- / -", "NI"):
        return "NI"

    try:
        return float(v.replace(",", "."))
    except ValueError:
        return "NI"


def pegar_valor_kpa(valor):
    """Extracts the value in kPa from a cell in "valor_ma/valor_kpa" format.

    Metrological rule: for electric pressure transmitters, uses the value
    after the slash (/), which represents kPa; if there is no slash, uses
    the whole value.

    Args:
        valor: raw content of the cell (accepts None).

    Returns:
        str | None: part after the slash (or the whole value, without a
        slash), as a string; None if `valor` is None.
    """
    if valor is None:
        return None

    partes = str(valor).split("/")
    return partes[1].strip() if len(partes) > 1 else partes[0].strip()



def extrair_texto_pagina(pdf, indice):
    """Extracts the text of a PDF page by index, tolerating an out-of-range index.

    Args:
        pdf: open PDF object (pdfplumber).
        indice: (0-based) index of the page to extract.

    Returns:
        str: page text, or empty string if the index does not exist or the
        page has no text.
    """
    try:
        return pdf.pages[indice].extract_text() or ""
    except IndexError:
        return ""


def extrair_tabelas_pagina_2(pdf):
    """Extracts the tables from the second page (index 1) of the calibration PDF.

    Tries the lines-based strategy first (drawn borders); if no table is
    found, uses the text-based strategy as a fallback (for PDFs without
    visible borders).

    Args:
        pdf: open PDF object (pdfplumber).

    Returns:
        list: list of extracted tables (each table is a list of rows);
        empty list if no table is found.
    """
    page = pdf.pages[1]

    tabelas = page.extract_tables({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines"
    })

    if not tabelas:
        tabelas = page.extract_tables({
            "vertical_strategy": "text",
            "horizontal_strategy": "text"
        })

    return tabelas or []


def classificar_tabelas(tabelas):
    """Classifies the tables extracted from the results page into AS_FOUND, AS_LEFT and RESULTADOS.

    Convention: the last table is always RESULTADOS; of the remaining
    ones, the first is AS_FOUND and, if there is a second one, it is
    AS_LEFT.

    Args:
        tabelas: list of extracted tables (see `extrair_tabelas_pagina_2`).

    Returns:
        dict: {"AS_FOUND": tabela | None, "AS_LEFT": tabela | None,
        "RESULTADOS": tabela | None}.
    """
    classificacao = {
        "AS_FOUND": None,
        "AS_LEFT": None,
        "RESULTADOS": None
    }

    qtd_tabelas = len(tabelas) if tabelas else 0
    
    if not tabelas:
        return classificacao

    classificacao["RESULTADOS"] = tabelas[-1]
    leitura = tabelas[:-1]

    if len(leitura) == 1:
        classificacao["AS_FOUND"] = leitura[0]
    elif len(leitura) >= 2:
        classificacao["AS_FOUND"] = leitura[0]
        classificacao["AS_LEFT"] = leitura[1]

    return classificacao



def ajustar_transmissor_pressao_eletrico(categoria, tabelas):
    """Structures the AS FOUND/AS LEFT/RESULTADOS records of an electric pressure transmitter.

    In the AS FOUND/AS LEFT tables, reads reference (SI and kPa),
    increasing/decreasing cycle points and standard deviation of each
    cycle. In the RESULTADOS table, applies the metrological rule of
    extracting the value in kPa (after the "/") for deviation and
    uncertainty via `pegar_valor_kpa`.

    Args:
        categoria: instrument category (text extracted from the PDF),
            passed back unchanged in the result.
        tabelas: dict classified by `classificar_tabelas`.

    Returns:
        dict: {"categoria": ..., "tabelaN": table name, "resultsN":
        list of records}, for N = 1..2 (AS FOUND/AS LEFT) and the
        RESULTADOS table.
    """
    resultado = {"categoria": categoria}
    idx = 1

    # ---------- AS FOUND / AS LEFT ----------
    for tipo in ("AS_FOUND", "AS_LEFT"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 2:
            continue

        registros = []
        for linha in tabela[2:]:
            if len(linha) < 6:
                continue

            registros.append({
                "SI_REF": to_float(linha[0]),
                "kPa_ref": to_float(linha[1]),
                "p_cic_cresc": to_float(linha[2]),
                "p_cic_decres": to_float(linha[3]),
                "s_cic_cres": to_float(linha[4]),
                "s_cic_decrs": to_float(linha[5]),
                "media": to_float(linha[6]) if len(linha) > 6 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    # ---------- RESULTADOS (REGRA mA) ----------
    tabela_res = tabelas.get("RESULTADOS")
    if tabela_res:
        registros = []
        for linha in tabela_res[1:]:
            if len(linha) < 7:
                continue

            registros.append({
                "referencia_si_kpa": to_float(linha[0]),
                "referencia_ma": to_float(linha[1]),
                "media_leituras_ma": to_float(linha[2]),
                "tendencia_kpa": to_valor_eng(pegar_valor_kpa(linha[3])),
                "incerteza_kpa": to_valor_eng(pegar_valor_kpa(linha[4])),
                "k": to_valor_eng(linha[5]),
                "veff": to_valor_eng(linha[6])
            })

        resultado[f"tabela{idx}"] = "RESULTADOS"
        resultado[f"results{idx}"] = registros

    return resultado


def ajustar_transmissor_temperatura_eletrico(categoria, tabelas):
    """Structures the AS FOUND/AS LEFT/RESULTADOS records of an electric temperature transmitter.

    Reads, from each row, reference in °C, mean in °C, mean in mA,
    deviation, uncertainty, k and veff.

    Args:
        categoria: instrument category (text extracted from the PDF),
            passed back unchanged in the result.
        tabelas: dict classified by `classificar_tabelas`.

    Returns:
        dict: {"categoria": ..., "tabelaN": table name, "resultsN": list of
        records}, for each table present among AS FOUND, AS LEFT and
        RESULTADOS.
    """
    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT", "RESULTADOS"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 1:
            continue

        registros = []
        for linha in tabela[1:]:
            if len(linha) < 6:
                continue

            registros.append({
                "valor_referencia_c": to_float(linha[0]),
                "media_leituras_c": to_float(linha[1]),
                "media_mA": to_float(linha[2]),
                "tendencia_c": to_float(linha[3]),
                "incerteza_c": to_valor_eng(linha[4]),
                "k": to_valor_eng(linha[5]),
                "veff": to_valor_eng(linha[6]) if len(linha) > 6 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    return resultado


def ajustar_transmissor_temperatura(categoria, tabelas):
    """Structures the RESULTADOS table records of a temperature transmitter in the simplified format.

    Simplified Temperature Transmitter format (6 columns, no mA column):
    Reference | Average Reading | Error | Expanded Uncertainty | k | Veff.

    Args:
        categoria: instrument category (text extracted from the PDF),
            passed back unchanged in the result.
        tabelas: dict classified by `classificar_tabelas`.

    Returns:
        dict: {"categoria": ...} plus "tabela1"/"results1" if the
        RESULTADOS table exists; otherwise, just {"categoria": ...}.
    """
    resultado = {"categoria": categoria}

    tabela = tabelas.get("RESULTADOS")
    if not tabela or len(tabela) <= 1:
        return resultado

    registros = []
    for linha in tabela[1:]:
        if len(linha) < 5:
            continue

        registros.append({
            "valor_referencia_c": to_float(linha[0]),
            "media_leituras_c":   to_float(linha[1]),
            "tendencia_c":        to_float(linha[2]),
            "incerteza_c":        to_valor_eng(linha[3]),
            "k":                  to_valor_eng(linha[4]),
            "veff":               to_valor_eng(linha[5]) if len(linha) > 5 else None,
        })

    resultado["tabela1"] = "RESULTADOS"
    resultado["results1"] = registros
    return resultado


def ajustar_manometros(categoria, tabelas):
    """Structures the AS FOUND/AS LEFT/RESULTADOS records of pressure gauges (digital, analog and differential).

    In the AS FOUND/AS LEFT tables, reads reference (SI and kPa),
    increasing/decreasing cycle points, standard deviation of each cycle
    and the mean. In the RESULTADOS table, extracts the part before the
    slash ("/") from the deviation column (value in kPa).

    Args:
        categoria: instrument category (text extracted from the PDF),
            passed back unchanged in the result.
        tabelas: dict classified by `classificar_tabelas`.

    Returns:
        dict: {"categoria": ..., "tabelaN": table name, "resultsN": list of
        records}, for each table present among AS FOUND, AS LEFT and
        RESULTADOS.
    """
    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 2:
            continue

        registros = []
        for linha in tabela[2:]:
            if len(linha) < 6:
                continue

            registros.append({
                "SI_kpa": to_float(linha[0]),
                "kPa_ref": to_float(linha[1]),
                "p_cic_cresc": to_float(linha[2]),
                "p_cic_decres": to_float(linha[3]),
                "s_cic_cres": to_float(linha[4]),
                "s_cic_decrs": to_float(linha[5]),
                "media": to_float(linha[6]) if len(linha) > 6 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    tabela_res = tabelas.get("RESULTADOS")
    if tabela_res:
        registros = []
        for linha in tabela_res[1:]:
            if len(linha) < 7:
                continue

            registros.append({
                "referencia_si_kpa": to_float(linha[0]),
                "p_indicada_kpa": to_float(linha[1]),
                "media_leituras_kpa": to_float(linha[2]),
                "tendencia_kpa": to_valor_eng(linha[3].split("/")[0]) if linha[3] else None,
                "incerteza_kpa": to_valor_eng(linha[4]),
                "k": to_valor_eng(linha[5]),
                "veff": to_valor_eng(linha[6])
            })

        resultado[f"tabela{idx}"] = "RESULTADOS"
        resultado[f"results{idx}"] = registros

    return resultado


def ajustar_pt100(categoria, tabelas):
    """Structures the AS FOUND/AS LEFT/RESULTADOS records of PT-100 thermoresistances (2, 3 or 4 wires).

    Reads, from each row, depth, standard used, reference value, mean in
    ohm, mean in °C, deviation, uncertainty, k and veff.

    Args:
        categoria: instrument category (text extracted from the PDF),
            passed back unchanged in the result.
        tabelas: dict classified by `classificar_tabelas`.

    Returns:
        dict: {"categoria": ..., "tabelaN": table name, "resultsN": list of
        records}, for each table present among AS FOUND, AS LEFT and
        RESULTADOS.
    """
    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT", 'RESULTADOS'):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 1:
            continue

        registros = []
        for linha in tabela[1:]:
            registros.append({
                "profundidade": linha[0] if len(linha) > 0 else None,
                "padrao_utilizado": linha[1] if len(linha) > 1 else None,
                "valor_referencia": to_float(linha[2]) if len(linha) > 2 else None,
                "media_ohm": to_float(linha[3]) if len(linha) > 3 else None,
                "media_celsius": to_float(linha[4]) if len(linha) > 4 else None,
                "tendencia": to_valor_eng(linha[5]) if len(linha) > 5 else None,
                "incerteza": to_valor_eng(linha[6]) if len(linha) > 6 else None,
                "k": to_valor_eng(linha[7]) if len(linha) > 7 else None,
                "veff": to_valor_eng(linha[8]) if len(linha) > 8 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    return resultado


def ajustar_termometro_digital_analogico(categoria, tabelas):
    """Structures the AS FOUND/AS LEFT/RESULTADOS records of digital or analog thermometers.

    Expected table structure: Reference | Reading Medium | Deviation |
    Uncertainty | k | Veff.

    Args:
        categoria: instrument category (text extracted from the PDF),
            passed back unchanged in the result.
        tabelas: dict classified by `classificar_tabelas`.

    Returns:
        dict: {"categoria": ..., "tabelaN": table name, "resultsN": list of
        records}, for each table present among AS FOUND, AS LEFT and
        RESULTADOS.
    """

    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT", "RESULTADOS"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 1:
            continue

        registros = []

        for linha in tabela[1:]:
            if len(linha) < 6:
                continue

            registros.append({
                "valor_referencia_c": to_float(linha[0]),
                "media_leituras_c": to_float(linha[1]),
                "tendencia_c": to_valor_eng(linha[2]),
                "incerteza_c": to_valor_eng(linha[3]),
                "k": to_valor_eng(linha[4]),
                "veff": to_valor_eng(linha[5])
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    return resultado


def processar_pdf(pdf_path):
    """Opens a calibration certificate PDF and extracts the calibration records according to the instrument category.

    Extracts the instrument category (page 1) and the results tables
    (page 2), classifies the tables into AS_FOUND/AS_LEFT/RESULTADOS and
    dispatches to the adjustment function specific to the category
    (electric pressure/temperature transmitter, temperature transmitter,
    pressure gauge, PT-100 or digital/analog thermometer).

    Args:
        pdf_path: path of the calibration certificate's PDF file.

    Returns:
        dict: structured calibration records, in the format returned by
        the adjustment function corresponding to the category.

    Raises:
        ValueError: if the instrument category is not supported by any of
            the known adjustment functions.
    """
    with pdfplumber.open(pdf_path) as pdf:

        categoria = extrair_categoria_intrumento(
            extrair_texto_pagina(pdf, 0)
        ).upper()

        tabelas = extrair_tabelas_pagina_2(pdf)
        classificacao = classificar_tabelas(tabelas)
        
        

        if "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA" in categoria or 'TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA' in categoria:
            return ajustar_transmissor_pressao_eletrico(categoria, classificacao)

        elif "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA" in categoria:
            return ajustar_transmissor_temperatura_eletrico(categoria, classificacao)

        elif "TRANSMISSOR DE TEMPERATURA" in categoria:
            return ajustar_transmissor_temperatura(categoria, classificacao)

        elif any(c in categoria for c in [
            "MANOMETRO DIGITAL",
            "MANOMETRO ANALÓGICO",
            "MANOMETRO DIGITAL ABSOLUTO",
            "MANOMETRO DIFERENCIAL DIGITAL",
            "MANOMETRO DIFERENCIAL ANALÓGICO"
        ]):
            return ajustar_manometros(categoria, classificacao)

        elif any(c in categoria for c in [
            "TERMORRESISTÊNCIA PT-100 - 2 FIOS",
            'TERMORRESISTÊNCIA PT-100 - 3 FIOS',
            'TERMORRESISTÊNCIA PT-100 - 4 FIOS'
        ]):
            return ajustar_pt100(categoria, classificacao)
        
        elif any(c in categoria for c in [
            "TERMÔMETRO DIGITAL",
            "TERMÔMETRO ANALÓGICO",
        ]):
            return ajustar_termometro_digital_analogico(categoria, classificacao)
            

        else:
            raise ValueError(f"Categoria não suportada: {categoria}")


