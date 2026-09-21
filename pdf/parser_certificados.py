# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_certificados
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses secondary instrument calibration certificates (pressure/temperature transmitters, thermometers, manometers), extracting tags, ranges, signatories and metrological data.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re
import unicodedata
from xml_model.xml_generator import normalizar_certificado


def calibration_location(texto):
    """Extracts the phrase in parentheses describing where the calibration was performed
    (customer's facility, permanent facility or mobile/container installation)."""
    padrão = r"\((Calibration performed at the (?:customer's facility|permanent facility|mobile installation \(container\)))\)"
    m = re.search(padrão, texto)
    return m.group(1).strip() if m else None

def extrair_categoria_intrumento(texto):
    """Extracts the instrument category from "Objeto da Calibração:".

    Returns:
        str: Category found, or "NA" if the field does not exist or is empty.
    """
    padrao = r"Objeto da Calibração\s*:\s*([^\n\r]+)"
    m = re.search(padrao, texto, re.IGNORECASE)
    valor = m.group(1).strip() if m else ""
    return valor if valor else "NA"

def extrair_metering_class(texto):
    """Extracts the certificate's "Metering Class", stopping at "System Description:" or end of line."""
    padrao = r"Metering\s*Class:\s*(.*?)\s*(?=System\s*Description:|[\r\n]|$)"
    m = re.search(padrao, texto, re.IGNORECASE)
    return m.group(1).strip() if m else None

def extrair_curva_calibracao(texto):
    """Extracts the calibration curve coefficients in the form "y = a + b.x" (x and y in kPa).

    Args:
        texto: Text extracted from the certificate.

    Returns:
        dict: {"a": float, "b": float} with the coefficients found, or None
        if the "Y = a + b.X" pattern is not located in the text.
    """

    texto = texto.upper().replace(",", ".")

    padrao = r"Y\s*=\s*([\-0-9.]+)\s*\+\s*([0-9.]+)\s*[\.\*X×]\s*X"
    m = re.search(padrao, texto)

    if not m:
        return None

    return {
        "a": float(m.group(1)),
        "b": float(m.group(2))
    }

def aplicar_curva_kpa(valor_ma, curva):
    """Converts a value in mA to kPa using the certificate's calibration curve.

    The certificate's actual equation is mA = a + b * kPa, so the inverse
    conversion applied here is kPa = (mA - a) / b.

    Args:
        valor_ma: mA reading to be converted.
        curva: dict with keys "a" and "b", in the format returned by
            extrair_curva_calibracao.

    Returns:
        float: Value converted to kPa, or None if `valor_ma`/`curva` are
        invalid or if `b` is None/zero (division by zero).
    """
    if valor_ma is None or not curva:
        return None

    a = curva.get("a")
    b = curva.get("b")

    if a is None or b in (None, 0):
        return None

    return (valor_ma - a) / b

def normalizar_num(valor):
    """Converts `valor` to float, handling decimal commas.

    Returns:
        float: Converted value, or None if `valor` is None or non-numeric.
    """
    if valor is None:
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None

def normalizar_texto(texto):
    """Uppercases `texto` and strips accents (via NFKD decomposition).

    Returns:
        str: Normalized text, or None if `texto` is empty/None.
    """
    if not texto:
        return None
    texto = texto.upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))

def extrair_tag(texto):
    """Extracts the instrument TAG (text between "TAG:" and "SN:"), normalizing the
    different hyphen/dash types to "-" and collapsing spaces.

    The character class includes "." because some real TAGs use it as a
    segment separator (e.g. "PDT-EMED-3129.01-003") — without it, the
    match can never bridge past the period to reach "SN:", so the regex
    falls through to the certificate's second (empty) "TAG:"/"SN:" label
    row instead and the TAG comes back empty/not found.
    """
    padrao = r"TAG:\s*([0-9A-Za-zÀ-ÿ\-‐‒–—―.\s]+?)\s+SN:"
    m = re.search(padrao, texto)
    if not m:
        return None

    tag = m.group(1)

    tag = (
        tag.replace("‐", "-")
           .replace("‒", "-")
           .replace("–", "-")
           .replace("—", "-")
           .replace("―", "-")
    )

    return re.sub(r"\s*-\s*|\s+", "-", tag).strip("-")

