# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_tr_ER
# Created       : 24-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses Gas Meter Run Evaluation Report (ER) PDFs, extracting the accept/reject results for cylindricity, roughness and length checks along the meter run.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re
from pdf.parser_er_common import extrair_numero_evaluation, normalizar_espacos


def _normalizar(texto):
    """Local shortcut to pdf.parser_er_common.normalizar_espacos (collapses spaces/line breaks).
    """
    return normalizar_espacos(texto)


def _to_aprovado(s):
    """Translates the raw accept/reject result (EN/PT) to "Sim"/"Não".

    Args:
        s: String captured by the regex, e.g., "Accepted", "Not Accepted", "aceito".

    Returns:
        str: "Sim" if accepted, "Não" if rejected ("Not Accepted"/"não aceito"
        take precedence over "Accepted"/"aceito" to avoid a false positive via
        substring match), or "NÃO ENCONTRADO" if `s` is empty or unrecognized.
    """
    if not s:
        return "NÃO ENCONTRADO"
    s = s.strip().lower()
    if "not accepted" in s or "não aceito" in s:
        return "Não"
    if "accepted" in s or "aceito" in s:
        return "Sim"
    return "NÃO ENCONTRADO"


def extrair_numero_evaluation_tr(texto):
    """Extracts the meter run's Evaluation Report number (delegates to pdf.parser_er_common.extrair_numero_evaluation).
    """
    return extrair_numero_evaluation(texto)


def extrair_d_er(texto):
    """Extracts the value and uncertainty of the measured internal diameter D of the meter run.

    Recognizes the pattern from Item 6.4.2 of the report, e.g., "Item 6.4.2
    Measured Internal diameter medium D @ 20°C:\\n52.57 ± 0.05 mm".

    Args:
        texto: Text extracted from the ER report.

    Returns:
        dict: {"valor": str, "incerteza": str} with decimal point, or None
        if the pattern is not found.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Item 6\.4\.2.*?D\s*@\s*20.*?°C\s*:\s*([\d,]+)\s*[±+\-]\s*([\d,]+)\s*mm",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        return {
            "valor": m.group(1).replace(",", "."),
            "incerteza": m.group(2).replace(",", "."),
        }
    return None


# ── Upstream cylindricity ──────────────────────────────────────────────────

def resultado_cilindricidade_montante_alem_10D(texto):
    """Extracts the accept/reject result of the upstream cylindricity, beyond 10D (Item 6.4.3).

    Recognizes the passage "Not exceed 2% of D ... Accepted/Not Accepted".

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Not exceed 2%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_cilindricidade_montante_2_10D(texto):
    """Extracts the accept/reject result of the upstream cylindricity, between 2D and 10D (Item 6.4.3).

    The "Not exceed 0.3% of D" result appears on the same line as the
    "beyond 10D" result (Not exceed 2%); this function captures the second
    result on the line, referring to the 2-10D range.

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Not exceed 2%.*?(\bNot Accepted\b|\bAccepted\b).*?"
        r"Not exceed 0,3%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(2)) if m else "NÃO ENCONTRADO"


def resultado_rugosidade_montante_2_10D(texto):
    """Extracts the accept/reject result of the upstream roughness, between 2D and 10D (Item 5.3.1).

    Recognizes the passage "Roughness evaluation 2-10D Upstream ... Medium
    roughness: Accepted/Not Accepted".

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Roughness evaluation 2-10D Upstream.*?Medium roughness[^A-Za-z]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_comprimento_montante(texto):
    """Extracts the accept/reject result of the upstream pipe length (Item 6.3.3.3).

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Item 6\.3\.3\.3.*?Pipe Lenght Upstream.*?Result[:\s]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


# ── Downstream ─────────────────────────────────────────────────────────────

def resultado_cilindricidade_jusante(texto):
    """Extracts the accept/reject result of the downstream cylindricity (Item 6.4.6).

    Captures the first result of the line "Not exceed 3% of D ... Accepted/Not Accepted".

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Not exceed 3%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_rugosidade_jusante(texto):
    """Extracts the accept/reject result of the downstream roughness (Item 5.3.1).

    The roughness shares the "Not exceed 3%" line with the downstream
    cylindricity; this function captures the second result of the line.

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(r"Not exceed 3%.*", t, flags=re.IGNORECASE)
    if m:
        resultados = re.findall(r"\bNot Accepted\b|\bAccepted\b", m.group(0), re.IGNORECASE)
        if len(resultados) >= 2:
            return _to_aprovado(resultados[1])
    return "NÃO ENCONTRADO"


def resultado_comprimento_tomada_temp(texto):
    """Extracts the accept/reject result of the temperature tap length (Item 5.4.4.1).

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Item 5\.4\.4\.1.*?Result[:\s]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_comprimento_acidente_jusante(texto):
    """Extracts the accept/reject result of the length to the first downstream fitting (Item 7.4.1).

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Item 7\.4\.1.*?Result[:\s]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


# ── Orifice Carrier ─────────────────────────────────────────────────────────

def resultado_cilindricidade_0_2D(texto):
    """Extracts the accept/reject result of the orifice carrier cylindricity, from 0 to 2D upstream (Item 6.4.1).

    Captures the first result after "Not exceed 0.3%" within the context of
    Item 6.4.1 (page 3 of the report).

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Item 6\.4\.1.*?Not exceed 0,3%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_rugosidade_0_2D(texto):
    """Extracts the accept/reject result of the orifice carrier roughness, from 0 to 2D (Item 5.3.1).

    Captures the second result of the "Not exceed 0.3%" line within the
    context of Item 6.4.1 (page 3 of the report).

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _to_aprovado.
    """
    t = _normalizar(texto)
    m = re.search(r"Item 6\.4\.1.*?Not exceed 0,3%.*", t, flags=re.IGNORECASE)
    if m:
        resultados = re.findall(r"\bNot Accepted\b|\bAccepted\b", m.group(0), re.IGNORECASE)
        if len(resultados) >= 2:
            return _to_aprovado(resultados[1])
    return "NÃO ENCONTRADO"


# ── Main ────────────────────────────────────────────────────────────────────

def extrair_campos_er_tr(texto):
    """Builds the complete results dictionary of the meter run Evaluation Report (ER).

    Orchestrates every extractor in this module (ER number, diameter D and
    uncertainty, and the upstream, downstream and orifice-carrier accept/reject
    results for cylindricity, roughness and length).

    Args:
        texto: Text extracted from the ER report.

    Returns:
        dict: Keys with the results of each check. "Diametro_D" is the
        result of Item 6.4.1 (0-2D upstream cylindricity), which validates
        the positions where D is measured for the flow computer.
    """
    return {
        "Numero_Evaluation": extrair_numero_evaluation_tr(texto),
        "d_er": extrair_d_er(texto),
        "Cil_Montante_Alem_10D": resultado_cilindricidade_montante_alem_10D(texto),
        "Cil_Montante_2_10D": resultado_cilindricidade_montante_2_10D(texto),
        "Rug_Montante_2_10D": resultado_rugosidade_montante_2_10D(texto),
        "Comp_Montante": resultado_comprimento_montante(texto),
        "Cil_Jusante": resultado_cilindricidade_jusante(texto),
        "Rug_Jusante": resultado_rugosidade_jusante(texto),
        "Comp_Tomada_Temp": resultado_comprimento_tomada_temp(texto),
        "Comp_Acidente_Jusante": resultado_comprimento_acidente_jusante(texto),
        "Diametro_D": resultado_cilindricidade_0_2D(texto),
        "Rug_0_2D": resultado_rugosidade_0_2D(texto),
    }