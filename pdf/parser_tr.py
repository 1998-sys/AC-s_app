# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_tr
# Created       : 24-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses Gas Meter Run (trecho reto) calibration certificates, extracting standard, components, dimensions and environmental conditions.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re
from pdf.parser_certificados import (
    extrair_certificado, extrair_datas, endereco_cliente,
    SIGNATARIOS_VALIDOS, extrair_assinaturas, separar_signatario,
    extrair_padroes,
)
from pdf.parser_po import coeficiente_dilatacao


def extrair_norma_tr(texto):
    """Identifies the gas meter run's sizing standard (AGA 3, ISO 17089 or ISO 5167)
    and builds the normalized string with edition and year.

    Tries each standard in order (AGA 3 -> ISO 17089 -> ISO 5167); when the
    year isn't found in the text, assumes a default per standard (AGA3-2:2000,
    ISO 17089-2:2010, ISO 5167-2:2022).

    Args:
        texto: Text extracted from the certificate.

    Returns:
        str: Normalized standard (e.g.: "AGA3-2:2000", "ISO 17089-2:2010",
        "ABNT NBR ISO 5167-2:2022"), or "ISO 5167-2:2022" as the final
        default if no standard is recognized in the text.
    """
    texto_norm = re.sub(r"[‐–—‐‑‒–—]", "-", texto)

    # AGA 3 → "AGA3-2:YEAR"
    m = re.search(r"AGA\s*3\b[^.\n\r]*?\b(1991|2000|2016)\b", texto_norm, re.IGNORECASE)
    if m:
        return f"AGA3-2:{m.group(1)}"
    if re.search(r"AGA\s*3\b", texto_norm, re.IGNORECASE):
        return "AGA3-2:2000"

    # ISO 17089 → "ISO 17089-2:YEAR"
    m = re.search(r"ISO\s*17089(-\d+)?(?::(\d{4}))?", texto_norm, re.IGNORECASE)
    if m:
        parte = m.group(1) or "-2"
        ano   = m.group(2) or "2010"
        return f"ISO 17089{parte}:{ano}"

    # ISO 5167 → "ISO 5167-2:YEAR" or "ABNT NBR ISO 5167-2:YEAR"
    m = re.search(r"(ABNT\s+NBR\s+)?ISO\s*5167(-\d+)?(?::(\d{4}))?", texto_norm, re.IGNORECASE)
    if m:
        abnt  = bool(m.group(1))
        parte = m.group(2) or "-2"
        ano   = m.group(3) or "2022"
        if abnt:
            return f"ABNT NBR ISO 5167{parte}:{ano}"
        return f"ISO 5167{parte}:{ano}"

    return "ISO 5167-2:2022"


def extrair_procedimento_tr(texto):
    """Extracts the gas meter run's dimensional measurement procedure and its description.

    The description is captured from the phrase "As medições foram re[a/i]lizadas
    ..." up to the mention of the standard (AGA 3 or ISO); the procedure
    identifier is the code "7.2 TM-003 Dimensional", with a fixed fallback if
    it isn't found in the text.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        dict: {"procedimento": str, "descricao": str}. "descricao" is empty
        if the phrase isn't found; "procedimento" is never empty (uses the
        fixed value "7.2 TM-003 Dimensional" as fallback).
    """
    texto_norm = re.sub(r"[‐–—‐‑‒–—]", "-", texto)
    m = re.search(
        r"(As\s+medi[çc][õo]es\s+foram\s+re[la][il]zadas.*?(?:AGA\s*3[^.\n\r]*|ISO\s+\d+[^.\n\r]*))",
        texto_norm,
        flags=re.IGNORECASE | re.DOTALL,
    )
    descricao = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    m_id = re.search(r"(7\.2\s+TM-003\s+Dimensional)", texto_norm, re.IGNORECASE)
    identificador = re.sub(r"\s+", " ", m_id.group(1)).strip() if m_id else "7.2 TM-003 Dimensional"
    return {"procedimento": identificador, "descricao": descricao}


