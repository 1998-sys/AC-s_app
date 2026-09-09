# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_extractor_FT
# Created       : 31-07-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses a flow meter external calibration XML and returns the header fields and calibration points for the linearization report.
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


def _unidade_amigavel(unidade: str) -> str:
    """Normalizes an ASCII engineering unit from UNIDADE_ENG (e.g. "m3/h") to its display form ("m³/h").

    Args:
        unidade: raw value of the UNIDADE_ENG attribute.

    Returns:
        str: `unidade` with "m3" replaced by "m³" (the schema allows either
        spelling); returned unchanged for any other unit.
    """
    return unidade.replace("m3", "m³") if unidade else unidade


def _valor_unidade(element, path, default=0.0):
    """Reads a `t_valor_decimal_eng` element: its value, original decimal places and UNIDADE_ENG attribute.

    Every numeric field of this XML schema (VAZAO_CALIBRADA, VOLUME_PADRAO,
    VOLUME_MEDIDOR etc.) carries its actual engineering unit in the
    UNIDADE_ENG attribute — the same element/schema is used by different
    meter types with different units, so the unit can't be assumed fixed.

    Args:
        element: XML element to search in.
        path: relative path (ElementTree find syntax) of the sub-element.
        default: value returned if the text is empty, is "NI" or cannot be
            converted.

    Returns:
        tuple: (valor: float, casas_decimais: int, unidade: str) — casas_decimais
        is the number of decimal digits in the certificate's own text (0 if
        it's an integer), so the output cell can be formatted to match it
        instead of a fixed template format. unidade is already normalized
        via `_unidade_amigavel`.
    """
    el = element.find(path)
    unidade = _unidade_amigavel(el.get("UNIDADE_ENG", "")) if el is not None else ""

    texto = el.text.strip() if el is not None and el.text else ""
    if not texto or texto == "NI":
        return default, 0, unidade

    texto_ponto = texto.replace(",", ".")
    try:
        valor = float(texto_ponto)
    except ValueError:
        return default, 0, unidade

    casas_decimais = len(texto_ponto.split(".")[1]) if "." in texto_ponto else 0
    return valor, casas_decimais, unidade


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
        manufacturer, calibrated range, K factor etc.), including
        "cliente_xml" (raw CLIENTE/NOME text, used by
        form.utils_print_linearizacao.identificar_cliente to resolve the
        report's "Cliente" field without depending on the file's path),
        the unit of each numeric column ("vazao_unidade",
        "vol_referencia_unidade", "vol_medidor_unidade" — read from each
        point's own UNIDADE_ENG attribute, not assumed) and the "pontos"
        key with the list of calibration points (flow rate, reference/meter
        volumes — kept in the certificate's own unit, no forced conversion
        — meter factor, percentage error, uncertainty, plus a "*_casas"
        decimal-place count per value so the output cell can mirror the
        certificate's precision).

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
        "cliente_xml":        _texto(root, "CLIENTE/NOME"),
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

    # AS_LEFT only exists when the meter received a manual adjustment of the
    # calibration constant during the test — in that case it's the final
    # (post-adjustment) result that must be reported, not AS_FOUND (deviation
    # before the adjustment, kept only for traceability). Without an
    # adjustment, the certificate only brings AS_FOUND anyway (it's the
    # calibration's own result).
    pontos_xml = root.findall(
        "MEDIDOR_VAZAO/CALIBRACAO_AS_LEFT/PONTOS_DE_CALIBRACAO/PONTO_DE_CALIBRACAO"
    )
    if not pontos_xml:
        pontos_xml = root.findall(
            "MEDIDOR_VAZAO/CALIBRACAO_AS_FOUND/PONTOS_DE_CALIBRACAO/PONTO_DE_CALIBRACAO"
        )

    for p in pontos_xml:
        vazao, vazao_casas, vazao_unidade = _valor_unidade(p, "VAZAO_CALIBRADA")
        vol_ref, vol_ref_casas, vol_ref_unidade = _valor_unidade(p, "VOLUME_PADRAO")
        vol_med, vol_med_casas, vol_med_unidade = _valor_unidade(p, "VOLUME_MEDIDOR")
        meter_factor = _float(p, "FATOR_DO_MEDIDOR/VALOR", 1.0)
        desvio       = _float(p, "DESVIO_MEDIO")

        incerteza_el = p.find("FATOR_DO_MEDIDOR/INCERTEZA_EXP")
        incerteza = (
            float(incerteza_el.text.strip())
            if incerteza_el is not None and incerteza_el.text
            else 0.0
        )

        dados["pontos"].append({
            "vazao":              vazao,
            "vazao_casas":        vazao_casas,
            "vol_referencia":     vol_ref,
            "vol_referencia_casas": vol_ref_casas,
            "vol_medidor":        vol_med,
            "vol_medidor_casas":  vol_med_casas,
            "meter_factor":       meter_factor,
            "erro_pct":           desvio,
            "incerteza":          incerteza,
        })
        # Unit comes from the meter's own schema, the same in every point of
        # the certificate — uses the first read point's unit for the column headers.
        dados.setdefault("vazao_unidade", vazao_unidade)
        dados.setdefault("vol_referencia_unidade", vol_ref_unidade)
        dados.setdefault("vol_medidor_unidade", vol_med_unidade)

    return dados
