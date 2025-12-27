import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path





def normalizar_certificado(cert: str | None) -> str:
    """
    Remove espaços do número do certificado.
    """
    if not cert:
        return ""
    return cert.replace(" ", "").replace("--", "-")


def formatar_instalacao(instalacao: str | None) -> str:
    """
    Formata instalação:
    FPSO FORTE → FPSO Forte
    FPSO BRAVO → FPSO Bravo
    """
    if not instalacao:
        return ""

    partes = instalacao.strip().split()
    if len(partes) >= 2 and partes[0].upper() == "FPSO":
        return f"FPSO {partes[1].capitalize()}"

    return instalacao.title()


def fmt_num(valor: float | None, casas=3) -> str:
    """
    Formata número com vírgula como separador decimal.
    """
    if valor is None:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def normalizar_tag_mvs(tag: str | None, instalacao: str | None) -> str:
    """
    Regra MVS:
    - Somente para FPSO Forte
    - Remove sufixos -TT, -PT, -DPT da TAG
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
    if not pontos:
        raise ValueError("Pontos de calibração não informados")

    # Tipo vem dos pontos
    tipo = pontos[0]["tipo"].upper()

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

   
    if tipo == "TT":
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

    
    xml_str = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "wb") as f:
        f.write(pretty_xml)

    return caminho_saida