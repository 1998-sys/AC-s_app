# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_generator
# Created       : 27-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the ODS-format standard calibration XML (Calibracion) for TE/TT/PT/DPT instruments from the extracted PDF data and points.
#                 Gera o XML de calibração padrão ODS (Calibracion) para instrumentos TE/TT/PT/DPT a partir dos dados e pontos extraídos do PDF.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import xml.etree.ElementTree as ET
import re

from xml_model.xml_common import salvar_xml_bonito


def determinar_tipo_xml(pontos: list, dados_pdf: dict) -> str:
    """Determines the instrument type (TE/TT/PT/DPT) to use in the XML.

    Special rule: at the FPSO Bravo installation, a TAG starting with "FIT"
    is treated as DPT regardless of the type detected in the points.
    Outside that case, uses the type already coming from the first
    calibration point.

    Args:
        pontos: list of extracted calibration points (see
            xml_extractor.extrair_pontos_calibracao_pdf); uses only the
            "tipo" field of the first point.
        dados_pdf: certificate data extracted from the PDF, with "local" and "tag".

    Returns:
        str: instrument type ("TE", "TT", "PT" or "DPT").
    """
    tipo_padrao = pontos[0]["tipo"].upper()
    local = (dados_pdf.get("local") or "").upper()
    tag = (dados_pdf.get("tag") or "").upper()

    if local == "FPSO BRAVO" and tag.startswith("FIT"):
        return "DPT"

    return tipo_padrao


def tag_te(tag: str | None) -> bool:
    """Checks whether the TAG identifies a TE (thermoresistance) instrument.

    Args:
        tag: instrument TAG (e.g. "TE-1234-56").

    Returns:
        bool: True if any segment of the TAG (split by "-") is "TE".
    """
    if not tag:
        return False

    partes = tag.upper().split("-")
    return "TE" in partes


_PREFIXOS_TIPO_TE_TT = {"TE", "TT", "TIT"}


def chave_par_te(tag: str | None) -> str | None:
    """Generates the key used to match a TE with its corresponding TT/TIT.

    The key is the TAG without the type prefix (TE, TT or TIT), since both
    share the same base number (e.g. TE-1234-56 and
    TT-1234-56/TIT-1234-56 → "1234-56").

    Args:
        tag: instrument TAG.

    Returns:
        str | None: TAG without the type prefix, or None if `tag` is empty
        or if nothing remains besides the prefix (malformed TAG).
    """
    if not tag:
        return None

    partes = [p for p in tag.upper().split("-") if p not in _PREFIXOS_TIPO_TE_TT]
    return "-".join(partes) or None

def normalizar_certificado(cert: str | None) -> str:
    """Removes spaces and collapses "--" into "-" in the certificate number.

    Args:
        cert: raw certificate number (accepts None/empty).

    Returns:
        str: normalized certificate number, or empty string if `cert` is empty/None.
    """
    if not cert:
        return ""
    return cert.replace(" ", "").replace("--", "-")


SIGLAS = {"FPSO"} 

def formatar_instalacao(instalacao: str | None) -> str:
    """Formats the installation name in title case, preserving known acronyms (e.g. FPSO).

    Replaces hyphens/underscores/dashes with a space before capitalizing
    each word.

    Args:
        instalacao: raw installation name (accepts None/empty).

    Returns:
        str: formatted name, or empty string if `instalacao` is empty/None.
    """

    if not instalacao:
        return ""

    inst = instalacao.strip()

    inst = re.sub(r"[\-_–]+", " ", inst)

    palavras = inst.split()
    resultado = []

    for p in palavras:
        if p.upper() in SIGLAS:
            resultado.append(p.upper())
        else:
            resultado.append(p.capitalize())

    return " ".join(resultado)


