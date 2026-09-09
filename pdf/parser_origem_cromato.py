# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_origem_cromato
# Created       : 25-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses chromatography reports from Origem Energia Alagoas's internal lab (LIMS Report Builder), extracting gas properties and their uncertainties.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re


def _normalizar_numero(valor):
    """Converts a number from the Origem report (decimal point, sometimes
    scientific notation, e.g., '5E-05') into the Brazilian comma format
    used throughout the rest of the app (e.g., '0,00005').

    Args:
        valor: String with the number in the report's original format.

    Returns:
        str: Number in PT-BR format (decimal comma), or the original `valor`
        unchanged if it cannot be converted to float; None if `valor` is None.
    """
    if valor is None:
        return None
    valor = valor.strip()
    try:
        numero = float(valor.replace(",", "."))
    except ValueError:
        return valor
    texto = f"{numero:.10f}".rstrip("0").rstrip(".")
    if not texto or texto == "-":
        texto = "0"
    return texto.replace(".", ",")


def identificar_origem_cromato(texto):
    """Identifies the chromatography report from Origem Energia Alagoas's
    internal lab (LIMS "Report Builder"/mylimsweb.cloud) — a layout
    completely different from the SGS report (see parser_sgs.py).

    Returns:
        bool: True if the text contains that lab's characteristic header,
        False otherwise (including when `texto` is empty).
    """
    if not texto:
        return False
    return bool(re.search(
        r"Laborat[óo]rio\s+Cromatografia\s*-\s*Origem\s+Energia\s+Alagoas",
        texto, re.IGNORECASE
    ))


def extrair_empresa_origem(texto):
    """Extracts the name of the lab/company that owns the report.

    <EMPRESA> here is the lab/company that owns the report itself — unlike
    the SGS report, this one has no external "Cliente:" (the "Cliente:" that
    appears in the report is the internal collection station, not an ODS
    client company).

    Returns:
        str: Name extracted after "Laboratório Cromatografia - ", or None if
        the pattern is not found.
    """
    if not texto:
        return None
    m = re.search(r"Laborat[óo]rio\s+Cromatografia\s*-\s*(.+)", texto, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extrair_certificado_origem(texto):
    """Extracts the Origem analysis report number.

    The report number appears with small formatting variations throughout
    the document (e.g., "15833/2026.0.A" in the main report and
    "15833/2026.0" in the supplementary properties report) — uses the most
    specific variant (the longest one).

    Returns:
        str: The longest report number among the occurrences found, or None
        if no occurrence is found.
    """
    if not texto:
        return None
    candidatos = [
        m.strip() for m in re.findall(
            r"Relat[óo]rio de An[áa]lises\s+([^\n]+)", texto, re.IGNORECASE
        ) if m.strip()
    ]
    return max(candidatos, key=len) if candidatos else None


def _linha_propriedade(texto, nome_exato):
    """Searches the "Resultados Analíticos" table for the row whose analysis is
    exactly `nome_exato` (e.g., "Massa Molar", "Fator de
    compressibilidade - CL") and returns (valor, incerteza) from the
    Resultado/Incerteza columns. The value is only accepted if it comes right
    after the name, with nothing in between — this avoids matching "Densidade
    Absoluta" with the "Densidade Absoluta - CL ..." row.

    Args:
        texto: Report text extracted.
        nome_exato: Analysis name, exactly as it appears in the table.

    Returns:
        tuple: (valor, incerteza) as raw strings (not yet normalized by
        _normalizar_numero), or (None, None) if the row is not found.
    """
    pat = re.compile(
        r"^[ \t]*" + re.escape(nome_exato) + r"[ \t]+"
        r"(?P<valor>[<>]?\s*[\d.,]+(?:[Ee][+-]?\d+)?)"
        r"[ \t]*(?:[A-Za-zµ/³%°]+)?[ \t]+"
        r"\S+[ \t]+\S+[ \t]+.+?[ \t]+"
        r"(?P<incerteza>[\d.,]+(?:[Ee][+-]?\d+)?)[ \t]+"
        r"(?:NBR|ISO|ASTM)",
        re.IGNORECASE | re.MULTILINE
    )
    m = pat.search(texto)
    if not m:
        return None, None
    return m.group("valor").strip(), m.group("incerteza").strip()


# (analysis name in the report -> destination list) — replicates the same
# standard/sampling (CL) split used for the SGS report, see xml_cromato.py
_CAMPOS_ORIGEM = [
    ("Massa Molar", "padrao"),
    ("Densidade Absoluta", "padrao"),
    ("Fator de compressibilidade - CL", "amostragem"),
    ("Viscosidade do gás - CL", "amostragem"),
    ("Coeficiente Isentrópico - CL", "amostragem"),
]


def extrair_campos_cromato_origem(texto):
    """Extracts the chromatography fields from the Origem Energia Alagoas
    report in the same format used by extrair_campos_cromato
    (pdf/parser_sgs.py), to feed xml_cromatografia() without requiring any
    changes there.

    Iterates over _CAMPOS_ORIGEM, looking up each property with
    _linha_propriedade and distributing the result between the "padrao" and
    "amostragem" lists as mapped.

    Args:
        texto: Report text extracted.

    Returns:
        dict: Keys "empresa", "certificado", "propriedades_pad" and
        "propriedades_amost", in the same format returned by
        pdf.parser_sgs.extrair_campos_cromato.
    """
    t = (texto or "").replace("\r\n", "\n").replace("\r", "\n")

    propriedades_padrao = []
    propriedades_amostragem = []
    destinos = {"padrao": propriedades_padrao, "amostragem": propriedades_amostragem}

    for nome, destino in _CAMPOS_ORIGEM:
        valor, incerteza = _linha_propriedade(t, nome)
        if valor is None:
            continue
        destinos[destino].append({
            "propriedade": nome,
            "referencia": None,
            "valor": _normalizar_numero(valor),
            "incerteza": _normalizar_numero(incerteza),
        })

    return {
        "empresa": extrair_empresa_origem(t),
        "certificado": extrair_certificado_origem(t),
        "propriedades_pad": {"propriedades_padrao": propriedades_padrao},
        "propriedades_amost": {"propriedades_amostragem": propriedades_amostragem},
    }
