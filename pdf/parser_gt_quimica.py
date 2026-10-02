# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_gt_quimica
# Created       : 09-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses GT Química chromatography reports ("Boletim de Resultado de Análise"), extracting client, certificate number, full gas composition and every reported property (standard and sampling condition).
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


def _todas_propriedades(bloco):
    """Finds every row "nome <método ref.> <valor> <unidade ou -> <incerteza>" in `bloco`.

    Both "Propriedades do Gás" tables in this report share this exact
    column layout (property name, one-letter+digit method reference —
    1A/1B/1C/1D —, value, unit or "-" for dimensionless, uncertainty), so
    the same pattern reads every row of either table, whatever properties
    it lists.

    Args:
        bloco: Text of a single properties table (see `_bloco`).

    Returns:
        list[dict]: one item per row, each with "nome" (unit folded into
        the name in parentheses, e.g. "Poder Calorífico Superior
        (kJ/m³)", same convention as the SGS report), "valor" and
        "incerteza" as raw PT-BR strings (decimal comma, already in the
        report's own format — no conversion needed).
    """
    pat = re.compile(
        r"^[ \t]*(?P<nome>[A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ\s\-/]*?)[ \t]+1[A-D][ \t]+"
        r"(?P<valor>[\d.,]+)[ \t]+(?P<unidade>\S+)[ \t]+"
        r"(?P<incerteza>[\d.,]+)[ \t]*$",
        re.MULTILINE,
    )
    resultado = []
    for m in pat.finditer(bloco):
        nome = m.group("nome").strip()
        unidade = m.group("unidade").strip()
        if unidade and unidade != "-":
            nome = f"{nome} ({unidade})"
        resultado.append({
            "nome": nome,
            "valor": m.group("valor").strip(),
            "incerteza": m.group("incerteza").strip(),
        })
    return resultado


def _composicao_gt(texto):
    """Extracts the natural gas molar composition table from a GT Química report.

    Isolates the text block between the sampling-conditions footnote ("*
    Dados coletados no ponto de amostragem", right before the table) and
    the "Total:" row that closes it, then matches each component line
    (label, name, method reference, molar percentage, uncertainty) — same
    row layout the properties tables use, see `_todas_propriedades`.

    Args:
        texto: Report text extracted (already normalized to "\\n" line
            endings).

    Returns:
        list[dict]: one item per component, each with "rotulo" (e.g.
        "N2", "iC4", "C9+"), "nome" (e.g. "Nitrogênio"), "mol_pct" and
        "incerteza" as raw PT-BR strings; empty list if the table isn't
        found.
    """
    bloco = _bloco(
        texto,
        r"Dados coletados no ponto de amostragem",
        r"Total:",
    )
    if not bloco:
        return []

    pat = re.compile(
        r"^[ \t]*(?P<rotulo>[A-Za-z0-9+]+)[ \t]+(?P<nome>[A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ\s\-]*?)[ \t]+1[A-D][ \t]+"
        r"(?P<mol>[\d.,]+)[ \t]+(?P<incerteza>[\d.,]+)[ \t]*$",
        re.MULTILINE,
    )
    composicao = []
    for m in pat.finditer(bloco):
        composicao.append({
            "rotulo": m.group("rotulo").strip(),
            "nome": m.group("nome").strip(),
            "mol_pct": m.group("mol").strip(),
            "incerteza": m.group("incerteza").strip(),
        })
    return composicao


# "Fator Z" doesn't contain "compressibilidade", the keyword every other
# lab's report uses for the same property and that xml_cromato.py's reduced
# generator (_buscar_propriedade) searches for — so it's the only property
# name GT Química's report needs renamed; everything else already matches
# as extracted (e.g. "Viscosidade" already contains "VISCOSIDADE").
_RENOMEAR = {"Fator Z": "Fator de Compressibilidade"}


def _renomear_propriedades(lista):
    """Applies `_RENOMEAR` to every item's "propriedade" field (in place semantics, returns a new list)."""
    return [{**p, "propriedade": _RENOMEAR.get(p["propriedade"], p["propriedade"])} for p in lista]


def extrair_campos_cromato_gt(texto):
    """Extracts the chromatography fields from a GT Química report in the same format used by extrair_campos_cromato (pdf/parser_sgs.py).

    "Densidade Absoluta" and "Fator Z"/"Viscosidade"/"Coeficiente
    Isentrópico" each appear in BOTH the "Condição Padrão" and "Condição
    Operação" tables with different values — the two tables are isolated
    first (see `_bloco`) so each property is only read from the table it
    belongs to (padrão -> standard-condition properties; operação -> the
    sampling/line-condition properties). Every row of each table is
    captured (not just the 5 used in the flow calculation), plus the full
    gas composition, so the report's complete content is available for
    `xml_model.xml_cromato.xml_cromatografia_completa`.

    Args:
        texto: Report text extracted.

    Returns:
        dict: Keys "empresa", "certificado", "composicao",
        "propriedades_pad" and "propriedades_amost", in the same format
        returned by pdf.parser_sgs.extrair_campos_cromato.
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

    propriedades_padrao = [
        {"propriedade": p["nome"], "referencia": None, "valor": p["valor"], "incerteza": p["incerteza"]}
        for p in _todas_propriedades(bloco_padrao)
    ]
    propriedades_amostragem = [
        {"propriedade": p["nome"], "referencia": None, "valor": p["valor"], "incerteza": p["incerteza"]}
        for p in _todas_propriedades(bloco_operacao)
    ]

    return {
        "empresa": extrair_cliente_gt(t),
        "certificado": extrair_certificado_gt(t),
        "composicao": {"composicao": _composicao_gt(t)},
        "propriedades_pad": {"propriedades_padrao": _renomear_propriedades(propriedades_padrao)},
        "propriedades_amost": {"propriedades_amostragem": _renomear_propriedades(propriedades_amostragem)},
    }
