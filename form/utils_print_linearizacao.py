# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_linearizacao
# Created       : 31-07-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Client detection, signature-name lookup and previous-point pairing shared by the Linearização/Falha Presumida/AC Primário reports (see form.utils_print_linearizacao_html, form.utils_print_falha_presumida_html, form.utils_print_ac_primario_html). Used to fill Template_Linearizacao.xlsx via Excel COM until the 2026-09-28 migration to HTML/WebView2.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import openpyxl
import os
from datetime import datetime

# Signature block cells in Template_Linearizacao.xlsx, sheet "Linearização"
# — the template ships with a fixed pair of default names, read here only to
# pre-fill the rename prompt shown before generating a report (see
# ler_nomes_assinatura / PdfProcessingService._processar_xml_ft).
CELLS = {
    "elaborado_nome": "F96",
    "verificado_nome": "N96",
}


def _data_br(data_iso: str) -> str:
    """Converts a date from ISO format (YYYY-MM-DD) to BR format (DD/MM/YYYY).

    Args:
        data_iso: Date in ISO format, e.g. "2026-04-25".

    Returns:
        str: Date in "DD/MM/YYYY" format, e.g. "25/04/2026"; returns
        `data_iso` unchanged if it cannot be parsed.
    """
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return data_iso


# Known clients recognized in the Linearização/Falha Presumida "Cliente"
# field — matched as a case-insensitive substring, so a raw XML value like
# "Prio Forte S/A" or a folder segment like ".../PRIO/..." both resolve to
# the same normalized "PRIO". Includes "ODS" itself: on some certificates
# CLIENTE/NOME names ODS as the calibration lab's own contracting client
# (e.g. "ODS do Brasil Sistemas de Medição LTDA") rather than the end oil
# company — a legitimate value for this field, not a detection error.
CLIENTES_CONHECIDOS = ("PRIO", "YINSON", "ORIGEM", "SBM", "PETROBRAS", "ODS")


def identificar_cliente(nome_cliente_xml: str, caminho_xml: str) -> str:
    """Suggests a default "Cliente" value from the certificate's own CLIENTE/NOME text, falling back to the file path.

    `gui.pdf_service` uses the result only as a pre-selected default for
    its "Cliente" prompt field (a fixed PRIO/YINSON/ORIGEM selection, since
    that value drives AC template routing) — if this returns something
    outside that set (e.g. "ODS", or a client only recognized via the
    broader `CLIENTES_CONHECIDOS` list), the field just starts unselected
    and the user picks one of the 3 explicitly.

    Args:
        nome_cliente_xml: raw text of the XML's CLIENTE/NOME element (see
            `xml_extractor_FT.extrair_dados_ft`'s "cliente_xml" key) —
            checked first since it doesn't depend on where the file happens
            to be saved on disk (a loose/dropped file saved to a generic
            folder has no client name in its path at all).
        caminho_xml: file path (e.g. ".../PRIO/..."), used as a fallback
            when the XML's own name doesn't contain a recognized client.

    Returns:
        str: recognized client name (one of `CLIENTES_CONHECIDOS`), or an
        empty string if neither source has one.
    """
    for fonte in (nome_cliente_xml or "", caminho_xml or ""):
        fonte_norm = fonte.upper().replace("\\", "/")
        for cliente in CLIENTES_CONHECIDOS:
            if cliente in fonte_norm:
                return cliente
    return ""


def contexto_db(tag: str):
    """Looks up application and system in the instrument registry by TAG.

    Used only as the pre-filled value for the prompt that asks the user for
    these two fields (see PdfProcessingService._processar_xml_ft); flow
    meters are usually not in this registry, so this tends to come back empty.

    Args:
        tag: Instrument TAG to look up.

    Returns:
        tuple: (aplicacao, sistema), each as a string (empty if not found
        or on a lookup error).
    """
    try:
        from data.utils_db import buscar_instrumento_por_tag
        inst = buscar_instrumento_por_tag(tag)
        if inst:
            return inst.get("aplicacao") or "", inst.get("sistema") or ""
    except Exception:
        pass
    return "", ""


def ler_nomes_assinatura():
    """Reads the default "Elaborado por"/"Verificado por" names baked into Template_Linearizacao.xlsx.

    Used only to pre-fill the rename prompt shown to the user before
    generating the report (see PdfProcessingService._processar_xml_ft) —
    the template ships with a fixed pair of names that most reports reuse
    as-is.

    Returns:
        tuple: (elaborado, verificado), each as a string (empty if the
        corresponding template cell has no value).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_template = os.path.join(base_dir, "templates", "Template_Linearizacao.xlsx")
    wb = openpyxl.load_workbook(caminho_template, read_only=True)
    try:
        ws = wb["Linearização"]
        return ws[CELLS["elaborado_nome"]].value or "", ws[CELLS["verificado_nome"]].value or ""
    finally:
        wb.close()


def parear_pontos_anterior(pontos_atual: list, pontos_anterior: list) -> list:
    """Pairs each current-certificate point with the full previous-certificate point at the nearest flow rate.

    Confirmed business rule (originally for Falha Presumida, now reused by
    the primary meter AC too — see form/utils_print_ac_primario_html.py):
    these reports compare the same meter across two calibration events, not
    by matching table position/index — when the calibrated range differs
    between the two certificates, the nearest flow point is used (no
    interpolation, and no validation that the two certificates share the
    same meter serial number — a spare/reserve meter with a different
    serial number can legitimately be installed at the same measurement
    point).

    Args:
        pontos_atual: current certificate's points (`dados["pontos"]`), in
            the same order they were written to the Linearização table.
        pontos_anterior: previous certificate's points (`dados["pontos"]`
            from `extrair_dados_ft` on the previous XML).

    Returns:
        list[dict]: one previous-certificate point per `pontos_atual`
        entry (same shape as `extrair_dados_ft`'s "pontos" — vazao,
        meter_factor, erro_pct, incerteza, repetibilidade — so callers can
        read whichever fields they need), from the `pontos_anterior` entry
        with the closest "vazao" value.

    Raises:
        ValueError: if `pontos_anterior` is empty (nothing to pair against).
    """
    if not pontos_anterior:
        raise ValueError(
            "O certificado da calibração anterior não tem pontos de "
            "calibração para comparar."
        )

    resultado = []
    for p_atual in pontos_atual:
        vazao_atual = p_atual["vazao"]
        mais_proximo = min(
            pontos_anterior,
            key=lambda p: abs(p["vazao"] - vazao_atual),
        )
        resultado.append(mais_proximo)
    return resultado
