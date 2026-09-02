# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_er_common
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Shared helpers for the Evaluation Report (ER) parsers, extracting the report number and normalizing whitespace.
#                 Funções auxiliares compartilhadas pelos parsers de Relatório de Avaliação (ER), extraindo o número do relatório e normalizando espaços.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re

from xml_model.xml_generator import normalizar_certificado


def normalizar_espacos(texto):
    """Collapses any run of spaces/line breaks into a single space.

    Args:
        texto: Input text, potentially with multiple spaces/line breaks.

    Returns:
        str: Text with all whitespace sequences collapsed into a single one.
    """
    return re.sub(r"\s+", " ", texto)


def extrair_numero_evaluation(texto):
    """Extracts the Evaluation Report number from the certificate text.

    Recognizes patterns such as "Nº 25-ODS-...-ER" (with or without the
    "RELATÓRIO DE AVALIAÇÃO" prefix), first normalizing the different
    dash/hyphen variants (‐, -, –, —) to a plain hyphen before applying the regex.

    Shared between parser_po_ER.py and parser_tr_ER.py — the only difference
    between the two certificates is the rest of the document, not this field.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        str: Normalized Evaluation Report number, or None if not found.
    """
    texto = re.sub(r"[‐\-–—]", "-", texto)
    m = re.search(
        r"(?:RELATÓRIO\s+DE\s+AVALIAÇÃO\s+)?N[º°\.]?\s*([A-Z0-9._\- ]+?)\s*-?\s*\bER\b",
        texto,
        flags=re.IGNORECASE,
    )
    if m:
        return normalizar_certificado(m.group(1).strip())
    return None
