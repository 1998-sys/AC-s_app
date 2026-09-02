# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_extractor_FT
# Created       : 31-07-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses a flow meter external calibration XML and returns the header fields and calibration points for the linearization report.
#                 Interpreta o XML de calibração externa de medidor de vazão e retorna os campos de cabeçalho e os pontos de calibração para o relatório de linearização.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import defusedxml.ElementTree as ET


def _texto(element, path, default=""):
    """Reads the (stripped) text of a sub-element located by `path`.

    Args:
        element: XML element to search in.
        path: relative path (ElementTree find syntax) of the sub-element.
        default: value returned if the element does not exist or has no text.

    Returns:
        str: element text, or `default`.
    """
    el = element.find(path)
    return el.text.strip() if el is not None and el.text else default


def _float(element, path, default=0.0):
    """Reads the text of a sub-element and converts it to float, tolerating decimal comma and "NI".

    Args:
        element: XML element to search in.
        path: relative path (ElementTree find syntax) of the sub-element.
        default: value returned if the text is empty, is "NI" (not
            informed) or cannot be converted.

    Returns:
        float: converted value, or `default`.
    """
    val = _texto(element, path)
    if not val or val == "NI":
        return default
    try:
        return float(val.replace(",", "."))
    except ValueError:
        return default


def is_certificado_ft(caminho_xml):
    """Checks whether the XML file is a flow meter external calibration certificate.

    Args:
        caminho_xml: path of the XML file to inspect.

    Returns:
        bool: True if the root tag contains "CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO",
        False otherwise or if the XML cannot be parsed.
    """
    try:
        for _, elem in ET.iterparse(caminho_xml, events=("start",)):
            return "CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO" in elem.tag
    except ET.ParseError:
        return False


def extrair_dados_ft(caminho_xml):
    """Extracts from the flow meter external calibration certificate the data for the linearization report.

    Args:
        caminho_xml: path of the CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO XML file.

    Returns:
        dict: header fields (certificate number, laboratory, tag,
        manufacturer, calibrated range, K factor etc.) and the "pontos" key
        with the list of calibration points (flow rate, reference/meter
        volumes in liters, meter factor, percentage error, uncertainty).

    Notes:
        Frequency, corrected K-factor, Status, average KF and the alarm
        limits are NOT calculated here — they are formulas already present
        in Template_Linearizacao.xlsx, derived from the values this dict
        provides. See form/utils_print_linearizacao.py.
    """
    tree = ET.parse(caminho_xml)
    root = tree.getroot()

    fator_k = _float(root, "MEDIDOR_VAZAO/FATOR_K_DO_MEDIDOR")

    faixa_min = _texto(root, "MEDIDOR_VAZAO/FAIXA_NOMINAL/MIN")
    faixa_max = _texto(root, "MEDIDOR_VAZAO/FAIXA_NOMINAL/MAX")

    dados = {
        "numero_certificado": _texto(root, "NUMERO_CERTIFICADO"),
        "data_emissao":       _texto(root, "DATA_EMISSAO"),
        "laboratorio":        _texto(root, "LABORATORIO/NOME"),
        "unidade_operacional": _texto(root, "CLIENTE/UNIDADE_OPERACIONAL"),
        "tag":                _texto(root, "MEDIDOR_VAZAO/TAG"),
        "num_serie":          _texto(root, "MEDIDOR_VAZAO/NUM_SERIE"),
        "fabricante":         _texto(root, "MEDIDOR_VAZAO/FABRICANTE"),
        "modelo":             _texto(root, "MEDIDOR_VAZAO/MODELO"),
        "tipo":               _texto(root, "MEDIDOR_VAZAO/TIPO"),
        "diametro":           _texto(root, "MEDIDOR_VAZAO/DIAMETRO_NOMINAL") + '"',
        "faixa_min":          faixa_min,
        "faixa_max":          faixa_max,
        "faixa_calibrada":    f"{faixa_min} m³/h a {faixa_max} m³/h",
        "data_calibracao":    _texto(root, "MEDIDOR_VAZAO/DATA_CALIBRACAO"),
        "fator_k":            fator_k,
        "pontos":             [],
    }

    pontos_xml = root.findall(
        "MEDIDOR_VAZAO/CALIBRACAO_AS_FOUND/PONTOS_DE_CALIBRACAO/PONTO_DE_CALIBRACAO"
    )

    for p in pontos_xml:
        vazao = _float(p, "VAZAO_CALIBRADA")

        vol_padrao_m3   = _float(p, "VOLUME_PADRAO")
        vol_medidor_m3  = _float(p, "VOLUME_MEDIDOR")
        meter_factor    = _float(p, "FATOR_DO_MEDIDOR/VALOR", 1.0)
        desvio          = _float(p, "DESVIO_MEDIO")

        incerteza_el = p.find("FATOR_DO_MEDIDOR/INCERTEZA_EXP")
        incerteza = (
            float(incerteza_el.text.strip())
            if incerteza_el is not None and incerteza_el.text
            else 0.0
        )

        dados["pontos"].append({
            "vazao":            vazao,
            "vol_referencia_l": round(vol_padrao_m3 * 1000, 2),
            "vol_medidor_l":    round(vol_medidor_m3 * 1000, 2),
            "meter_factor":     meter_factor,
            "erro_pct":         desvio,
            "incerteza":        incerteza,
        })

    return dados
