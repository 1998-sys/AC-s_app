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
    el = element.find(path)
    return el.text.strip() if el is not None and el.text else default


def _float(element, path, default=0.0):
    val = _texto(element, path)
    if not val or val == "NI":
        return default
    try:
        return float(val.replace(",", "."))
    except ValueError:
        return default


def is_certificado_ft(caminho_xml):
    """Retorna True se o XML for um CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO."""
    try:
        for _, elem in ET.iterparse(caminho_xml, events=("start",)):
            return "CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO" in elem.tag
    except ET.ParseError:
        return False


def extrair_dados_ft(caminho_xml):
    """
    Parseia CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO e retorna dict com
    os campos de cabeçalho e a lista de pontos de calibração.

    Frequência, K-factor corrigido, Status, KF médio e os limites de alarme
    NÃO são calculados aqui — são fórmulas já presentes no
    Template_Linearizacao.xlsx, derivadas dos valores que este dict fornece
    (vazão, volumes, meter factor, erro, incerteza). Ver
    form/utils_print_linearizacao.py."""
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
