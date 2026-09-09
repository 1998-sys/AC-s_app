# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_gt_quimica
# Created       : 09-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses GT Química chromatography reports ("Boletim de Resultado de Análise"), extracting client, certificate number and the gas properties used in the flow calculation.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re


def identificar_gt_quimica(texto):
    """Identifies a GT Química chromatography report ("Boletim de Resultado de Análise").

    Args:
        texto: Report text extracted.

    Returns:
        bool: True if the text carries GT Química's site footer
        ("gtquimica.com.br"), False otherwise (including when `texto` is empty).
    """
    if not texto:
        return False
    return "gtquimica" in texto.lower()


def extrair_certificado_gt(texto):
    """Extracts the report number from "Boletim de Resultado de Análise N° ...".

    Args:
        texto: Report text extracted.

    Returns:
        str: Report number (e.g. "CRO FRADE/26-28374"), or None if not found.
    """
    if not texto:
        return None
    m = re.search(
        r"Boletim de Resultado de An[áa]lise\s*N[°º]\s*(.+)$",
        texto, re.IGNORECASE | re.MULTILINE,
    )
    return m.group(1).strip() if m else None


def extrair_cliente_gt(texto):
    """Extracts the client name from "Razão Social: ... Interessado: ...".

    Args:
        texto: Report text extracted.

    Returns:
        str: Client's company name (e.g. "PETRO RIO JAGUAR PETRÓLEO S.A"),
        or None if not found.
    """
    if not texto:
        return None
    m = re.search(r"Raz[ãa]o Social:\s*(.+?)\s+Interessado:", texto, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _bloco(texto, padrao_inicio, padrao_fim):
    """Isolates the text between the end of `padrao_inicio` and the start of `padrao_fim`.

    Args:
        texto: Full report text (already extracted).
        padrao_inicio: Regex marking the start of the block (excluded from
            the result).
        padrao_fim: Regex marking the end of the block (excluded from the
            result), or None to take the rest of the text.

    Returns:
        str: The isolated block, or "" if `padrao_inicio` isn't found.
    """
    m_ini = re.search(padrao_inicio, texto, re.IGNORECASE)
    if not m_ini:
        return ""
    start = m_ini.end()
    m_fim = re.search(padrao_fim, texto[start:], re.IGNORECASE) if padrao_fim else None
    end = start + m_fim.start() if m_fim else len(texto)
    return texto[start:end]


def _valor_incerteza(bloco, nome_exato):
    """Finds, within `bloco`, the row "nome_exato <método ref.> <valor> <unidade ou -> <incerteza>".

    Both "Propriedades do Gás" tables in this report share this exact
    column layout (property name, one-letter+digit method reference —
    1A/1B/1C/1D —, value, unit or "-" for dimensionless, uncertainty), so
    the same pattern works for either table's rows.

    Args:
        bloco: Text of a single properties table (see `_bloco`).
        nome_exato: Property name, exactly as it appears in the report
            (e.g. "Peso Molecular Médio").

    Returns:
        tuple: (valor, incerteza) as raw PT-BR strings (decimal comma,
        already in the report's own format — no conversion needed), or
        (None, None) if the row isn't found in this block.
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


# Property names as they appear in each table, and how to rename them so
# xml_cromato.py's keyword matching (_buscar_propriedade) recognizes them
# without needing any change there — "Fator Z" doesn't contain
# "compressibilidade", the keyword every other lab's report uses for the
# same property, so it's the only one that needs renaming; the rest already
# match as-is (e.g. "Viscosidade" already contains "VISCOSIDADE").
_CAMPOS_PADRAO = ["Peso Molecular Médio", "Densidade Absoluta"]
_CAMPOS_OPERACAO = ["Fator Z", "Viscosidade", "Coeficiente Isentrópico"]
_RENOMEAR = {"Fator Z": "Fator de Compressibilidade"}


def extrair_campos_cromato_gt(texto):
    """Extracts the chromatography fields from a GT Química report in the same format used by extrair_campos_cromato (pdf/parser_sgs.py).

    "Densidade Absoluta" and "Fator Z"/"Viscosidade"/"Coeficiente
    Isentrópico" each appear in BOTH the "Condição Padrão" and "Condição
    Operação" tables with different values — the two tables are isolated
    first (see `_bloco`) so each property is only read from the table it
    belongs to (padrão -> molar mass/absolute density at standard
    condition; operação -> the "_CL"/line-condition properties).

    Args:
        texto: Report text extracted.

    Returns:
        dict: Keys "empresa", "certificado", "propriedades_pad" and
        "propriedades_amost", in the same format returned by
        pdf.parser_sgs.extrair_campos_cromato.
    """
    t = (texto or "").replace("\r\n", "\n").replace("\r", "\n")

    bloco_padrao = _bloco(
        t,
        r"Propriedades do G[aá]s\s*\(Condi[cç][ãa]o Padr[ãa]o\)",
        r"Propriedades do G[aá]s\s*\(Condi[cç][ãa]o Opera[cç][ãa]o\)",
    )
    bloco_operacao = _bloco(
        t,
        r"Propriedades do G[aá]s\s*\(Condi[cç][ãa]o Opera[cç][ãa]o\)",
        r"Contaminantes:",
    )

    propriedades_padrao = []
    for nome in _CAMPOS_PADRAO:
        valor, incerteza = _valor_incerteza(bloco_padrao, nome)
        if valor is None:
            continue
        propriedades_padrao.append({
            "propriedade": _RENOMEAR.get(nome, nome),
            "referencia": None,
            "valor": valor,
            "incerteza": incerteza,
        })

    propriedades_amostragem = []
    for nome in _CAMPOS_OPERACAO:
        valor, incerteza = _valor_incerteza(bloco_operacao, nome)
        if valor is None:
            continue
        propriedades_amostragem.append({
            "propriedade": _RENOMEAR.get(nome, nome),
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