def extrair_sn(texto):
    """Extracts the instrument's serial number and, if present, the sensor's.

    Searches all occurrences of "SN:" or "Num. de Série:" and keeps only
    the ones containing at least one digit (to discard false positives). The
    first valid occurrence is considered the instrument's SN and the second,
    if it exists, the sensor's SN.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        tuple: (sn_inst, sn_sensor), each a str or None if not found.
    """
    # The lookahead below stops the SN capture before the next FIELD LABEL on
    # the same line, so it doesn't swallow it as extra words of the SN value
    # (e.g. "SN: 1767380 Calibration Range: Min: 0°C..." -> SN must stop at
    # "1767380", not "1767380 Calibration"). A label is recognized as one OR
    # TWO words immediately followed by ":" — one word alone isn't enough,
    # since some real certificates glue multi-word labels right after SN on
    # the same line (e.g. "Calibration Range:", "Indication Range:"), and a
    # single-word check would only catch the second word ("Range:"), letting
    # the first ("Calibration") leak into the SN. "Nominal" is kept as a
    # standalone exception for a layout where it appears without a trailing
    # colon at all.
    #
    # The label lookahead's own word separator must be "[ \t]" (same line
    # only), not "\s" (which also matches newlines) — otherwise a genuine
    # last word of the SN, on its own line, gets mistaken for "word 1 of a
    # 2-word label" together with an unrelated label that starts the NEXT
    # line right after it (e.g. "SN: 9019D2645 448 7\nTAG: SN:..." — "7" is
    # part of the SN, "TAG:" is a separate field on the next line, but "\s"
    # bridges the line break and reads them as one "7 TAG:" label, dropping
    # the "7" from the captured SN).
    encontrados = re.findall(
        r"(?:SN|Num\.?\s*de\s*Série):\s*([\w./-]+(?:[ \t]+(?![\w./-]+(?:[ \t]+[\w./-]+)?[ \t]*:|Nominal\b)[\w./-]+)*)",
        texto,
        flags=re.IGNORECASE
    )
    sns_validos = [s for s in encontrados if any(c.isdigit() for c in s)]
    sn_inst = sns_validos[0] if len(sns_validos) >= 1 else None
    sn_sensor = sns_validos[1] if len(sns_validos) >= 2 else None
    return sn_inst, sn_sensor

def extrair_certificado(texto):
    """Extracts the certificate number (first occurrence of "Nº ...") and normalizes it."""
    m = re.search(r"Nº\s*([^\n]+)", texto)
    return normalizar_certificado(m.group(1).strip()) if m else None

def extrair_datas(texto):
    """Extracts the certificate's calibration date and report date.

    Returns:
        tuple: (data_calibracao, data_relatorio), each in "DD/MM/AAAA"
        format (str) or None if the respective field is not found.
    """
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

def data_proxima_calibracao(texto):
    """Extracts the next calibration date ("Next Calibration"/"Próxima Calibração")."""
    padrao = (
        r"(Next\s*Calibration|Próxima\s*Calibração)\s*:\s*"
        r"(\d{2}/\d{2}/\d{4})"
    )

    m = re.search(padrao, texto, flags=re.IGNORECASE)

    return m.group(2) if m else None

def extrair_nome_cliente(texto):
    """Extracts the client name from the "Name:"/"Nome:" field, stopping before "Contact:"/"Contato:"."""
    m = re.search(
        r"(Name|Nome):\s*([^\n\r]+?)(?:\s+(Contact|Contato):|$)",
        texto,
        flags=re.IGNORECASE
    )

    return m.group(2).strip() if m else None