def fmt_num(valor: float | None, casas=3) -> str:
    """Formats a number with a fixed number of decimal places and comma as the decimal separator.

    Args:
        valor: number to format; None is treated as 0.0.
        casas: number of decimal places.

    Returns:
        str: number formatted with decimal comma (e.g. "12,340").
    """
    if valor is None:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def normalizar_tag_mvs(tag: str | None, instalacao: str | None) -> str:
    """Normalizes the instrument TAG to the MVS standard, removing the type suffix at FPSO Forte.

    Args:
        tag: raw instrument TAG (accepts None/empty).
        instalacao: installation name; at "FPSO FORTE" the "-TT", "-PT" and
            "-DPT" suffixes are removed from the TAG.

    Returns:
        str: TAG normalized to uppercase, or empty string if `tag` is empty/None.
    """
    if not tag:
        return ""

    tag = tag.strip().upper()

    if not instalacao:
        return tag

    instalacao = instalacao.strip().upper()

    if instalacao == "FPSO FORTE":
        for sufixo in ("-TT", "-PT", "-DPT"):
            if tag.endswith(sufixo):
                return tag[:-len(sufixo)]

    return tag




def gerar_xml_calibracao(
    dados_pdf: dict,
    pontos: list,
    caminho_saida: str,
    nro_certificado_te_anterior: str | None = None
):
    """Generates the ODS standard calibration XML ("Calibracion") from the data and points extracted from the PDF.

    Args:
        dados_pdf: certificate data extracted from the PDF (certificado,
            datas, local, tag, sn_instrumento, faixa etc.).
        pontos: list of calibration points (see
            xml_extractor.extrair_pontos_calibracao_pdf); must not be empty.
        caminho_saida: path of the output XML file.
        nro_certificado_te_anterior: certificate number of the associated
            TE, included as NroCertificadoRTD only when the detected type
            is "TT" and this value is provided.

    Returns:
        str: `caminho_saida`, passed back unchanged after the XML is written.

    Notes:
        Raises ValueError if `pontos` is empty.
    """
    if not pontos:
        raise ValueError("Pontos de calibração não informados")


    tipo = determinar_tipo_xml(pontos, dados_pdf)

    root = ET.Element("Calibracion")

    def add(tag, value=""):
        """Creates a sub-element of `root` with the text of `value` (empty if None)."""
        el = ET.SubElement(root, tag)
        el.text = "" if value is None else str(value)
        return el


    
 
    add("NroCertificado", normalizar_certificado(dados_pdf.get("certificado")))
    add("FechaDeCalibracion", dados_pdf.get("data"))
    add("FechaEmisionCertificado", dados_pdf.get("report_date"))
    add("Instalacao", formatar_instalacao(dados_pdf.get("local")))
    add("Tipo", tipo)
    add("Serial", dados_pdf.get("sn_instrumento"))

    add("FajaInicial", fmt_num(dados_pdf.get("min_range"), 2))
    add("FajaFinal", fmt_num(dados_pdf.get("max_range"), 2))

    add("InLoco", "1")
    add("AsLeft", "0")

   
    if tipo == "TT" and nro_certificado_te_anterior:
        add(
            "NroCertificadoRTD",
            normalizar_certificado(nro_certificado_te_anterior)
        )

    add("CalcularValorNominal", "0")

    
    add(
        "TAG",
        normalizar_tag_mvs(
            dados_pdf.get("tag"),
            dados_pdf.get("local")
        )
    )

   
    for p in pontos:
        grid = ET.SubElement(root, "GrillaAsFound")

        ET.SubElement(grid, "ValorNominal").text = fmt_num(p.get("referencia"))
        ET.SubElement(grid, "MediaInstrumento").text = fmt_num(p.get("media"))
        ET.SubElement(grid, "Tendencia").text = fmt_num(p.get("tendencia"))
        ET.SubElement(grid, "Incerteza").text = fmt_num(p.get("incerteza"))
        ET.SubElement(grid, "K").text = fmt_num(p.get("k"), 2)

    
    salvar_xml_bonito(root, caminho_saida, standalone=True)

    return caminho_saida