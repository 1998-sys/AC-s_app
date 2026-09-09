# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_gt_technology
# Created       : 09-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses GT Technology chromatography reports ("Boletim de Resultado de Análise"), extracting client, certificate number and the gas properties used in the flow calculation.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re

from pdf.parser_gt_quimica import extrair_certificado_gt, extrair_cliente_gt


def identificar_gt_technology(texto):
    """Identifies a GT Technology chromatography report ("Boletim de Resultado de Análise").

    Args:
        texto: Report text extracted.

    Returns:
        bool: True if the text carries GT Technology's site footer
        ("gttechnology.com.br"), False otherwise (including when `texto` is empty).
    """
    if not texto:
        return False
    return "gttechnology" in texto.lower()


def _valor_incerteza(bloco, nome_exato):
    """Finds, within `bloco`, the row "nome_exato <método ref.> <valor> <unidade ou -> <incerteza>".

    Args:
        bloco: Text of the single "Propriedades do Gás" table (see
            `extrair_campos_cromato_gt_technology`).
        nome_exato: Property name, exactly as it appears in the report —
            unlike GT Química's report (two separate tables), this lab
            puts the condition directly in the name (e.g. "Fator Z
            (Operação)", "Densidade Absoluta (Padrão)").

    Returns:
        tuple: (valor, incerteza) as raw PT-BR strings (decimal comma,
        already in the report's own format — no conversion needed), or
        (None, None) if the row isn't found.
    """
    pat = re.compile(
        r"^[ \t]*" + re.escape(nome_exato) + r"[ \t]+1[A-D][ \t]+"
        r"(?P<valor>[\d.,]+)[ \t]+\S+[ \t]+"
        r"(?P<incerteza>[\d.,]+)[ \t]*$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = pat.search(bloco)
    if not m:
        return None, None
    return m.group("valor").strip(), m.group("incerteza").strip()


# (property name in the report, destination list) — unlike GT Química (two
# separate tables), this lab has a single "Propriedades do Gás" table with
# the condition embedded in the name itself. "Fator Z" is renamed to "Fator
# de Compressibilidade" so xml_cromato.py's keyword matching
# (_buscar_propriedade) recognizes it without needing any change there —
# the rest already match as-is (e.g. "Viscosidade (Operação)" already
# contains "VISCOSIDADE").
_CAMPOS = [
    ("Peso Molecular Médio", "padrao", None),
    ("Densidade Absoluta (Padrão)", "padrao", "Densidade Absoluta"),
    ("Fator Z (Operação)", "amostragem", "Fator de Compressibilidade"),
    ("Viscosidade (Operação)", "amostragem", None),
    ("Coeficiente Isentrópico (Operação)", "amostragem", None),
]


def extrair_campos_cromato_gt_technology(texto):
    """Extracts the chromatography fields from a GT Technology report in the same format used by extrair_campos_cromato (pdf/parser_sgs.py).

    Args:
        texto: Report text extracted.

    Returns:
        dict: Keys "empresa", "certificado", "propriedades_pad" and
        "propriedades_amost", in the same format returned by
        pdf.parser_sgs.extrair_campos_cromato.
    """
    t = (texto or "").replace("\r\n", "\n").replace("\r", "\n")

    m_ini = re.search(r"Propriedades do G[aá]s\b", t, re.IGNORECASE)
    bloco = ""
    if m_ini:
        start = m_ini.end()
        m_fim = re.search(r"^Observa[cç][õo]es\b", t[start:], re.IGNORECASE | re.MULTILINE)
        end = start + m_fim.start() if m_fim else len(t)
        bloco = t[start:end]

    propriedades_padrao = []
    propriedades_amostragem = []
    destinos = {"padrao": propriedades_padrao, "amostragem": propriedades_amostragem}

    for nome, destino, renomear_para in _CAMPOS:
        valor, incerteza = _valor_incerteza(bloco, nome)
        if valor is None:
            continue
        destinos[destino].append({
            "propriedade": renomear_para or nome,
            "referencia": None,
            "valor": valor,
            "incerteza": incerteza,
        })

    return {
        "empresa": extrair_cliente_gt(t),
        "certificado": extrair_certificado_gt(t),
        "propriedades_pad": {"propriedades_padrao": propriedades_padrao},
        "propriedades_amost": {"propriedades_amostragem": propriedades_amostragem},
    }
