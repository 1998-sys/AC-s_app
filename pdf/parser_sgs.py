# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_sgs
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses SGS chromatography reports, extracting client, certificate number, gas composition and standard/sampling condition properties.
#                 Analisa relatórios de cromatografia da SGS, extraindo cliente, número do certificado, composição do gás e propriedades nas condições padrão/amostragem.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re



def extrair_empresa(texto):
    """Identifies whether the report is from SGS (used only to detect the report
    TYPE in pdf/utils_parser.py, not the certificate's client).

    Returns:
        str: "SGS" if the text contains that word (case-insensitive), otherwise None.
    """
    if not texto:
        return None

    if "sgs" in texto.lower():
        return "SGS"

    return None


def extrair_cliente(texto):
    """Extracts the report's client name (label "Cliente:") — this is the value
    that goes into the XML's <EMPRESA> tag, not the lab (extrair_empresa only
    identifies the report TYPE in select_extract).

    In the most common layout, the value is on the same line as the label. In
    some observed SGS PDFs, the label is extracted in isolation (no value on
    the same line) and the value reappears much further down in the text,
    right after the title "RELATÓRIO DE ANÁLISES DE GÁS NATURAL" — used as a
    fallback.

    Args:
        texto: Report text extracted.

    Returns:
        str: Client name, or None if neither pattern matches.
    """
    if not texto:
        return None
    t = texto.replace("\r\n", "\n").replace("\r", "\n")

    m = re.search(r"Cliente:[ \t]*(\S[^\n]*)", t)
    if m:
        return m.group(1).strip()

    m_titulo = re.search(r"RELAT[ÓO]RIO DE AN[ÁA]LISES DE G[ÁA]S NATURAL[^\n]*", t, re.IGNORECASE)
    if m_titulo:
        for linha in t[m_titulo.end():].splitlines():
            linha = linha.strip()
            if linha:
                return linha

    return None


def numero_cert(texto):
    """Extracts the certificate number from the first non-empty line of the report text.

    Args:
        texto: Report text extracted.

    Returns:
        str: Certificate number, or None if not found either in the first line
        or in the title-based fallback (the same "out-of-order" layout handled
        in extrair_cliente).
    """
    if not texto:
        return None
    primeira = next((l.strip() for l in texto.splitlines() if l.strip()), "")

    m = re.search(r"(\d{3,6}(?:[.,]\d{2,3})?.*)$", primeira)
    if m:
        return m.group(1).strip()

    # Fallback: no mesmo layout "fora de ordem" tratado em extrair_cliente,
    # o número do certificado aparece colado no título do relatório, não na
    # primeira linha extraída.
    m_titulo = re.search(
        r"RELAT[ÓO]RIO DE AN[ÁA]LISES DE G[ÁA]S NATURAL\s+(\S.*)$",
        texto, re.IGNORECASE | re.MULTILINE
    )
    return m_titulo.group(1).strip() if m_titulo else None


