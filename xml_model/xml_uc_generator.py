import re
import xml.etree.ElementTree as ET

from xml_model.xml_common import salvar_xml_bonito

_NUM_RE = re.compile(r'^\d[\d.,]*$')
# Caracteres inválidos em XML 1.0 (exceto tab \x09, newline \x0A e CR \x0D)
_INVALID_XML = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')


def _sanitize(text: str) -> str:
    return _INVALID_XML.sub(' ', str(text)).strip()


def _num(v: str) -> str:
    return v if _NUM_RE.match(v.strip()) else "NI"


def sub(parent, tag, text="", **attrs):
    el = ET.SubElement(parent, tag, **attrs)
    el.text = _sanitize(text)
    return el


def criar_bloco_padrao(root, tag_bloco, d, com_diametro=False):
    """Bloco Tag/[Diameter]/U/CoverageFactor/MaxError/CertificateNumber comum a
    GasMeterRun, OrificePlate, PressureTransmitter, TemperatureTransmitter e
    TemperatureSensor — a única diferença entre esses blocos é o nome da tag XML,
    a chave de origem em `dados` e a presença (ou não) do campo Diameter."""
    bloco = ET.SubElement(root, tag_bloco)
    sub(bloco, "Tag", d.get("tag", "NI"))
    if com_diametro:
        sub(bloco, "Diameter", d.get("diametro", "NI"))
    sub(bloco, "U",                _num(d.get("u",       "")))
    sub(bloco, "CoverageFactor",   _num(d.get("fator_k", "")))
    sub(bloco, "MaxError",         _num(d.get("erro",    "")))
    sub(bloco, "CertificateNumber", d.get("certificado", "NI"))
    return bloco


def criar_gas_meter_run(root, dados):
    criar_bloco_padrao(root, "GasMeterRun", dados.get("trecho", {}), com_diametro=True)


def criar_orifice_plate(root, dados):
    criar_bloco_padrao(root, "OrificePlate", dados.get("placa", {}), com_diametro=True)


def criar_pd_transmitter(root, dados, range_: str, chave: str):
    if chave not in dados:
        return
    d = dados[chave]
    bloco = ET.SubElement(root, "DifferentialPressureTransmitter", range=range_)
    sub(bloco, "Tag",              d.get("tag",         "NI"))
    sub(bloco, "U",                _num(d.get("u",       "")))
    sub(bloco, "CoverageFactor",   _num(d.get("fator_k", "")))
    sub(bloco, "MaxError",         _num(d.get("erro",    "")))
    sub(bloco, "CertificateNumber", d.get("certificado", "NI"))
    sub(bloco, "MaxFlowRate",      d.get("vazao_max",      "NI"), unit="m³/h")
    sub(bloco, "MinFlowRate",      d.get("vazao_min",      "NI"), unit="m³/h")
    sub(bloco, "MaxPressure",      d.get("pressao_max",    "NI"), unit="kPa")
    sub(bloco, "MinPressure",      d.get("pressao_min",    "NI"), unit="kPa")
    sub(bloco, "MaxUncertainty",   d.get("incerteza_max",  "NI"), unit="%")
    sub(bloco, "MinUncertainty",   d.get("incerteza_min",  "NI"), unit="%")


def criar_pressure_transmitter(root, dados):
    criar_bloco_padrao(root, "PressureTransmitter", dados.get("pressao_estatica", {}))


def criar_temperature_transmitter(root, dados):
    criar_bloco_padrao(root, "TemperatureTransmitter", dados.get("termometro", {}))


def criar_temperature_sensor(root, dados):
    criar_bloco_padrao(root, "TemperatureSensor", dados.get("termoresistencia", {}))


def criar_operation_flow_rate(root, dados):
    dp_high = dados.get("dp_high", {})
    dp_low  = dados.get("dp_low",  {})
    max_flow    = dp_high.get("vazao_max",   "NI")
    min_flow    = dp_low.get("vazao_min")    or dp_high.get("vazao_min",   "NI")
    max_pressao = dp_high.get("pressao_max", "NI")
    min_pressao = dp_low.get("pressao_min")  or dp_high.get("pressao_min", "NI")
    max_incerteza = dp_high.get("incerteza_max") or dp_low.get("incerteza_max", "NI")
    min_incerteza = dp_low.get("incerteza_min")  or dp_high.get("incerteza_min", "NI")
    bloco = ET.SubElement(root, "OperationFlowRate")
    sub(bloco, "MaxFlowRate", max_flow,    unit="m³/h")
    sub(bloco, "MinFlowRate", min_flow,    unit="m³/h")
    sub(bloco, "MaxPressure", max_pressao, unit="kPa")
    sub(bloco, "MinPressure", min_pressao, unit="kPa")
    sub(bloco, "MaxUncertainty", max_incerteza, unit="%")
    sub(bloco, "MinUncertainty", min_incerteza, unit="%")


CLIENTES = {
    "origem": "ORIGEM ENERGIA ALAGOAS S.A.",
}


def gerar_xml_uc(numero_ci: str, dados: dict, caminho_saida: str) -> str:
    cliente_raw = dados.get("cliente", "")
    customer = CLIENTES.get(cliente_raw.lower(), cliente_raw) if cliente_raw else "NI"
    root = ET.Element("UncertaintyReport", company="ODS ENERGY SOLUTIONS", customer=customer)

    sub(root, "CINumber",    numero_ci)
    sub(root, "location",    dados.get("ativo", "NI"))
    sub(root, "date",        dados.get("data", "NI"))
    sub(root, "Tag",         dados.get("tag",          "NI"))
    sub(root, "SystemName",  dados.get("nome_sistema", "NI"))

    criar_gas_meter_run(root, dados)
    criar_orifice_plate(root, dados)
    criar_pd_transmitter(root, dados, "high", "dp_high")
    criar_pd_transmitter(root, dados, "low",  "dp_low")
    criar_pressure_transmitter(root, dados)
    criar_temperature_transmitter(root, dados)
    criar_temperature_sensor(root, dados)
    criar_operation_flow_rate(root, dados)

    return salvar_xml_bonito(root, caminho_saida)
