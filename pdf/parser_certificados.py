import re
import unicodedata
from xml_model.xml_generator import normalizar_certificado


def calibration_location(texto):
    padrão = r"\((Calibration performed at the (?:customer's facility|permanent facility|mobile installation \(container\)))\)"
    m = re.search(padrão, texto)
    return m.group(1).strip() if m else None

def extrair_categoria_intrumento(texto):
    padrao = r"Objeto da Calibração\s*:\s*([^\n\r]+)"
    m = re.search(padrao, texto, re.IGNORECASE)
    valor = m.group(1).strip() if m else ""
    return valor if valor else "NA"

def extrair_metering_class(texto):
    padrao = r"Metering\s*Class:\s*(.*?)\s*(?=System\s*Description:|[\r\n]|$)"
    m = re.search(padrao, texto, re.IGNORECASE)
    return m.group(1).strip() if m else None

def extrair_curva_calibracao(texto):
    """
    Extrai curva do tipo:
    y = a + b.x
    onde x e y estão em kPa
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
    """
    Converte mA → kPa usando a curva do certificado.
    Equação REAL do certificado:
        mA = a + b * kPa
        => kPa = (mA - a) / b
    """
    if valor_ma is None or not curva:
        return None

    a = curva.get("a")
    b = curva.get("b")

    if a is None or b in (None, 0):
        return None

    return (valor_ma - a) / b

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
    padrao = r"TAG:\s*([0-9A-Za-zÀ-ÿ\-‐‒–—―\s]+?)\s+SN:"
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
    encontrados = re.findall(
        r"(?:SN|Num\.?\s*de\s*Série):\s*([\w.-]+(?:[ \t]+(?![\w.-]+\s*:|Nominal\b)[\w.-]+)*)",
        texto,
        flags=re.IGNORECASE
    )
    sns_validos = [s for s in encontrados if any(c.isdigit() for c in s)]
    sn_inst = sns_validos[0] if len(sns_validos) >= 1 else None
    sn_sensor = sns_validos[1] if len(sns_validos) >= 2 else None
    return sn_inst, sn_sensor

def extrair_certificado(texto):
    m = re.search(r"Nº\s*([^\n]+)", texto)
    return normalizar_certificado(m.group(1).strip()) if m else None

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

def data_proxima_calibracao(texto):
    padrao = (
        r"(Next\s*Calibration|Próxima\s*Calibração)\s*:\s*"
        r"(\d{2}/\d{2}/\d{4})"
    )

    m = re.search(padrao, texto, flags=re.IGNORECASE)

    return m.group(2) if m else None

def extrair_nome_cliente(texto):
    m = re.search(
        r"(Name|Nome):\s*([^\n\r]+?)(?:\s+(Contact|Contato):|$)",
        texto,
        flags=re.IGNORECASE
    )

    return m.group(2).strip() if m else None

def extrair_local(texto):
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

def extrair_resolucao(texto):
    padrao = r"Resolution\s*:\s*([\d.,]+)\s*(kPa|Pa|bar|mbar)"
    m = re.search(padrao, texto, flags=re.I)
    return normalizar_num(m.group(1)) if m else None

def extrair_haste(texto):
    rod = re.search(r"Rod length:\s*([\d,.]+)", texto, flags=re.IGNORECASE)
    probe = re.search(r"Probe diameter:\s*([\d,.]+)", texto, flags=re.IGNORECASE)

    return (
        normalizar_num(rod.group(1)) if rod else None,
        normalizar_num(probe.group(1)) if probe else None
    )

def extrair_indicadores_metrologicos(texto):
    """
    Extrai Repetibilidade, Histerese, Erro Fiducial e Incerteza
    de forma robusta, mesmo com variações no PDF.
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
    if not assinaturas_raw:
        return {
            "signatario": None,
            "executante": None
        }

    texto = " ".join(assinaturas_raw.split())  # normaliza espaços

    for signatario in signatarios_validos:
        if signatario in texto:
            executante = texto.replace(signatario, "").strip()

            return {
                "signatario": signatario,
                "executante": executante if executante else None
            }

    # se nenhum signatário válido for encontrado
    return {
        "signatario": None,
        "executante": texto
    }

def extrair_condicoes_ambientais(texto):
    resultado = {
        "temperatura_ambiente": None,
        "umidade_ambiente": None
    }

    # TEMPERATURA AMBIENTE
    padrao_temp = re.search(
        r"Ambient\s+Temperature:\s*([\d.,]+)\s*°?\s*C",
        texto,
        flags=re.IGNORECASE
    )

    if padrao_temp:
        resultado["temperatura_ambiente"] = float(
            padrao_temp.group(1).replace(",", ".")
        )

    # UMIDADE AMBIENTE
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
    """
    Extrai somente o fabricante, ignorando:
    - Model
    - Output
    - TAG
    """
    padrao = re.search(
        r"(?:Manufacturer|Maker)\s*:\s*(.+?)(?=\s+(?:Model|Modelo|Output|TAG)\s*:|$)",
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )

    if padrao:
        return padrao.group(1).strip()

    return None

def extrair_modelo(texto):
    """
    Extrai o modelo (Model) do certificado.
    """
    if not texto:
        return None

    padrao = re.search(
        r"Model:\s*([A-Z0-9\-/]+)",
        texto,
        flags=re.IGNORECASE
    )

    return padrao.group(1).strip() if padrao else None


def extrair_tag_sensor(texto):
    """
    Extrai a TAG do sensor localizada no bloco 'Sensor Information'
    """

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
    """
    Extrai o tipo do sensor (PT-BR) a partir do campo 'Sensor Type',
    retornando o texto após a barra (/).
    """

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

def extrair_codigo_ods(certificado: str) -> str | None:
    if not certificado:
        return None

    padrao = r"ODS\s*[‐-–—-]\s*(\d+)"
    m = re.search(padrao, certificado.upper())
    return m.group(1) if m else None


def extrair_campos(texto: str) -> dict:
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
        "modelo": model
        
    }