def composicao(texto: str):
    """Extracts the natural gas molar composition table from the SGS report.

    Isolates the text block between the "Composição do gás (...)" header and
    the following section (Gas Properties/Air Contamination/Observations),
    then matches each component line (e.g., iC4+, CO2, H2S, N2, C6+) with its
    name, molar percentage and uncertainty. Labels like "N2"/"C6" are
    converted to the Unicode subscript form (e.g., "N₂", "C₆"), and a
    molar/uncertainty value that is not a recognizable number is replaced
    with zero.

    Args:
        texto: Report text extracted.

    Returns:
        dict: {"composicao": list[dict]}, each item with "rotulo", "nome",
        "mol_pct" and "incerteza"; empty list if the section is not found.
    """
    if not texto:
        return {"composicao": []}

    
    DEFAULT_DECIMALS = 3
    def _zero(decimals=DEFAULT_DECIMALS) -> str:
        """Returns "0" with the given number of decimal places (PT-BR format, comma)."""
        return "0," + "0" * decimals

    def _as_num_or_zero(s: str, default_decimals=DEFAULT_DECIMALS) -> str:
        """Returns `s` if it is a number in "N,NN..." format, otherwise zero with `default_decimals` places."""
        s = s.strip()
        if re.fullmatch(r"\d+,\d+", s):
            return s
        return _zero(default_decimals)
    t = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    m_ini = re.search(r"Composiç[ãa]o do g[aá]s\s*\([^)]+\)", t, re.IGNORECASE)
    if not m_ini:
        return {"composicao": []}
    start = m_ini.end()
    m_fim = re.search(
        r"^(?:Propriedades do G[aá]s|Propriedades do Gas|Contaminaç[ãa]o por Ar|OBSERVAÇÕES?)\b",
        t[start:], re.IGNORECASE | re.MULTILINE
    )
    end = start + m_fim.start() if m_fim else len(t)
    bloco = t[start:end]

   
    linha_pat = re.compile(
        r"""^
        (?!Total\b)                            
        (?!Incerteza\b)                         
        (?!Componentes\b)
        (?!Expandida\b)
        \s*(?P<rotulo>                          
              (?:[in]\s*C\s*\d+\+?)             
            | CO2                                
            | H\s*2\s*S                          
            | N\s*\d+                            
            | C\s*\d+\+?                         
        )
        \s+(?P<nome>.+?)                       
        \s+(?P<mol>\S+)                         
        \s+(?P<inc>\S+)                         
        \s*$""",
        re.IGNORECASE | re.MULTILINE | re.VERBOSE
    )

    subs = str.maketrans({"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇","8":"₈","9":"₉"})
    def rotulo_identico(rotulo_raw: str) -> str:
        """Normalizes the component's raw label to the final format with Unicode subscript."""
        r = re.sub(r"\s+", "", rotulo_raw)
        if re.match(r"^[in]c\d+\+?$", r, re.IGNORECASE):
            return r[0].lower() + "C" + r[2:]
       
        if re.match(r"^CO\d+\+?$", r):
            return r
        if r == "C9+":
            return r
        m = re.match(r"^([NC])(\d+)$", r.upper())
        if m:
            base, dig = m.groups()
            return base + dig.translate(subs)
        return r.upper()

    composicao = []
    for m in linha_pat.finditer(bloco):
        mol_val = _as_num_or_zero(m.group("mol"))
        inc_val = _as_num_or_zero(m.group("inc"))
        composicao.append({
            "rotulo":    rotulo_identico(m.group("rotulo")),
            "nome":      m.group("nome"),
            "mol_pct":   mol_val,  
            "incerteza": inc_val,   
        })

    return {"composicao": composicao}


def propriedades_padrao(texto: str):
    """Extracts the "Propriedades do Gás - Condição Padrão (1) Referência" table from the SGS report.

    Tries to locate the section's full header; if not found, falls back to
    searching only for the isolated "Referência" line, covering the same
    "out-of-order" layout handled in extrair_cliente. Each line of the block
    is then matched against a property, an optional normative reference
    (ISO ####), and the numeric and uncertainty values.

    Args:
        texto: Report text extracted.

    Returns:
        dict: {"propriedades_padrao": list[dict]}, each item with
        "propriedade", "referencia", "valor" and "incerteza"; empty list if
        the section is not found.
    """
    if not texto:
        return {"propriedades_padrao": []}
    t = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    m_ini = re.search(r"Propriedades do Gas\s*-\s*Condiç[ãa]o Padr[ãa]o\s*\(1\)\s*Refer[êe]ncia", t, re.IGNORECASE)
    if not m_ini:

        m_ini = re.search(r"Propriedades do G[aá]s\s*-\s*Condi[cç][aã]o Padr[aã]o\s*\(1\)\s*Refer[êe]ncia", t, re.IGNORECASE)
    if not m_ini:
        # Fallback: mesmo layout "fora de ordem" tratado em extrair_cliente —
        # o título da seção fica separado do cabeçalho "Referência", que
        # aparece isolado numa linha própria antes das propriedades.
        m_ini = re.search(r"^\s*Refer[êe]ncia\s*$", t, re.IGNORECASE | re.MULTILINE)
    if not m_ini:
        return {"propriedades_padrao": []}
    start = m_ini.end()

  
    m_fim = re.search(
        r"^(?:Propriedades do Gas\s*-\s*Condi[cç][oõ]es de Amostragem|Propriedades do G[aá]s\s*-\s*Condi[cç][oõ]es de Amostragem|Contamina[cç][aã]o por Ar|OBSERVA[CÇ][OÕ]ES?)\b",
        t[start:], re.IGNORECASE | re.MULTILINE
    )
    end = start + m_fim.start() if m_fim else len(t)
    bloco = t[start:end].strip()
    linha_pat = re.compile(
        r"""^
        (?P<prop>.+?)                          
        (?:\s+(?P<ref>ISO\s*\d{4,5}))?          
        \s+(?P<val>\d+(?:,\d+)?)                
        \s+(?P<inc>\d+(?:,\d+)?)                
        \s*$""",
        re.IGNORECASE | re.MULTILINE | re.VERBOSE
    )
    saida = []
    for m in linha_pat.finditer(bloco):
        saida.append({
            "propriedade": m.group("prop").strip(),        
            "referencia": (m.group("ref") or None),
            "valor":      m.group("val"),
            "incerteza":  m.group("inc"),
        })

    return {"propriedades_padrao": saida}


