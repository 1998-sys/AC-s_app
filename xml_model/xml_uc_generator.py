# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_uc_generator
# Created       : 21-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the uncertainty calculation report XML (UncertaintyReport) with the measurement chain components and their metrological limits.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re
import xml.etree.ElementTree as ET

from xml_model.xml_common import salvar_xml_bonito

_NUM_RE = re.compile(r'^\d[\d.,]*$')
# Characters invalid in XML 1.0 (except tab \x09, newline \x0A and CR \x0D)
_INVALID_XML = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')


def _sanitize(text: str) -> str:
    """Removes characters invalid in XML 1.0 (except tab, newline and CR) from the text.

    Args:
        text: text to sanitize (converted to str before processing).

    Returns:
        str: text without the invalid characters, with surrounding spaces removed.
    """
    return _INVALID_XML.sub(' ', str(text)).strip()


def _num(v: str) -> str:
    """Validates whether the string represents a number (digits, dot and comma).

    Args:
        v: value to validate.

    Returns:
        str: `v` itself if it matches the numeric pattern, or "NI" (not
        informed) otherwise.
    """
    return v if _NUM_RE.match(v.strip()) else "NI"


def sub(parent, tag, text="", **attrs):
    """Creates a sub-element with sanitized text and optional attributes.

    Args:
        parent: parent XML element.
        tag: tag name of the new element.
        text: element text, sanitized via `_sanitize` before assignment.
        **attrs: XML attributes of the element (e.g. unit="kPa").

    Returns:
        Element: the created element.
    """
    el = ET.SubElement(parent, tag, **attrs)
    el.text = _sanitize(text)
    return el


def criar_bloco_padrao(root, tag_bloco, d, com_diametro=False):
    """Creates a Tag/[Diameter]/U/CoverageFactor/MaxError/CertificateNumber block.

    Pattern common to GasMeterRun, OrificePlate, PressureTransmitter,
    TemperatureTransmitter and TemperatureSensor — the only difference
    between these blocks is the XML tag name, the source key in `dados`
    and the presence (or not) of the Diameter field.

    Args:
        root: parent XML element where the block will be inserted.
        tag_bloco: XML tag name of the block (e.g. "GasMeterRun").
        d: dict with the component data ("tag", "diametro", "u",
            "fator_k", "erro", "certificado").
        com_diametro: if True, includes the Diameter tag in the block.

    Returns:
        Element: the created block element.
    """
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
    """Creates the GasMeterRun block from `dados["trecho"]`."""
    criar_bloco_padrao(root, "GasMeterRun", dados.get("trecho", {}), com_diametro=True)


def criar_orifice_plate(root, dados):
    """Creates the OrificePlate block from `dados["placa"]`."""
    criar_bloco_padrao(root, "OrificePlate", dados.get("placa", {}), com_diametro=True)


def criar_pd_transmitter(root, dados, range_: str, chave: str):
    """Creates the DifferentialPressureTransmitter block (high or low range) with the flow/pressure/uncertainty limits.

    Args:
        root: parent XML element where the block will be inserted.
        dados: general UC data dict; uses `dados[chave]` as the source of the fields.
        range_: value of the XML "range" attribute ("high" or "low").
        chave: key in `dados` with the fields of this differential
            pressure transmitter. If absent, no block is created.
    """
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
    """Creates the PressureTransmitter block from `dados["pressao_estatica"]`."""
    criar_bloco_padrao(root, "PressureTransmitter", dados.get("pressao_estatica", {}))


def criar_temperature_transmitter(root, dados):
    """Creates the TemperatureTransmitter block from `dados["termometro"]`."""
    criar_bloco_padrao(root, "TemperatureTransmitter", dados.get("termometro", {}))


def criar_temperature_sensor(root, dados):
    """Creates the TemperatureSensor block from `dados["termoresistencia"]`."""
    criar_bloco_padrao(root, "TemperatureSensor", dados.get("termoresistencia", {}))


def criar_operation_flow_rate(root, dados):
    """Creates the OperationFlowRate block combining limits from the high and low dP ranges.

    For each limit (flow, pressure, uncertainty), preferentially uses the
    value from the corresponding range (maximum from dp_high, minimum from
    dp_low) and falls back to the other range when the preferred value is
    not present.

    Args:
        root: parent XML element where the block will be inserted.
        dados: general UC data dict; uses the "dp_high" and "dp_low" keys.
    """
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
    """Generates the uncertainty calculation report XML (UncertaintyReport) and writes it to disk.

    Args:
        numero_ci: certificate/CI number to place in CINumber.
        dados: report data (cliente, ativo, data, tag, sistema and the
            blocks for each measurement chain component: trecho, placa,
            dp_high/dp_low, pressao_estatica, termometro, termoresistencia).
        caminho_saida: path of the output XML file.

    Returns:
        str: absolute path of the generated XML file.
    """
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