def extrair_local(texto):
    """Extracts the calibration location name from inside the "CALIBRATION LOCATION:" block.

    First isolates the block of text between "CALIBRATION LOCATION:" and the
    next section ("CALIBRATED ITEM DESCRIPTION"/"CLIENT INFORMATION"), then
    searches for the "Name:"/"Nome:" field inside that block.

    Returns:
        str: Location name, or None if the block or field are not found.
    """
    bloco = re.search(
        r"CALIBRATION LOCATION:(.*?)(?:CALIBRATED ITEM DESCRIPTION|CLIENT INFORMATION|$)",
        texto,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not bloco:
        return None

    m = re.search(
        r"(Name|Nome):\s*([^\n\r\(]+?)(?:\s*\(|\s+Report\s+Date:|\s+Calibration\s+Date:|\n|\r|$)",
        bloco.group(1),
        flags=re.IGNORECASE
    )

    return m.group(2).strip() if m else None

def extrair_sistema(texto):
    """Extracts the system description ("System Description:"/"Descrição do Sistema:").

    The capture runs until the next known section label (Name, Address,
    Calibrated, Classification/Classificação, Periodicity/Periodicidade, Next
    Calibration/Próxima Calibração, LOCAL ENVIRONMENTAL, REFERENCE STANDARDS,
    ITEM, TAG or SN); multiple spaces are collapsed and any periodicity
    fragment that "leaked" into the capture is stripped out.

    Returns:
        str: System description, or None if the field is not found.
    """
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

    sistema = re.sub(
        r"\b(Periodicity|Periodicidade)\b.*$",
        "",
        sistema,
        flags=re.IGNORECASE
    ).strip()

    return sistema

def extrair_range_calibrado(texto):
    """Extracts the Min/Max limits of the certificate's "Calibration Range".

    First tries the main pattern ("Calibration Range ... Min: X ... Max: Y");
    if it fails, falls back to matching just "Range: Min: X ... Max: Y",
    because pdfplumber sometimes fragments the word "Calibration" in
    multi-column layouts, merging it with the instrument's model number.

    Returns:
        tuple: (min, max) as float, or (None, None) if no pattern matches.
    """
    # Main pattern: "Calibration Range ... Min: X ... Max: Y"
    padrao = r"""
    Calibration\s*Range.*?
    Min\s*[:\-]?\s*([-+]?[0-9.,]+)
    .*?
    Max\s*[:\-]?\s*([-+]?[0-9.,]+)
    """
    m = re.search(padrao, texto, flags=re.I | re.S | re.VERBOSE)
    if m:
        return normalizar_num(m.group(1)), normalizar_num(m.group(2))

    # Fallback: pdfplumber sometimes fragments "Calibration" in multi-column layouts,
    # merging it with the model number. "Range:" stays intact.
    m = re.search(
        r"Range\s*:\s*Min\s*:\s*([-+]?[0-9.,]+).*?Max\s*:\s*([-+]?[0-9.,]+)",
        texto, flags=re.I | re.S,
    )
    if m:
        return normalizar_num(m.group(1)), normalizar_num(m.group(2))

    return None, None

def extrair_range_indicado(texto):
    """Extracts the Min/Max limits of the certificate's "Indication Range".

    Returns:
        tuple: (min, max) as float, or (None, None) if the pattern does not match.
    """
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

def extrair_resolucao(texto):
    """Extracts the numeric value of the "Resolution:" field (in kPa, Pa, bar or mbar)."""
    padrao = r"Resolution\s*:\s*([\d.,]+)\s*(kPa|Pa|bar|mbar)"
    m = re.search(padrao, texto, flags=re.I)
    return normalizar_num(m.group(1)) if m else None

def extrair_haste(texto):
    """Extracts the rod length ("Rod length:") and the probe diameter ("Probe diameter:").

    Returns:
        tuple: (rod_length, probe_diameter) as float, each None if absent.
    """
    rod = re.search(r"Rod length:\s*([\d,.]+)", texto, flags=re.IGNORECASE)
    probe = re.search(r"Probe diameter:\s*([\d,.]+)", texto, flags=re.IGNORECASE)

    return (
        normalizar_num(rod.group(1)) if rod else None,
        normalizar_num(probe.group(1)) if probe else None
    )

def extrair_indicadores_metrologicos(texto):
    """Extracts Repeatability, Hysteresis, Fiducial Error and Uncertainty from the
    certificate's metrological characteristics table.

    The regex first locates the section header and the labels of the four
    columns (in English or Portuguese), and only then captures the four
    corresponding numeric values, which makes it resilient to small layout
    variations between certificates.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        dict: Keys "repetibilidade", "histerese", "erro_fiducial" and
        "incerteza", each a float or None; all None if the pattern does not match.
    """

    padrao = r"""
    (Metrological\ characteristics|Caracter[ií]sticas\ metrol[oó]gicas)
    .*?
    (Repeatability|Repetibilidade)
    .*?
    (Hysteresis|Histerese)
    .*?
    (Fiducial\s*Error|Erro\s*Fiducial)
    .*?
    (Uncertainty|Incerteza)
    .*?
    ([-+]?\d+[.,]\d+)\s*%?
    \s+
    ([-+]?\d+[.,]\d+)\s*%?
    \s+
    ([-+]?\d+[.,]\d+)\s*%?
    \s+
    ([-+]?\d+[.,]\d+)\s*%?
    """

    m = re.search(
        padrao,
        texto,
        flags=re.IGNORECASE | re.DOTALL | re.VERBOSE
    )

    if not m:
        return {
            "repetibilidade": None,
            "histerese": None,
            "erro_fiducial": None,
            "incerteza": None
        }

    return {
        "repetibilidade": normalizar_num(m.group(6)),
        "histerese": normalizar_num(m.group(7)),
        "erro_fiducial": normalizar_num(m.group(8)),
        "incerteza": normalizar_num(m.group(9))
    }

def endereco_cliente(texto):
    """Extracts the client address from inside the "CLIENT INFORMATION"/"INFORMAÇÕES DO CLIENTE" block."""
    if not texto:
        return None

    padrao = re.search(
        r"(?:CLIENT INFORMATION|INFORMAÇÕES DO CLIENTE).*?"
        r"(?:Address|Endereço)\s*:\s*"
        r"([^\n\r]+)",
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )

    return padrao.group(1).strip() if padrao else None


SIGNATARIOS_VALIDOS = [
    "Francisco Nascimento",
    "Marcio Martirios",
    "Leonardo Tonim",
    "Matheus Moraes",
    "Iago Fiuza",
    "Caio Campos",
    "Nathan Santos",
    "Marcus Fioravante",
]

def extrair_assinaturas(texto):
    """Extracts the name that appears right above the signature label on the certificate.

    Looks for a line in uppercase/title case followed, on the next line, by
    "Signatory", "Signatário", "Calibration Executor" or "Executor da
    Calibração".

    Returns:
        str: Raw name found (not yet split into signatory/executor by
        separar_signatario), or None if the pattern does not match.
    """
    if not texto:
        return None

    texto_limpo = texto.replace("\r", "\n")

    padrao = re.search(
        r"\n\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇà-ú\s]+?)\s*\n\s*"
        r"(Signatory|Signatário|Calibration\s+Executor|Executor\s+da\s+Calibração)",
        texto_limpo,
        flags=re.IGNORECASE
    )

    return padrao.group(1).strip() if padrao else None

def separar_signatario(assinaturas_raw, signatarios_validos):
    """Splits the raw signature text into which name is the official signatory
    (from the SIGNATARIOS_VALIDOS list) and which is the calibration executor.

    Args:
        assinaturas_raw: Text returned by extrair_assinaturas, usually
            containing both names concatenated.
        signatarios_validos: List of names recognized as official signatories.

    Returns:
        dict: {"signatario": str|None, "executante": str|None}. If no name
        from the list is found, the whole text is assigned to "executante" and
        "signatario" is None; if `assinaturas_raw` is empty, both are None.
    """
    if not assinaturas_raw:
        return {
            "signatario": None,
            "executante": None
        }

    texto = " ".join(assinaturas_raw.split())  # normalizes whitespace

    for signatario in signatarios_validos:
        if signatario in texto:
            executante = texto.replace(signatario, "").strip()

            return {
                "signatario": signatario,
                "executante": executante if executante else None
            }

    # if no valid signatory is found
    return {
        "signatario": None,
        "executante": texto
    }

def extrair_condicoes_ambientais(texto):
    """Extracts ambient temperature and humidity ("Ambient Temperature:"/"Ambient Humidity:").

    Returns:
        dict: {"temperatura_ambiente": float|None, "umidade_ambiente": float|None}.
    """
    resultado = {
        "temperatura_ambiente": None,
        "umidade_ambiente": None
    }

    # AMBIENT TEMPERATURE
    padrao_temp = re.search(
        r"Ambient\s+Temperature:\s*([\d.,]+)\s*°?\s*C",
        texto,
        flags=re.IGNORECASE
    )

    if padrao_temp:
        resultado["temperatura_ambiente"] = float(
            padrao_temp.group(1).replace(",", ".")
        )

    # AMBIENT HUMIDITY
    padrao_umid = re.search(
        r"Ambient\s+Humidity:\s*([\d.,]+)\s*%",
        texto,
        flags=re.IGNORECASE
    )

    if padrao_umid:
        resultado["umidade_ambiente"] = float(
            padrao_umid.group(1).replace(",", ".")
        )

    return resultado

def extrair_padroes(texto):
    """Extracts the list of reference standards used in the calibration.

    Locates the "PADRÕES DE REFERÊNCIA:" block and, for each line inside it,
    tries to match the pattern "<type>, AF<no>, Cert. no <certificate>, Val. <mm/yyyy>,
    CAL<no>/RBC"; lines that do not follow this format are ignored.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        list[dict]: One dict per recognized standard, with keys "tipo",
        "identificacao", "certificado", "validade" and "procedimento_calib".
        Empty list if the block does not exist or no line matches.
    """
    padroes = []

    
    bloco_match = re.search(
        r"PADRÕES DE REFERÊNCIA:(.*?)(?:\n\s*\n|$)",
        texto,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not bloco_match:
        return padroes

    bloco = bloco_match.group(1)

    linhas = [
        l.strip()
        for l in bloco.splitlines()
        if l.strip()
    ]

    regex_padrao = re.compile(
        r"""
        (?P<tipo>[^,]+),\s*
        (?P<identificacao>AF\s*\d+[A-Za-z]?),\s*
        Cert\.?\s*n[ºo]\s*(?P<certificado>[^,]+),\s*
        Val\.?\s*(?P<validade>\d{2}/\d{4}),\s*
        (?P<procedimento>CAL\s*\d+\s*/\s*RBC)
        """,
        flags=re.IGNORECASE | re.VERBOSE
    )

    for linha in linhas:
        m = regex_padrao.search(linha)
        if not m:
            continue

        padroes.append({
            "tipo": m.group("tipo").strip(),
            "identificacao": m.group("identificacao").strip(),
            "certificado": m.group("certificado").strip(),
            "validade": m.group("validade").strip(),
            "procedimento_calib": m.group("procedimento").strip()
        })

    return padroes

MAPA_PROCEDIMENTOS = [{
    "categorias": [ "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA", "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA" ],
    "procedimento": "7.2 TM-005 Pressure Transmitters",
    "descricao": "A calibração consistiu na medição de quatro vezes cada ponto de pressão (dois ciclos de carga e descaga) comparando com um padrão, na sua posição de trabalho e utilizando o procedimento 7.2 TM-005  Pressure Transmitters"
},
{
    "categorias": [ "MANOMETRO ANALÓGICO", "MANOMETRO DIGITAL", "MANOMETRO DIGITAL ABSOLUTO", "MANOMETRO DIFERENCIAL ANALÓGICO", "MANOMETRO DIFERENCIAL DIGITAL" ],
    "procedimento": "7.2 TM-002 Manometers",
    "descricao": "A calibração consistiu na medição de quatro vezes cada ponto de pressão (dois ciclos de carga e descaga) comparando com um padrão, na sua posição de trabalho e utilizando o procedimento 7.2 TM-002 Manometers"
},
{
    "categorias": ["TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA", "TRANSMISSOR DE TEMPERATURA"],
    "procedimento": "7.2 TM-004 Temperature Transmitter",
    "descricao": "A calibração consistiu na medição de três vezes cada ponto calibrado em um ciclo de subida e outro de descida, conforme o procedimento 7.2 TM-004 Temperature Transmitter"
},
{
    "categorias": [ "TERMÔMETRO ANALÓGICO", "TERMÔMETRO DIGITAL", ],
    "procedimento": "7.2 TM-001 Temperature Meter with Sensor",
    "descricao": "O sensor do instrumento e o sensor padrão de referência foram introduzidos no banho térmico e a calibração foi realizada através da comparação direta entre as indicações do instrumento e do padrão de referência. As medições foram realizadas após a estabilização, confirmada pelas leituras do padrão em 3 séries de medições alternadas, com intervalos de 1 minuto. A calibração foi realizado conforme procedimento 7.2 TM-001 Temperature Meter with Sensor, , no qual esta de acordo aos requisitos da norma NBR 14610"
},
{
    "categorias": [ "TERMORRESISTÊNCIA PT‐100 ‐ 2 FIOS", "TERMORRESISTÊNCIA PT‐100 ‐ 3 FIOS", "TERMORRESISTÊNCIA PT‐100 ‐ 4 FIOS", 'Termorresistência PT-100 - 4 Fios', 'Termorresistência PT-100 - 3 Fios', 'Termorresistência PT-100 - 2 Fios'],
    "procedimento": "7.2 TM-006 Thermoresistances",
    "descricao": "O sensor do instrumento e o sensor padrão de referência foram introduzidos no bloco seco e a calibração foi realizada através da comparação direta entre as indicações do instrumento e do padrão de referência. As medições foram realizadas após a estabilização, confirmada pelas leituras do padrão em 3 séries de medições alternadas. A calibração foi realizado conforme procedimento 7.2 TM-006 Thermoresistances, no qual esta de acordo aos requisitos da norma  NBR 13772"
},
{
    "categorias": ['PLACA DE ORIFICIO'],
    "procedimento": "TM-003 Dimensional Measurement",
    "descricao": "As medições foram relizadas através da comparação direta utilizando-se equipamentos de medição convencionais. Os parâmetros e a quantidade de medições executadas no artefato estão em conformidade com TM-003 Dimensional Measurement, baseado na AGA 3, Parte 2, de 2000"
},

]

'Termorresistência PT-100 - 3 Fios'

def obter_procedimento_por_categoria(categoria_instrumento):
    """Looks up in MAPA_PROCEDIMENTOS the calibration procedure and description
    associated with the instrument category (substring match, case-insensitive).

    Args:
        categoria_instrumento: Instrument category name, as returned by
            extrair_categoria_intrumento.

    Returns:
        dict: {"procedimento": str, "descricao": str} from the first entry of
        MAPA_PROCEDIMENTOS whose category matches, or None if none matches or
        `categoria_instrumento` is empty.
    """
    if not categoria_instrumento:
        return None

    categoria_norm = categoria_instrumento.upper()

    for item in MAPA_PROCEDIMENTOS:
        for cat in item["categorias"]:
            if cat.upper() in categoria_norm:
                return {
                    "procedimento": item["procedimento"],
                    "descricao": item["descricao"]
                }

    return None

def extrair_fabricante(texto):
    """Extracts the manufacturer ("Manufacturer:"/"Maker:"), stopping before the
    Model/Modelo, Output or TAG fields that usually follow it on the same line."""
    padrao = re.search(
        r"(?:Manufacturer|Maker)\s*:\s*(.+?)(?=\s+(?:Model|Modelo|Output|TAG)\s*:|$)",
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )

    if padrao:
        return padrao.group(1).strip()

    return None

def extrair_modelo(texto):
    """Extracts the certificate's model ("Model:")."""
    if not texto:
        return None

    padrao = re.search(
        r"Model:\s*([A-Z0-9\-/]+)",
        texto,
        flags=re.IGNORECASE
    )

    return padrao.group(1).strip() if padrao else None


def extrair_tag_sensor(texto):
    """Extracts the sensor TAG from inside the "Sensor Information" block (field "Tag"/"TAG"/"Sensor Tag")."""

    if not texto:
        return None

    padrao = re.search(
        r"Sensor Information[\s\S]*?(?:Tag|TAG|Sensor Tag)\s*[:\-]?\s*([A-Z0-9\-_/]+)",
        texto,
        flags=re.IGNORECASE
    )

    if padrao:
        return padrao.group(1).strip()

    return None

def extrair_tipo_sensor(texto):
    """Extracts the sensor type in Portuguese from the certificate's "Sensor Type"
    field, returning only the text after the slash ("EN/PT")."""

    if not texto:
        return None

    match = re.search(
        r"Sensor Type\s*:\s*.*?/\s*([^\n\r]+)",
        texto,
        flags=re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return None

LOCALIZACOES_ORIGEM = {
    "1100": "Anambé",
    "1200": "Arapaçu",
    "1300": "Cidade de São Miguel dos Campos",
    "1400": "Furado",
    "1500": "Paru",
    "1600": "Pilar",
    "1700": "São Miguel dos Campos",
    "1900": "ESGN",
    "2100": "Conceição",
    "2400": "Quererá",
}


def _normalizar_tag_relacionado(tag):
    """Normalizes a TAG for comparison: uppercase, assorted dashes
    converted to "-" and all spaces removed."""
    if not tag:
        return ""
    tag = tag.strip().upper()
    for ch in "‐‒–—―":
        tag = tag.replace(ch, "-")
    return re.sub(r"\s+", "", tag)


def extrair_itens_relacionados(texto):
    """Parses an Origem "Itens Relacionados" (Related Items) document (e.g.: LDN-030.pdf
    — a file separate from the certificates, chosen by the user) and
    returns a dict {tag_normalizada: (numero_ac, localizacao)} with one
    entry per "AC - Análise Crítica - <TAG>" line whose location (4
    digits right after "AC-") is recognized.

    The extracted text glues the "Nome" column to the "Descrição" column
    with no space, e.g.: "AC-1600.0000-6252-812-O2C-574AC - Análise Crítica - PDT-124402"
    — the part before the 2nd "AC" is the AC number.

    Args:
        texto: Text extracted from the related items document.

    Returns:
        dict: Maps each normalized TAG (via _normalizar_tag_relacionado)
        to the tuple (numero_ac, localizacao); empty dict if `texto` is empty
        or no recognizable line is found.
    """
    resultado = {}
    if not texto:
        return resultado

    padrao = re.compile(
        r"(AC-(\d{4})\.\d+-\d+-\d+-O2C-\d+)\s*AC\s*-\s*An[áa]lise\s*Cr[íi]tica\s*-\s*([^\n\r]+)",
        re.IGNORECASE,
    )

    for m in padrao.finditer(texto):
        codigo, cod_local, tag_desc = m.group(1), m.group(2), m.group(3)
        localizacao = LOCALIZACOES_ORIGEM.get(cod_local)
        if not localizacao:
            continue
        tag_norm = _normalizar_tag_relacionado(tag_desc)
        if tag_norm:
            resultado[tag_norm] = (codigo, localizacao)

    return resultado


def buscar_item_relacionado(mapa_itens_relacionados, tag):
    """Looks up the dict built by extrair_itens_relacionados for this certificate's TAG.

    Args:
        mapa_itens_relacionados: Dict returned by extrair_itens_relacionados.
        tag: TAG of the current certificate's instrument (will be normalized before the lookup).

    Returns:
        tuple: (numero_ac, localizacao) if the TAG is found, or (None, None)
        otherwise (including when `mapa_itens_relacionados` or `tag` are empty).
    """
    if not mapa_itens_relacionados or not tag:
        return None, None
    return mapa_itens_relacionados.get(_normalizar_tag_relacionado(tag), (None, None))


def extrair_codigo_ods(certificado: str) -> str | None:
    """Extracts the sequential number of the ODS code from a certificate number (pattern "ODS-<number>")."""
    if not certificado:
        return None

    padrao = r"ODS\s*[‐-–—-]\s*(\d+)"
    m = re.search(padrao, certificado.upper())
    return m.group(1) if m else None


def extrair_campos(texto: str) -> dict:
    """Builds the complete field dictionary for a secondary instrument certificate.

    Orchestrates every extractor in this module (TAG, serial numbers,
    certificate, category, calibration location, dates, system, class,
    calibrated/indicated ranges, rod/probe, metrological indicators, calibration
    curve, client, signatures, ambient conditions, standards, procedure,
    manufacturer, model and sensor type) to produce the dataset used to
    populate the AC template.

    Args:
        texto: Text extracted from the certificate.

    Returns:
        dict: All the certificate's fields, ready for use by the rest of
        the system (see the keys in the returned dict for the full list).
    """
    tag = extrair_tag(texto)
    tag_sen = extrair_tag_sensor(texto)
    sn_inst, sn_sensor = extrair_sn(texto)
    certificado = extrair_certificado(texto)
    cod = extrair_codigo_ods(extrair_certificado(texto))
    categoria = extrair_categoria_intrumento(texto)
    calibration_loc = calibration_location(texto)
    data_cal, report_date = extrair_datas(texto)
    prox_cal = data_proxima_calibracao(texto)
    local = extrair_local(texto)
    cla = extrair_metering_class(texto)
    sistema = extrair_sistema(texto)
    resolucao=extrair_resolucao(texto)
    min_range, max_range = extrair_range_calibrado(texto)
    inmin_range, inmax_range = extrair_range_indicado(texto)
    rod_length, probe_diameter = extrair_haste(texto)
    ind = extrair_indicadores_metrologicos(texto)
    curva_de_calibracao = extrair_curva_calibracao(texto)
    cliente = extrair_nome_cliente(texto)
    endereco_cli= endereco_cliente(texto)
    exe_sig = separar_signatario(extrair_assinaturas(texto), SIGNATARIOS_VALIDOS)
    condicoes_amb = extrair_condicoes_ambientais(texto)
    padroes = extrair_padroes(texto)
    proced= obter_procedimento_por_categoria(categoria)
    fab = extrair_fabricante(texto)
    model = extrair_modelo(texto)
    tip_sens = extrair_tipo_sensor(texto)

    return {
        "tag": tag,
        "sn_instrumento": sn_inst,
        "sn_sensor": sn_sensor,
        "tag_sensor": tag_sen,
        "tipo_sensor": tip_sens,
        "certificado": certificado,
        "cod_certificado": cod,
        "categoria": categoria,
        'cliente': cliente,
        "local_calibracao": calibration_loc,
        "data": data_cal,
        "proxima_cal": prox_cal,
        "local": local,
        "sistema": sistema,
        "classe": cla,
        "report_date": report_date,
        "min_range": min_range,
        "max_range": max_range,
        "inmin_range": inmin_range,
        "inmax_range": inmax_range,
        'resolucao': resolucao,
        "rod_length": rod_length,
        "probe_diameter": probe_diameter,
        "indicadores_metrologicos": ind,
        "curva_de_calibracao": curva_de_calibracao,
        'endereco_cliente': endereco_cli,
        "exec_sig": exe_sig,
        "cond_amb": condicoes_amb,
        "padroes_utilizados": padroes,
        "procedimento": proced,
        "fabricante": fab,
        "modelo": model,
    }


