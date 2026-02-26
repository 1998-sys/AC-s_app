import re
from pdf.extrator import extrair_texto
from xml_model.xml_cromato import xml_cromatografia









def extrair_empresa(texto):
    if not texto:
        return None
    
    if "sgs" in texto.lower():
        return "SGS"
    
    return None


def numero_cert(texto):
    if not texto:
        return None
    primeira = next((l.strip() for l in texto.splitlines() if l.strip()), "")

    m = re.search(r"(\d{3,6}(?:[.,]\d{2,3})?.*)$", primeira)
    return m.group(1).strip() if m else None


def composicao(texto: str):
    if not texto:
        return {"composicao": []}

    
    DEFAULT_DECIMALS = 3
    def _zero(decimals=DEFAULT_DECIMALS) -> str:
        return "0," + "0" * decimals

    def _as_num_or_zero(s: str, default_decimals=DEFAULT_DECIMALS) -> str:
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
    if not texto:
        return {"propriedades_padrao": []}
    t = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    m_ini = re.search(r"Propriedades do Gas\s*-\s*Condiç[ãa]o Padr[ãa]o\s*\(1\)\s*Refer[êe]ncia", t, re.IGNORECASE)
    if not m_ini:
        
        m_ini = re.search(r"Propriedades do G[aá]s\s*-\s*Condi[cç][aã]o Padr[aã]o\s*\(1\)\s*Refer[êe]ncia", t, re.IGNORECASE)
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
    if not texto:
        return {"propriedades_amostragem": []}
    DEFAULT_DECIMALS = 3
    def _zero(decimals=DEFAULT_DECIMALS) -> str:
        return "0," + "0" * decimals
    def _as_num_or_zero(s: str, default_decimals=DEFAULT_DECIMALS) -> str:
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
    empre = extrair_empresa(texto)
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



