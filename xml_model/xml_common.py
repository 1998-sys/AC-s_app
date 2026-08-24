import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path


def salvar_xml_bonito(root, caminho_saida, standalone=False):
    """Serializa um Element em XML formatado (indentado) e grava em disco,
    criando as pastas do caminho de saída se necessário.

    Usado por todos os geradores de certificado XML (cromatografia, UC, PO,
    TR, petro) para evitar reimplementar tostring → minidom → toprettyxml →
    write em cada um deles.

    Args:
        root: elemento raiz (xml.etree.ElementTree.Element) a ser serializado.
        caminho_saida (str | Path): caminho do arquivo .xml de saída.
        standalone (bool): se True, adiciona `standalone="yes"` à declaração XML.

    Returns:
        str: caminho absoluto do arquivo gerado (mesmo valor recebido em caminho_saida).
    """
    xml_str = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

    if standalone:
        pretty_xml = pretty_xml.replace(
            b'<?xml version="1.0" encoding="utf-8"?>',
            b'<?xml version="1.0" encoding="utf-8" standalone="yes"?>'
        )

    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "wb") as f:
        f.write(pretty_xml)

    return str(caminho_saida)