def identificar_tr(texto):
    """Identifies whether the certificate is for a Gas Meter Run (Trecho Reto).

    Used by pdf/utils_parser.py to route the PDF. "Trecho Reto(?!\\s+cil)"
    avoids a false positive on "trecho reto cilíndrico do orifício", which
    appears in orifice plate certificates.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        bool: True if "Meter Run" or "Trecho Reto" (not followed by "cil")
        is found in the text.
    """
    return bool(re.search(r"Meter Run|Trecho Reto(?!\s+cil)", texto, re.IGNORECASE))


def extrair_nome_cliente_tr(texto):
    """Extracts the client name from the format "Name / Nome: PRIO Contact/Contato: metering@...".
    """
    m = re.search(r"Nome:\s*(.+?)\s+Contact\s*/\s*Contato:", texto, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extrair_local_tr(texto):
    """Extracts the calibration location name from within the "CALIBRATION LOCATION / Local de Calibração:" block.

    E.g.: block "CALIBRATION LOCATION / Local de Calibração:\\nName / Nome: FPSO Bravo".

    Returns:
        str: Location name, or None if the block or the "Nome:" field aren't found.
    """
    bloco = re.search(
        r"CALIBRATION LOCATION.*?:(.*?)(?=ITEM DESCRIPTION|$)",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not bloco:
        return None
    m = re.search(r"Nome:\s*([^\n\r]+)", bloco.group(1), re.IGNORECASE)
    return m.group(1).strip() if m else None


def extrair_data_medicao(texto):
    """Extracts the measurement/calibration date from the format "Measurement Date / Data da Medição: 12/11/2025".
    """
    m = re.search(r"(?:Measurement|Calibration) Date.*?:\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    return m.group(1) if m else None


def extrair_condicoes_ambientais_tr(texto):
    """Extracts the gas meter run's ambient temperature and humidity (e.g.: "Ambient Temperature / Temperatura Ambiente: 21,9°C").

    Returns:
        dict: {"temperatura_ambiente": float|None, "umidade_ambiente": float|None}.
    """
    resultado = {"temperatura_ambiente": None, "umidade_ambiente": None}

    m_temp = re.search(
        r"(?:Ambient\s+Temperature|Temperatura\s+Ambiente).*?:\s*([\d,\.]+)\s*°?C",
        texto,
        flags=re.IGNORECASE,
    )
    if m_temp:
        resultado["temperatura_ambiente"] = float(m_temp.group(1).replace(",", "."))

    m_umid = re.search(
        r"(?:Ambient\s+Humidity|Umidade\s+Ambiente).*?:\s*([\d,\.]+)\s*%",
        texto,
        flags=re.IGNORECASE,
    )
    if m_umid:
        resultado["umidade_ambiente"] = float(m_umid.group(1).replace(",", "."))

    return resultado


def material_tr(texto):
    """Extracts the pipe/orifice-carrier material, covering two observed formats.

    Old format: "Material of Pipe / Orifice Carrier: Carbon Steel - Coefficient: ...".
    New format: "Material of Pipe Carbon Steel - Coefficient: ...".

    Returns:
        str: Material found, or None if neither format matches.
    """
    m = re.search(
        r"Material(?:\s+of\s+Pipe)?(?:[^:\n]*:\s*|\s+)([A-Za-z][A-Za-z\s]+?)\s*-\s*Coefficient",
        texto,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def extrair_diametro_nominal_tr(texto):
    """Extracts the pipe's nominal diameter, covering two unit formats.

    Format 1: 'Nominal Diameter / Diâmetro Nominal: 2"' (inches).
    Format 2: 'Diameter / Diâmetro:  742,2 mm' (millimeters).

    Args:
        texto: Text extracted from the certificate.

    Returns:
        dict: {"valor": str, "unidade": str} with the raw value (not converted
        to float) and the unit found, or None if no format matches.
    """
    # Format 1: 'Nominal Diameter / Diâmetro Nominal: 2"'
    m = re.search(r'Nominal Diameter.*?:\s*([\d,\.]+)\s*"', texto, re.IGNORECASE)
    if m:
        return {"valor": m.group(1).strip(), "unidade": '"'}
    # Format 2: 'Diameter / Diâmetro:  742,2 mm'
    m = re.search(r'Diameter\s*/\s*Di[aâ]metro.*?:\s*([\d,\.]+)\s*(mm)', texto, re.IGNORECASE)
    if m:
        return {"valor": m.group(1).strip(), "unidade": m.group(2).strip()}
    return None


def extrair_tag_sistema_tr(texto):
    """Extracts the gas meter run measurement system's TAG (and, if present, SN).

    Covers two observed formats: "Identification / identificação: FX-1025-03"
    (no SN) and "Identification TAG/SN / Identificação TAG/NS: 776-FX-0010 /
    2021-ODS-0038-076" (TAG and SN separated by "/").

    Args:
        texto: Text extracted from the certificate.

    Returns:
        dict: {"tag": str|None, "sn": str|None}; both None if the pattern doesn't match.
    """
    m = re.search(
        r"Identification(?:\s+TAG/SN)?\s*/\s*Identifica[çc][aã]o(?:\s+TAG/NS)?\s*:\s*([A-Z0-9][A-Z0-9\-]+)(?:\s*/\s*([A-Z0-9][A-Z0-9\-]+))?",
        texto,
        flags=re.IGNORECASE,
    )
    if not m:
        return {"tag": None, "sn": None}
    return {
        "tag": m.group(1).strip(),
        "sn": m.group(2).strip() if m.group(2) else None,
    }


def extrair_componentes_tr(texto):
    """
    Extracts TAG and SN for the gas meter run's three components:
    - Orifice Carrier  -> PORTA PLACA
    - Upstream Pipe    -> TRECHO MONTANTE
    - Downstream Pipe  -> TRECHO JUSANTE

    Separation rule: the TAG/SN separator is the first slash preceded by a space
    (" /"), which distinguishes the separator "/" from the internal "/" ones
    (N/A, TR00916-21/2.1). If there's no separator -> TAG = "NI", SN = full value.
    SN ends before \n or lowercase-letter text; allows an exact positional suffix
    of 1 uppercase letter + 1 digit (e.g.: M1, J1).

    Args:
        texto: Text extracted from the certificate.

    Returns:
        list[dict]: One {"tipo", "tag", "sn"} dict per component found in the
        text; components not mentioned in the certificate simply don't
        appear in the list.
    """
    padroes = [
        (r"Orifice Carrier\s*/\s*Porta Placa", "PORTA PLACA"),
        (r"Upstream Pipe", "TRECHO MONTANTE"),
        (r"Downstream Pipe", "TRECHO JUSANTE"),
        (r"19\s+Tube\s+Bundle\s+Flow\s+Straightener", "CONDICIONADOR DE FLUXO"),
        (r"Zanker", "CONDICIONADOR DE FLUXO"),
    ]

    # TAG: compact value (alphanumeric + /-.) before the " /" separator
    # SN:  same pattern + optional suffix of exactly [A-Z][0-9] (e.g.: M1, J1)
    _tag = r"[A-Z0-9][A-Z0-9/\-\.]*"
    _sn  = r"[A-Z0-9][A-Z0-9/\-\.]*(?:\s+[A-Z][0-9])?"
    # Fully absent: N/A (or similar) with no valid SN following
    _ausente = r"(?:N/A|N[aã]o\s+consta|Not\s+present|N/C)(?!\s*/\s*[A-Z0-9])"
    # TAG values that indicate absence (but an SN may still exist)
    _tag_ausente = {"N/A", "N/C"}

    componentes = []
    for padrao_nome, tipo in padroes:
        # Entire identification absent → component present but without TAG or SN
        if re.search(
            padrao_nome + r"[^\n]*?TAG\s*/\s*SN\s*:\s*" + _ausente,
            texto,
            flags=re.IGNORECASE,
        ):
            componentes.append({"tipo": tipo, "tag": "NI", "sn": "NI"})
            continue

        m = re.search(
            padrao_nome
            + r"[^\n]*?TAG\s*/\s*SN\s*:\s*"
            + rf"(?:({_tag})\s+/\s*)?"  # Optional TAG: value before the first " /"
            + rf"({_sn})",              # SN: compact value + positional suffix
            texto,
            flags=re.IGNORECASE,
        )
        if m:
            tag_raw = m.group(1).strip() if m.group(1) else "NI"
            sn      = m.group(2).strip() if m.group(2) else "NI"
            tag     = "NI" if tag_raw.upper() in _tag_ausente else tag_raw
            componentes.append({"tipo": tipo, "tag": tag, "sn": sn})

    return componentes


_ZANKER_AUSENTE = {"N/A", "NÃO CONSTA", "NAO CONSTA", "NOT PRESENT", "N/C"}

def extrair_condicionador_fluxo(texto):
    """Identifies the gas meter run's flow conditioner: "Zanker", "19 tubos" or "Nenhum".

    If the "Zanker TAG / SN:" field exists but indicates absence (e.g.: "N/A",
    "Não consta"), returns "Nenhum"; if the field doesn't exist but the text
    mentions "19 tubes"/"19 tubos", returns "19 tubos".

    Returns:
        str: "Zanker", "19 tubos" or "Nenhum" (default when nothing is found).
    """
    m = re.search(r"Zanker\s+TAG\s*/\s*SN\s*:\s*([^\n\r]+)", texto, re.IGNORECASE)
    if m:
        val = m.group(1).strip().upper()
        return "Nenhum" if val in _ZANKER_AUSENTE else "Zanker"
    if re.search(r"19\s+(?:tubes?|tubos?)", texto, re.IGNORECASE):
        return "19 tubos"
    return "Nenhum"


def extrair_campos_tr(texto):
    """Builds the complete fields dictionary for a Gas Meter Run (Trecho Reto) certificate.

    Combines this module's local extractors (standard, procedure, client,
    location, measurement date, ambient conditions, material, diameter,
    system and component TAG/SN, flow conditioner) with generic extractors
    from pdf.parser_certificados and the expansion coefficient from
    pdf.parser_po. The certificate's reference TAG/SN is the PORTA PLACA
    component's, with a fallback to the CONDICIONADOR DE FLUXO if the
    orifice carrier isn't found.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        dict: Certificate fields ready to fill in the AC model.
    """
    texto = re.sub(r"[‐–—]", "-", texto)
    certificado = extrair_certificado(texto)
    _, report_date = extrair_datas(texto)
    data_medicao = extrair_data_medicao(texto)
    nome_cliente = extrair_nome_cliente_tr(texto)
    endereco_cli = endereco_cliente(texto)
    local = extrair_local_tr(texto)
    exec_sig = separar_signatario(extrair_assinaturas(texto), SIGNATARIOS_VALIDOS)
    cond_amb = extrair_condicoes_ambientais_tr(texto)
    padroes = extrair_padroes(texto)
    material = material_tr(texto)
    coef = coeficiente_dilatacao(texto)
    diametro_t = extrair_diametro_nominal_tr(texto)
    id_sistema = extrair_tag_sistema_tr(texto)
    componentes = extrair_componentes_tr(texto)
    condicionador = extrair_condicionador_fluxo(texto)

    porta_placa    = next((c for c in componentes if c["tipo"] == "PORTA PLACA"), {})
    cond_componente = next((c for c in componentes if c["tipo"] == "CONDICIONADOR DE FLUXO"), {})
    componente_ref  = porta_placa or cond_componente

    return {
        "certificado": certificado,
        "instrumento": "Gas Meter Run",
        "data_calibracao": data_medicao,
        "report_date": report_date,
        "cliente": nome_cliente,
        "endereco_cliente": endereco_cli,
        "local": local,
        "exec_sig": exec_sig,
        "cond_amb": cond_amb,
        "padroes_utilizados": padroes,
        "tag": componente_ref.get("tag") or id_sistema["tag"],
        "sn_inst": componente_ref.get("sn") or id_sistema["sn"],
        "material": material,
        "coef": coef,
        "norma": extrair_norma_tr(texto),
        "diametro_tubo": diametro_t.get("valor") if diametro_t else None,
        "diametro_tubo_unidade": diametro_t.get("unidade", '"') if diametro_t else '"',
        "procedimento": extrair_procedimento_tr(texto),
        "tag_sistema": id_sistema["tag"],
        "componentes": componentes,
        "condicionador_fluxo": condicionador,
    }