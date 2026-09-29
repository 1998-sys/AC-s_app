# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ac_primario
# Created       : 15-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Acceptance criteria and header-field helpers shared by the primary flow meter Critical Analysis (AC) report (see form.utils_print_ac_primario_html). Used to fill Template_AC_PRIM_PRIO.xlsx via Excel COM until the 2026-09-28 migration to HTML/WebView2.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from datetime import datetime

# Fixed values (see tasks/TAREFAS_ac_medidor_primario_prio.md — assumed
# from the template's own example, not present as a distinct field in the
# flow meter XML schema).
INSTRUMENTO_PADRAO = "Medidor de Vazão"
UNIDADE_CERTIFICADO_PADRAO = "SI"

# Confirmed with the user (2026-09-15) — percentage points, matching the
# template's own number format ("0.00", not "0.00%": 0.2 means "0,2%").
CRITERIOS_ACEITACAO = {
    "Master Meter": {
        "erro_maximo": 0.2,
        "repetibilidade": 0.02,
        "validacao_mf": None,  # does not apply
    },
    "Fiscal": {
        "erro_maximo": 0.2,
        "repetibilidade": 0.05,
        "validacao_mf": 0.25,
    },
    "Transferência de Custódia": {
        "erro_maximo": 0.2,
        "repetibilidade": 0.05,
        "validacao_mf": 0.25,
    },
    "Apropriação": {
        "erro_maximo": 0.6,
        "repetibilidade": 0.4,
        "validacao_mf": 2.0,
    },
    "Operacional": {
        "erro_maximo": 0.6,
        "repetibilidade": 0.4,
        "validacao_mf": 2.0,
    },
}


def _data_iso_para_data(data_iso: str):
    """Parses an ISO date string (YYYY-MM-DD) into a `datetime` object.

    Args:
        data_iso: Date in ISO format, e.g. "2025-09-26".

    Returns:
        datetime.datetime: parsed date, or None if `data_iso` is empty or
        cannot be parsed.
    """
    if not data_iso:
        return None
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d")
    except ValueError:
        return None


def _validade_padrao_texto(padroes: list) -> str:
    """Builds the multi-line "Validade Padrão" text from the certificate's reference standards.

    Args:
        padroes: list of {"identificador", "validade"} dicts (see
            `xml_extractor_FT.extrair_dados_ft`'s "padroes" key) — one per
            reference standard used in the calibration.

    Returns:
        str: one "<identificador>: <validade DD/MM/YY>" line per standard,
        joined with "\\n" (matches the template's own example format,
        e.g. "Padrão 16 HV: 23/01/26\\nPadrão 15 HV: 23/03/25"); empty
        string if there are no standards.
    """
    linhas = []
    for p in padroes or []:
        data = _data_iso_para_data(p.get("validade"))
        validade_fmt = data.strftime("%d/%m/%y") if data else (p.get("validade") or "")
        identificador = p.get("identificador") or ""
        if identificador or validade_fmt:
            linhas.append(f"{identificador}: {validade_fmt}".strip(": "))
    return "\n".join(linhas)
