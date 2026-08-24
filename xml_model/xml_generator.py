import xml.etree.ElementTree as ET
import re

from xml_model.xml_common import salvar_xml_bonito


def determinar_tipo_xml(pontos: list, dados_pdf: dict) -> str:
    """
    Determina o tipo do instrumento para o XML.
    Regra especial:
      - FPSO Bravo + TAG iniciando com FIT → DPT
    Caso contrário, usa o tipo vindo dos pontos.
    """
    tipo_padrao = pontos[0]["tipo"].upper()
    local = (dados_pdf.get("local") or "").upper()
    tag = (dados_pdf.get("tag") or "").upper()

    if local == "FPSO BRAVO" and tag.startswith("FIT"):
        return "DPT"

    return tipo_padrao


def tag_te(tag: str | None) -> bool:
    if not tag:
        return False

    partes = tag.upper().split("-")
    return "TE" in partes

def normalizar_certificado(cert: str | None) -> str:
    if not cert:
        return ""
    return cert.replace(" ", "").replace("--", "-")


SIGLAS = {"FPSO"} 

def formatar_instalacao(instalacao: str | None) -> str:

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
    if valor is None:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def normalizar_tag_mvs(tag: str | None, instalacao: str | None) -> str:
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
    if not pontos:
        raise ValueError("Pontos de calibração não informados")

    
    tipo = determinar_tipo_xml(pontos, dados_pdf)

    root = ET.Element("Calibracion")

    def add(tag, value=""):
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