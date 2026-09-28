# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.full_ac_templates
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Category title resolution and business-day date helper shared by the AC Secundário generators (PRIO/YINSON/YINSON ATLANTA — see form.utils_print_ac_secundario_html, migrated 2026-09-28 from this module's former Excel/win32com pipeline).
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from datetime import datetime, timedelta


def _adicionar_dia_util(data):
    """Adds one day to `data` and pushes the result to the next business day if it falls on a weekend.

    Args:
        data: Reference date.

    Returns:
        datetime: `data` + 1 day, advanced by 1 or 2 more days if the result
        falls on a Saturday or Sunday (guaranteeing a business-day return).
    """
    data += timedelta(days=1)
    if data.weekday() == 5:  # Saturday
        data += timedelta(days=2)
    elif data.weekday() == 6:  # Sunday
        data += timedelta(days=1)
    return data


# Each category group maps to the same title across all clients in this
# family — except the "pressao" case when `permitir_split_pt_pdt` is
# enabled (currently only PRIO), which distinguishes PT from PDT by the
# maximum calibrated range.
_GRUPOS_CATEGORIA = [
    (("TERMORRESISTÊNCIA PT-100 - 2 FIOS",
      "TERMORRESISTÊNCIA PT-100 - 3 FIOS",
      "TERMORRESISTÊNCIA PT-100 - 4 FIOS"), "temperatura"),
    (("TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA",
      "TERMÔMETRO ANALÓGICO",
      "TERMÔMETRO DIGITAL"), "temperatura"),
    (("TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA",
      "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA",
      "MANOMETRO DIGITAL",
      "MANOMETRO ANALÓGICO",
      "MANOMETRO DIGITAL ABSOLUTO"), "pressao"),
    (("MANOMETRO DIFERENCIAL DIGITAL",
      "MANOMETRO DIFERENCIAL ANALÓGICO"), "pressao_diferencial"),
]

_TITULOS_CATEGORIA = {
    "temperatura": "Análise Crítica de Calibração dos Sensores de Temperatura",
    "pressao": "Análise Crítica de Calibração dos Transmissores de Pressão",
    "pressao_diferencial": "Análise Crítica de Calibração dos Transmissores de Pressão Diferencial",
}


def _titulo_categoria(categoria, permitir_split_pt_pdt, max_range):
    """Resolves the critical-analysis title corresponding to the instrument category.

    Walks through the category groups (`_GRUPOS_CATEGORIA`) until it finds
    the given category; when `permitir_split_pt_pdt` is enabled and the
    category is the generic pressure transmitter, it distinguishes PT from
    PDT by the maximum calibrated range (`max_range` <= 250 becomes PDT).

    Args:
        categoria: Instrument category name (already upper case).
        permitir_split_pt_pdt: If True, enables the PT/PDT distinction by range.
        max_range: Maximum calibrated range of the instrument (used only in the PT/PDT split).

    Returns:
        str: Corresponding title, or None if the category is not recognized.
    """
    for categorias, grupo in _GRUPOS_CATEGORIA:
        if categoria not in categorias:
            continue

        if (
            permitir_split_pt_pdt
            and grupo == "pressao"
            and categoria == "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA"
        ):
            try:
                max_range_float = float(max_range)
            except (TypeError, ValueError):
                max_range_float = None
            if max_range_float is not None and max_range_float <= 250:
                return _TITULOS_CATEGORIA["pressao_diferencial"]

        return _TITULOS_CATEGORIA[grupo]

    return None
