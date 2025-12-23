import re
import unicodedata




def normalizar_num(valor):
    if valor is None:
        return None
    try:
        return float(str(valor).replace(",", "."))
    except Exception:
        return None


def normalizar_texto(texto):
    if not texto:
        return None
    texto = texto.upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))



def extrair_tag(texto):
    padrao = r"TAG:\s*([0-9A-Za-z]+(?:\s*[-‐‒–—―]\s*[0-9A-Za-z]+)+)"
    m = re.search(padrao, texto)
    if not m:
        return None

    tag = (
        m.group(1)
        .replace("‐", "-")
        .replace("‒", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("―", "-")
    )
    return re.sub(r"\s*-\s*", "-", tag).strip()


def extrair_sn(texto):
    encontrados = re.findall(
        r"(?:SN|Num\.?\s*de\s*Série):\s*([^\s]+)",
        texto,
        flags=re.IGNORECASE
    )
    sns_validos = [s for s in encontrados if any(c.isdigit() for c in s)]
    sn_inst = sns_validos[0] if len(sns_validos) >= 1 else None
    sn_sensor = sns_validos[1] if len(sns_validos) >= 2 else None
    return sn_inst, sn_sensor


def extrair_certificado(texto):
    m = re.search(r"Nº\s*([^\n]+)", texto)
    return m.group(1).strip() if m else None


def extrair_datas(texto):
    m_cal = re.search(
        r"(Calibration Date|Data da Calibração):\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
        texto,
        flags=re.IGNORECASE
    )
    m_rep = re.search(
        r"(Report Date|Data do Relatório):\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
        texto,
        flags=re.IGNORECASE
    )
    return (
        m_cal.group(2) if m_cal else None,
        m_rep.group(2) if m_rep else None
    )


def extrair_local(texto):
    bloco = re.search(
        r"CALIBRATION LOCATION:(.*?)(?:CALIBRATED ITEM DESCRIPTION|CLIENT INFORMATION|$)",
        texto,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not bloco:
        return None

    m = re.search(
        r"(Name|Address|Nome|Endereço):\s*([A-Za-z0-9 \-_/]+)",
        bloco.group(1),
        flags=re.IGNORECASE
    )

    return m.group(2).strip() if m else None


def extrair_sistema(texto):
    m = re.search(
        r"(?:System Description|Descrição do Sistema):\s*([\s\S]+?)"
        r"(?=\n(?:Name:|Address:|Calibrated|Classification|Classificação|"
        r"Periodicidade|Periodicity|Next Calibration|Próxima Calibração|"
        r"LOCAL ENVIRONMENTAL|REFERENCE STANDARDS|ITEM|TAG|SN))",
        texto,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not m:
        return None

    sistema = re.sub(r"\s+", " ", m.group(1)).strip()

    # 🔒 remove Periodicity / Periodicidade se vier colado no sistema
    sistema = re.sub(
        r"\b(Periodicity|Periodicidade)\b.*$",
        "",
        sistema,
        flags=re.IGNORECASE
    ).strip()

    return sistema



def extrair_range_calibrado(texto):
    padrao = r"""
    Calibration\s*Range.*?
    Min\s*[:\-]?\s*([-+]?[0-9.,]+)
    .*?
    Max\s*[:\-]?\s*([-+]?[0-9.,]+)
    """
    m = re.search(padrao, texto, flags=re.I | re.S | re.VERBOSE)
    return (
        normalizar_num(m.group(1)) if m else None,
        normalizar_num(m.group(2)) if m else None
    )


def extrair_range_indicado(texto):
    padrao = r"""
    Indication\s*Range.*?
    Min\s*[:\-]?\s*([-+]?[0-9.,]+)
    .*?
    Max\s*[:\-]?\s*([-+]?[0-9.,]+)
    """
    m = re.search(padrao, texto, flags=re.I | re.S | re.VERBOSE)
    return (
        normalizar_num(m.group(1)) if m else None,
        normalizar_num(m.group(2)) if m else None
    )



def extrair_haste(texto):
    rod = re.search(r"Rod length:\s*([\d,.]+)", texto, flags=re.IGNORECASE)
    probe = re.search(r"Probe diameter:\s*([\d,.]+)", texto, flags=re.IGNORECASE)

    return (
        normalizar_num(rod.group(1)) if rod else None,
        normalizar_num(probe.group(1)) if probe else None
    )



def extrair_erro_incerteza(texto):
    """
    Extrai Erro Fiducial e Incerteza a partir da tabela
    'Metrological characteristics', ignorando curva de calibração.
    """

    padrao = r"""
    Metrological\ characteristics.*?          # início do bloco
    Repeatability.*?Uncertainty                # cabeçalho (EN)
    .*?\n                                     # quebra de linha
    .*?\n                                     # linha PT (Repetibilidade...)
    \s*
    ([-+]?\d+[.,]\d+)\s*%?\s+                 # repetibilidade
    ([-+]?\d+[.,]\d+)\s*%?\s+                 # histerese
    ([-+]?\d+[.,]\d+)\s*%?\s+                 # ERRO FIDUCIAL  ← grupo 3
    ([-+]?\d+[.,]\d+)\s*%?                    # INCERTEZA      ← grupo 4
    """

    m = re.search(
        padrao,
        texto,
        flags=re.IGNORECASE | re.DOTALL | re.VERBOSE
    )

    if not m:
        return None, None

    return (
        normalizar_num(m.group(3)),
        normalizar_num(m.group(4))
    )



def extrair_campos(texto: str) -> dict:
    tag = extrair_tag(texto)
    sn_inst, sn_sensor = extrair_sn(texto)
    certificado = extrair_certificado(texto)
    data_cal, report_date = extrair_datas(texto)
    local = extrair_local(texto)
    sistema = extrair_sistema(texto)

    min_range, max_range = extrair_range_calibrado(texto)
    inmin_range, inmax_range = extrair_range_indicado(texto)

    rod_length, probe_diameter = extrair_haste(texto)
    erro_fid, incerteza = extrair_erro_incerteza(texto)

    return {
        "tag": tag,
        "sn_instrumento": sn_inst,
        "sn_sensor": sn_sensor,
        "certificado": certificado,
        "data": data_cal,
        "local": local,
        "sistema": sistema,
        "report_date": report_date,
        "min_range": min_range,
        "max_range": max_range,
        "inmin_range": inmin_range,
        "inmax_range": inmax_range,
        "rod_length": rod_length,
        "probe_diameter": probe_diameter,
        "erro_fid": erro_fid,
        "incerteza": incerteza
    }


