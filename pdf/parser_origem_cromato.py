import re


def _normalizar_numero(valor):
    """Converte um número do relatório da Origem (ponto decimal, por vezes
    notação científica, ex.: '5E-05') pro formato brasileiro com vírgula
    usado no resto do app (ex.: '0,00005')."""
    if valor is None:
        return None
    valor = valor.strip()
    try:
        numero = float(valor.replace(",", "."))
    except ValueError:
        return valor
    texto = f"{numero:.10f}".rstrip("0").rstrip(".")
    if not texto or texto == "-":
        texto = "0"
    return texto.replace(".", ",")


def identificar_origem_cromato(texto):
    """Identifica o relatório de cromatografia do laboratório interno da
    Origem Energia Alagoas (LIMS "Report Builder"/mylimsweb.cloud) — layout
    completamente diferente do relatório da SGS (ver parser_sgs.py)."""
    if not texto:
        return False
    return bool(re.search(
        r"Laborat[óo]rio\s+Cromatografia\s*-\s*Origem\s+Energia\s+Alagoas",
        texto, re.IGNORECASE
    ))


def extrair_empresa_origem(texto):
    """<EMPRESA> aqui é o próprio laboratório/empresa dono do relatório —
    diferente do relatório da SGS, esse não tem um "Cliente:" externo
    (o "Cliente:" que aparece no relatório é a estação de coleta interna,
    não uma empresa cliente da ODS)."""
    if not texto:
        return None
    m = re.search(r"Laborat[óo]rio\s+Cromatografia\s*-\s*(.+)", texto, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extrair_certificado_origem(texto):
    """O número do relatório aparece com pequenas variações de formatação
    ao longo do documento (ex.: "15833/2026.0.A" no relatório principal e
    "15833/2026.0" no relatório complementar de propriedades) — usa a
    variante mais específica (a mais longa)."""
    if not texto:
        return None
    candidatos = [
        m.strip() for m in re.findall(
            r"Relat[óo]rio de An[áa]lises\s+([^\n]+)", texto, re.IGNORECASE
        ) if m.strip()
    ]
    return max(candidatos, key=len) if candidatos else None


def _linha_propriedade(texto, nome_exato):
    """Busca, na tabela "Resultados Analíticos", a linha cuja análise é
    exatamente `nome_exato` (ex.: "Massa Molar", "Fator de
    compressibilidade - CL") e retorna (valor, incerteza) das colunas
    Resultado/Incerteza. O valor só é aceito se vier logo após o nome, sem
    nada no meio — isso evita casar "Densidade Absoluta" com a linha
    "Densidade Absoluta - CL ..."."""
    pat = re.compile(
        r"^[ \t]*" + re.escape(nome_exato) + r"[ \t]+"
        r"(?P<valor>[<>]?\s*[\d.,]+(?:[Ee][+-]?\d+)?)"
        r"[ \t]*(?:[A-Za-zµ/³%°]+)?[ \t]+"
        r"\S+[ \t]+\S+[ \t]+.+?[ \t]+"
        r"(?P<incerteza>[\d.,]+(?:[Ee][+-]?\d+)?)[ \t]+"
        r"(?:NBR|ISO|ASTM)",
        re.IGNORECASE | re.MULTILINE
    )
    m = pat.search(texto)
    if not m:
        return None, None
    return m.group("valor").strip(), m.group("incerteza").strip()


# (nome da análise no relatório -> lista de destino) — replica a mesma
# separação padrão/linha (CL) usada pro relatório da SGS, ver xml_cromato.py
_CAMPOS_ORIGEM = [
    ("Massa Molar", "padrao"),
    ("Densidade Absoluta", "padrao"),
    ("Fator de compressibilidade - CL", "amostragem"),
    ("Viscosidade do gás - CL", "amostragem"),
    ("Coeficiente Isentrópico - CL", "amostragem"),
]


def extrair_campos_cromato_origem(texto):
    """Extrai os campos de cromatografia do relatório da Origem Energia
    Alagoas no mesmo formato usado por extrair_campos_cromato
    (pdf/parser_sgs.py), pra alimentar xml_cromatografia() sem precisar de
    nenhuma mudança lá."""
    t = (texto or "").replace("\r\n", "\n").replace("\r", "\n")

    propriedades_padrao = []
    propriedades_amostragem = []
    destinos = {"padrao": propriedades_padrao, "amostragem": propriedades_amostragem}

    for nome, destino in _CAMPOS_ORIGEM:
        valor, incerteza = _linha_propriedade(t, nome)
        if valor is None:
            continue
        destinos[destino].append({
            "propriedade": nome,
            "referencia": None,
            "valor": _normalizar_numero(valor),
            "incerteza": _normalizar_numero(incerteza),
        })

    return {
        "empresa": extrair_empresa_origem(t),
        "certificado": extrair_certificado_origem(t),
        "propriedades_pad": {"propriedades_padrao": propriedades_padrao},
        "propriedades_amost": {"propriedades_amostragem": propriedades_amostragem},
    }
