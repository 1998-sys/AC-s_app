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
    """Colapsa qualquer sequência de espaços/quebras de linha em um único espaço."""
    return re.sub(r"\s+", " ", texto)


def extrair_numero_evaluation(texto):
    """Extrai o número do Evaluation Report (ex.: 'Nº 25-ODS-...-ER').

    Compartilhado entre parser_po_ER.py e parser_tr_ER.py — a única diferença
    entre os dois certificados é o restante do documento, não este campo.
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