def propriedades_amostragem(texto: str):
    """Extracts the "Propriedades do Gás - Condições de Amostragem" table from the SGS report.

    Each line of the block may carry a note in parentheses (e.g., "(1)")
    and/or a normative reference (ISO ####); when there is no ISO reference,
    the note is used as the reference. Non-numeric values are replaced with
    zero.

    Args:
        texto: Report text extracted.

    Returns:
        dict: {"propriedades_amostragem": list[dict]}, each item with
        "propriedade", "referencia", "valor" and "incerteza"; empty list if
        the section is not found.
    """
    if not texto:
        return {"propriedades_amostragem": []}
    DEFAULT_DECIMALS = 3
    def _zero(decimals=DEFAULT_DECIMALS) -> str:
        """Returns "0" with the given number of decimal places (PT-BR format, comma)."""
        return "0," + "0" * decimals
    def _as_num_or_zero(s: str, default_decimals=DEFAULT_DECIMALS) -> str:
        """Returns `s` if it is a number in "N" or "N,NN..." format, otherwise zero with `default_decimals` places."""
        s = (s or "").strip()
        return s if re.fullmatch(r"\d+(?:,\d+)?", s) else _zero(default_decimals)
    t = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    m_ini = re.search(
        r"Propriedades do G[aá]s\s*-\s*Condi[cç][oõ]es de Amostragem",
        t, re.IGNORECASE
    )
    if not m_ini:
        return {"propriedades_amostragem": []}
    start = m_ini.end()
    m_fim = re.search(
        r"^(?:Contamina[cç][aã]o por Ar|OBSERVA[CÇ][OÕ]ES?)\b",
        t[start:], re.IGNORECASE | re.MULTILINE
    )
    end = start + m_fim.start() if m_fim else len(t)
    bloco = t[start:end].strip()
    linha_pat = re.compile(
        r"""^
        (?P<prop>.+?)                           
        \s*(?P<nota>\(\d+\))?                   
        (?:\s+(?P<ref>ISO\s*\d{4,5}))?          
        \s+(?P<val>\S+)                         
        \s+(?P<inc>\S+)                         
        \s*$""",
        re.IGNORECASE | re.MULTILINE | re.VERBOSE
    )

    saida = []
    for m in linha_pat.finditer(bloco):
        prop = m.group("prop").strip()
        nota = (m.group("nota") or "").strip() or None
        ref  = (m.group("ref") or None)
        val  = _as_num_or_zero(m.group("val"))
        inc  = _as_num_or_zero(m.group("inc"))

        
        referencia = ref or nota

        if not prop:
            continue
        saida.append({
            "propriedade": prop,   
            "referencia": referencia,   
            "valor": val,
            "incerteza": inc,
        })

    return {"propriedades_amostragem": saida}


def extrair_campos_cromato(texto):
    """Builds the complete dictionary of fields for an SGS chromatography report.

    Args:
        texto: Report text extracted.

    Returns:
        dict: Keys "empresa", "certificado", "composicao", "propriedades_pad"
        and "propriedades_amost", ready to fill the AC template.
    """
    empre = extrair_cliente(texto)
    cert = numero_cert(texto)
    comp = composicao(texto)
    prop_pad = propriedades_padrao(texto)
    prop_amost=propriedades_amostragem(texto)
 
    return {
        'empresa': empre,
        'certificado': cert,
        'composicao': comp,
        'propriedades_pad': prop_pad,
        'propriedades_amost':prop_amost

    }



