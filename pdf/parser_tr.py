import re
from pdf.parser_certificados import (
    extrair_certificado, extrair_datas, endereco_cliente,
    SIGNATARIOS_VALIDOS, extrair_assinaturas, separar_signatario,
    extrair_padroes,
)
from pdf.parser_po import coeficiente_dilatacao


PROCEDIMENTO_TR = {
    "procedimento": "7.2 TM-003 Dimensional",
    "descricao": (
        "As medições foram realizadas através da comparação direta utilizando-se "
        "equipamentos de medição convencionais. Os parâmetros e a quantidade de "
        "medições executadas no artefato estão em conformidade com 7.2 TM-003 "
        "Dimensional, baseado na ISO 5167-2:2022"
    ),
}


def identificar_tr(texto):
    return bool(re.search(r"Gas Meter Run|Trecho Reto de Medi", texto, re.IGNORECASE))


def extrair_nome_cliente_tr(texto):
    # "Name / Nome: PRIO Contact/Contato: metering@..."
    m = re.search(r"Nome:\s*(.+?)\s+Contact/Contato:", texto, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extrair_local_tr(texto):
    # "CALIBRATION LOCATION / Local de Calibração:\nName / Nome: FPSO Bravo"
    bloco = re.search(
        r"CALIBRATION LOCATION.*?:(.*?)(?=ITEM DESCRIPTION|$)",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not bloco:
        return None
    m = re.search(r"Nome:\s*([^\n\r]+)", bloco.group(1), re.IGNORECASE)
    return m.group(1).strip() if m else None


def extrair_data_medicao(texto):
    # "Measurement Date / Data da Medição: 12/11/2025"
    m = re.search(r"Measurement Date.*?:\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    return m.group(1) if m else None


def extrair_condicoes_ambientais_tr(texto):
    # "Ambient Temperature / Temperatura Ambiente: 21,9°C REF ..."
    resultado = {"temperatura_ambiente": None, "umidade_ambiente": None}

    m_temp = re.search(
        r"(?:Ambient\s+Temperature|Temperatura\s+Ambiente).*?:\s*([\d,\.]+)\s*°?C",
        texto,
        flags=re.IGNORECASE,
    )
    if m_temp:
        resultado["temperatura_ambiente"] = float(m_temp.group(1).replace(",", "."))

    m_umid = re.search(
        r"(?:Ambient\s+Humidity|Umidade\s+Ambiente).*?:\s*([\d,\.]+)\s*%",
        texto,
        flags=re.IGNORECASE,
    )
    if m_umid:
        resultado["umidade_ambiente"] = float(m_umid.group(1).replace(",", "."))

    return resultado


def material_tr(texto):
    # "Material of Pipe / Orifice Carrier: Duplex - Coefficient: ..."
    m = re.search(
        r"Material of Pipe.*?:\s*([A-Za-z\s]+?)\s*-\s*Coefficient",
        texto,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def extrair_diametro_nominal_tr(texto):
    # 'Nominal Diameter / Diâmetro Nominal: 2"'
    m = re.search(r'Nominal Diameter.*?:\s*([\d,\.]+)\s*"', texto, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extrair_tag_sistema_tr(texto):
    # "Identification / identificação: FX-1025-03"
    m = re.search(
        r"Identification\s*/\s*identifica[çc][aã]o\s*:\s*([A-Z0-9\-]+)",
        texto,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def extrair_componentes_tr(texto):
    """
    Extrai TAG e SN dos três componentes do trecho reto:
    - Orifice Carrier  → PORTA PLACA
    - Upstream Pipe    → TRECHO MONTANTE
    - Downstream Pipe  → TRECHO JUSANTE

    Regra de separação: o separador TAG/SN é a primeira barra precedida de espaço
    (" /"), que distingue o "/" do separador dos "/" internos (N/A, TR00916-21/2.1).
    Se não houver separador → TAG = "NI", SN = valor completo.
    SN termina antes de \n ou texto com letras minúsculas; admite sufixo posicional
    de exatamente 1 letra maiúscula + 1 dígito (ex: M1, J1).
    """
    padroes = [
        (r"Orifice Carrier\s*/\s*Porta Placa", "PORTA PLACA"),
        (r"Upstream Pipe", "TRECHO MONTANTE"),
        (r"Downstream Pipe", "TRECHO JUSANTE"),
    ]

    # TAG: valor compacto (alfanum + /-.) antes do separador " /"
    # SN:  mesmo padrão + sufixo opcional de exatamente [A-Z][0-9] (ex: M1, J1)
    _tag = r"[A-Z0-9][A-Z0-9/\-\.]*"
    _sn  = r"[A-Z0-9][A-Z0-9/\-\.]*(?:\s+[A-Z][0-9])?"

    componentes = []
    for padrao_nome, tipo in padroes:
        m = re.search(
            padrao_nome
            + r"[^\n]*?TAG\s*/\s*SN\s*:\s*"
            + rf"(?:({_tag})\s+/\s*)?"  # TAG opcional: valor antes do primeiro " /"
            + rf"({_sn})",              # SN: valor compacto + sufixo posicional
            texto,
            flags=re.IGNORECASE,
        )
        if m:
            tag = m.group(1).strip() if m.group(1) else "NI"
            sn  = m.group(2).strip() if m.group(2) else "NI"
            componentes.append({"tipo": tipo, "tag": tag, "sn": sn})

    return componentes


def extrair_condicionador_fluxo(texto):
    # "Zanker TAG / SN: N/A"  →  "Nenhum"  |  SN presente  →  "Zanker"
    m = re.search(r"Zanker\s+TAG\s*/\s*SN\s*:\s*([^\s\n\r]+)", texto, re.IGNORECASE)
    if m:
        return "Nenhum" if m.group(1).strip().upper() == "N/A" else "Zanker"
    if re.search(r"19\s+(?:tubes?|tubos?)", texto, re.IGNORECASE):
        return "19 tubos"
    return "Nenhum"


def extrair_campos_tr(texto):
    texto = re.sub(r"[‐–—]", "-", texto)
    certificado = extrair_certificado(texto)
    _, report_date = extrair_datas(texto)
    data_medicao = extrair_data_medicao(texto)
    nome_cliente = extrair_nome_cliente_tr(texto)
    endereco_cli = endereco_cliente(texto)
    local = extrair_local_tr(texto)
    exec_sig = separar_signatario(extrair_assinaturas(texto), SIGNATARIOS_VALIDOS)
    cond_amb = extrair_condicoes_ambientais_tr(texto)
    padroes = extrair_padroes(texto)
    material = material_tr(texto)
    coef = coeficiente_dilatacao(texto)
    diametro_t = extrair_diametro_nominal_tr(texto)
    tag_sistema = extrair_tag_sistema_tr(texto)
    componentes = extrair_componentes_tr(texto)
    condicionador = extrair_condicionador_fluxo(texto)

    porta_placa = next((c for c in componentes if c["tipo"] == "PORTA PLACA"), {})

    return {
        "certificado": certificado,
        "instrumento": "Gas Meter Run",
        "data_calibracao": data_medicao,
        "report_date": report_date,
        "cliente": nome_cliente,
        "endereco_cliente": endereco_cli,
        "local": local,
        "exec_sig": exec_sig,
        "cond_amb": cond_amb,
        "padroes_utilizados": padroes,
        "tag": porta_placa.get("tag"),
        "sn_inst": porta_placa.get("sn"),
        "material": material,
        "coef": coef,
        "norma": "ISO 5167-2:2022",
        "diametro_tubo": diametro_t,
        "procedimento": PROCEDIMENTO_TR,
        "tag_sistema": tag_sistema,
        "componentes": componentes,
        "condicionador_fluxo": condicionador,
    }