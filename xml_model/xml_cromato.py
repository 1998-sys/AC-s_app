from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

def xml_cromatografia(pdf_path: str, dados: dict, caminho_saida_xml: str | None = None) -> str:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    if caminho_saida_xml is None:
        caminho_saida_xml = pdf_path.with_suffix(".xml")
    caminho_saida_xml = Path(caminho_saida_xml)

    root = Element("CROMATOGRAFIA")

    cab = SubElement(root, "CABECALHO")
    empresa = dados.get("empresa")
    certificado = dados.get("certificado")
    if empresa is not None:
        SubElement(cab, "EMPRESA").text = str(empresa)
    if certificado is not None:
        SubElement(cab, "CERTIFICADO").text = str(certificado)

    comp_wrap = SubElement(root, "COMPOSICAOGASES")
    comp_list = (dados.get("composicao") or {}).get("composicao", []) or []
    for item in comp_list:
        rot = item.get("rotulo")
        nome = item.get("nome")
        mol  = item.get("mol_pct")
        inc  = item.get("incerteza")

        comp_el = SubElement(comp_wrap, "COMPONENTE")
        if rot is not None:
            comp_el.set("rotulo", str(rot))
        if nome is not None:
            SubElement(comp_el, "NOME").text = str(nome)
        if mol is not None:
            SubElement(comp_el, "MOLPCT").text = str(mol)
        if inc is not None:
            SubElement(comp_el, "INCERTEZA").text = str(inc)

    pad_wrap = SubElement(root, "PROPRIEDADESCONDICAOPADRAO")
    props_padrao = (dados.get("propriedades_pad") or {}).get("propriedades_padrao", []) or []
    for p in props_padrao:
        prop_el = SubElement(pad_wrap, "PROPRIEDADE")
        ref = p.get("referencia")
        if ref:
            prop_el.set("referencia", str(ref))
        if p.get("propriedade") is not None:
            SubElement(prop_el, "NOME").text = str(p["propriedade"])
        if p.get("valor") is not None:
            SubElement(prop_el, "VALOR").text = str(p["valor"])
        if p.get("incerteza") is not None:
            SubElement(prop_el, "INCERTEZA").text = str(p["incerteza"])

    amost_wrap = SubElement(root, "PROPRIEDADESCONDICOESAMOSTRAGEM")
    props_amost = (dados.get("propriedades_amost") or {}).get("propriedades_amostragem", []) or []
    for p in props_amost:
        prop_el = SubElement(amost_wrap, "PROPRIEDADE")
        ref = p.get("referencia")
        if ref:
            prop_el.set("referencia", str(ref))
        if p.get("propriedade") is not None:
            SubElement(prop_el, "NOME").text = str(p["propriedade"])
        if p.get("valor") is not None:
            SubElement(prop_el, "VALOR").text = str(p["valor"])
        if p.get("incerteza") is not None:
            SubElement(prop_el, "INCERTEZA").text = str(p["incerteza"])

    xml_str = tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

    caminho_saida_xml.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida_xml, "wb") as f:
        f.write(pretty_xml)

    return str(caminho_saida_xml)