import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path


def sub(parent, tag, text="", **attrs):
    el = ET.SubElement(parent, tag, **attrs)
    el.text = str(text)
    return el


def criar_gas_meter_run(root, dados):
    bloco = ET.SubElement(root, "GasMeterRun")
    sub(bloco, "Certificate",       dados.get("trecho", {}).get("tag",         "NI"))
    sub(bloco, "InternalDiameter",  dados.get("trecho", {}).get("diametro",    "NI"))
    sub(bloco, "CertificateNumber", dados.get("trecho", {}).get("certificado", "NI"))


def criar_orifice_plate(root, dados):
    bloco = ET.SubElement(root, "OrificePlate")
    sub(bloco, "Certificate",       dados.get("placa", {}).get("tag",         "NI"))
    sub(bloco, "DiameterAt20C",     dados.get("placa", {}).get("diametro",    "NI"))
    sub(bloco, "CertificateNumber", dados.get("placa", {}).get("certificado", "NI"))


def criar_pd_transmitter(root, dados, range_: str, chave: str):
    if chave not in dados:
        return
    d = dados[chave]
    bloco = ET.SubElement(root, "DifferentialPressureTransmitter", range=range_)
    sub(bloco, "Certificate",       d.get("tag",          "NI"))
    sub(bloco, "CertificateNumber", d.get("certificado",  "NI"))
    sub(bloco, "MaxFlowRate",       d.get("vazao_max",    "NI"), unit="m³/h")
    sub(bloco, "MinFlowRate",       d.get("vazao_min",    "NI"), unit="m³/h")
    sub(bloco, "MaxPressure",       d.get("pressao_max",  "NI"), unit="kPa")
    sub(bloco, "MinPressure",       d.get("pressao_min",  "NI"), unit="kPa")


def criar_pressure_transmitter(root, dados):
    bloco = ET.SubElement(root, "PressureTransmitter")
    sub(bloco, "Certificate",       dados.get("pressao_estatica", {}).get("tag",         "NI"))
    sub(bloco, "CertificateNumber", dados.get("pressao_estatica", {}).get("certificado", "NI"))


def criar_temperature_transmitter(root, dados):
    bloco = ET.SubElement(root, "TemperatureTransmitter")
    sub(bloco, "Certificate",       dados.get("termometro", {}).get("tag",         "NI"))
    sub(bloco, "CertificateNumber", dados.get("termometro", {}).get("certificado", "NI"))


def criar_temperature_sensor(root):
    bloco = ET.SubElement(root, "TemperatureSensor")
    sub(bloco, "Certificate",       "NI")
    sub(bloco, "CertificateNumber", "NI")


def criar_operation_flow_rate(root, dados):
    dp_high = dados.get("dp_high", {})
    dp_low  = dados.get("dp_low",  {})
    max_flow    = dp_high.get("vazao_max",   "NI")
    min_flow    = dp_low.get("vazao_min")    or dp_high.get("vazao_min",   "NI")
    max_pressao = dp_high.get("pressao_max", "NI")
    min_pressao = dp_low.get("pressao_min")  or dp_high.get("pressao_min", "NI")
    bloco = ET.SubElement(root, "OperationFlowRate")
    sub(bloco, "MaxFlowRate", max_flow,    unit="m³/h")
    sub(bloco, "MinFlowRate", min_flow,    unit="m³/h")
    sub(bloco, "MaxPressure", max_pressao, unit="kPa")
    sub(bloco, "MinPressure", min_pressao, unit="kPa")


def gerar_xml_uc(numero_ci: str, dados: dict, caminho_saida: str) -> str:
    root = ET.Element("UncertaintyReport", company="ODS ENERGY SOLUTIONS", customer='ORIGEM ENERGIA ALAGOAS S.A.')

    sub(root, "CINumber",    numero_ci)
    sub(root, "Tag",         "NI")
    sub(root, "SystemName",  "NI")

    criar_gas_meter_run(root, dados)
    criar_orifice_plate(root, dados)
    criar_pd_transmitter(root, dados, "high", "dp_high")
    criar_pd_transmitter(root, dados, "low",  "dp_low")
    criar_pressure_transmitter(root, dados)
    criar_temperature_transmitter(root, dados)
    criar_temperature_sensor(root)
    criar_operation_flow_rate(root, dados)

    xml_bytes = ET.tostring(root, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8")

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "wb") as f:
        f.write(pretty_xml)

    return caminho_saida
