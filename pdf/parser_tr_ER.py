import re
from pdf.parser_er_common import extrair_numero_evaluation, normalizar_espacos


def _normalizar(texto):
    return normalizar_espacos(texto)


def _to_aprovado(s):
    if not s:
        return "NÃO ENCONTRADO"
    s = s.strip().lower()
    if "not accepted" in s or "não aceito" in s:
        return "Não"
    if "accepted" in s or "aceito" in s:
        return "Sim"
    return "NÃO ENCONTRADO"


def extrair_numero_evaluation_tr(texto):
    return extrair_numero_evaluation(texto)


def extrair_d_er(texto):
    """
    Extrai valor e incerteza de D a partir de:
    'Item 6.4.2 Measured Internal diameter medium D @ 20°C:\n52,57 ± 0,05 mm'
    """
    t = _normalizar(texto)
    m = re.search(
        r"Item 6\.4\.2.*?D\s*@\s*20.*?°C\s*:\s*([\d,]+)\s*[±+\-]\s*([\d,]+)\s*mm",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        return {
            "valor": m.group(1).replace(",", "."),
            "incerteza": m.group(2).replace(",", "."),
        }
    return None


# ── Upstream cylindricity ──────────────────────────────────────────────────

def resultado_cilindricidade_montante_alem_10D(texto):
    """Item 6.4.3 - beyond 10D: 'Not exceed 2% of D ≥ Accepted'"""
    t = _normalizar(texto)
    m = re.search(
        r"Not exceed 2%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_cilindricidade_montante_2_10D(texto):
    """Item 6.4.3 - 2-10D: 'Not exceed 0,3% of D ≥ Accepted'
    Appears on the same line as the beyond-10D result; we capture the second one.
    """
    t = _normalizar(texto)
    m = re.search(
        r"Not exceed 2%.*?(\bNot Accepted\b|\bAccepted\b).*?"
        r"Not exceed 0,3%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(2)) if m else "NÃO ENCONTRADO"


def resultado_rugosidade_montante_2_10D(texto):
    """Item 5.3.1 - roughness 2-10D upstream: 'Medium roughness: Accepted'"""
    t = _normalizar(texto)
    m = re.search(
        r"Roughness evaluation 2-10D Upstream.*?Medium roughness[^A-Za-z]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_comprimento_montante(texto):
    """Item 6.3.3.3 upstream pipe length: 'Result: Accepted'"""
    t = _normalizar(texto)
    m = re.search(
        r"Item 6\.3\.3\.3.*?Pipe Lenght Upstream.*?Result[:\s]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


# ── Downstream ─────────────────────────────────────────────────────────────

def resultado_cilindricidade_jusante(texto):
    """Item 6.4.6 - downstream cylindricity: first result on 'Not exceed 3%' line"""
    t = _normalizar(texto)
    m = re.search(
        r"Not exceed 3%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_rugosidade_jusante(texto):
    """Item 5.3.1 downstream roughness: second result on 'Not exceed 3%' line"""
    t = _normalizar(texto)
    m = re.search(r"Not exceed 3%.*", t, flags=re.IGNORECASE)
    if m:
        resultados = re.findall(r"\bNot Accepted\b|\bAccepted\b", m.group(0), re.IGNORECASE)
        if len(resultados) >= 2:
            return _to_aprovado(resultados[1])
    return "NÃO ENCONTRADO"


def resultado_comprimento_tomada_temp(texto):
    """Item 5.4.4.1 temperature tap length: 'Result: Accepted'"""
    t = _normalizar(texto)
    m = re.search(
        r"Item 5\.4\.4\.1.*?Result[:\s]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_comprimento_acidente_jusante(texto):
    """Item 7.4.1 first downstream accident: 'Result: Accepted'"""
    t = _normalizar(texto)
    m = re.search(
        r"Item 7\.4\.1.*?Result[:\s]+(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


# ── Orifice Carrier ─────────────────────────────────────────────────────────

def resultado_cilindricidade_0_2D(texto):
    """Item 6.4.1 - cylindricity up to 2D upstream: first result after 'Not exceed 0,3%'
    within the Item 6.4.1 context (page 3).
    """
    t = _normalizar(texto)
    m = re.search(
        r"Item 6\.4\.1.*?Not exceed 0,3%.*?of D.*?(\bNot Accepted\b|\bAccepted\b)",
        t,
        flags=re.IGNORECASE,
    )
    return _to_aprovado(m.group(1)) if m else "NÃO ENCONTRADO"


def resultado_rugosidade_0_2D(texto):
    """Item 5.3.1 - roughness 0-2D: second result on the 'Not exceed 0,3%' line
    in the Item 6.4.1 context (page 3).
    """
    t = _normalizar(texto)
    m = re.search(r"Item 6\.4\.1.*?Not exceed 0,3%.*", t, flags=re.IGNORECASE)
    if m:
        resultados = re.findall(r"\bNot Accepted\b|\bAccepted\b", m.group(0), re.IGNORECASE)
        if len(resultados) >= 2:
            return _to_aprovado(resultados[1])
    return "NÃO ENCONTRADO"


# ── Main ────────────────────────────────────────────────────────────────────

def extrair_campos_er_tr(texto):
    """
    Retorna dict com todos os resultados do Relatório de Avaliação do trecho reto.

    'Diametro_D' é o resultado de Item 6.4.1 (cilindricidade 0-2D a montante),
    que valida as posições onde D é medido para o computador de vazão.
    """
    return {
        "Numero_Evaluation": extrair_numero_evaluation_tr(texto),
        "d_er": extrair_d_er(texto),
        "Cil_Montante_Alem_10D": resultado_cilindricidade_montante_alem_10D(texto),
        "Cil_Montante_2_10D": resultado_cilindricidade_montante_2_10D(texto),
        "Rug_Montante_2_10D": resultado_rugosidade_montante_2_10D(texto),
        "Comp_Montante": resultado_comprimento_montante(texto),
        "Cil_Jusante": resultado_cilindricidade_jusante(texto),
        "Rug_Jusante": resultado_rugosidade_jusante(texto),
        "Comp_Tomada_Temp": resultado_comprimento_tomada_temp(texto),
        "Comp_Acidente_Jusante": resultado_comprimento_acidente_jusante(texto),
        "Diametro_D": resultado_cilindricidade_0_2D(texto),
        "Rug_0_2D": resultado_rugosidade_0_2D(texto),
    }