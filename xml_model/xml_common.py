# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_common
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Shared helper that pretty-prints an XML Element and writes it to disk, used by all certificate XML generators.
#                 Helper compartilhado que formata um Element XML e grava em disco, usado por todos os geradores de XML de certificado.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path


def salvar_xml_bonito(root, caminho_saida, standalone=False):
    """Serializes an Element into formatted (indented) XML and writes it to disk,
    creating the output path's folders if needed.

    Used by all certificate XML generators (chromatography, UC, PO, TR, petro)
    to avoid reimplementing tostring → minidom → toprettyxml → write in each one.

    Args:
        root: root element (xml.etree.ElementTree.Element) to be serialized.
        caminho_saida (str | Path): path of the output .xml file.
        standalone (bool): if True, adds `standalone="yes"` to the XML declaration.

    Returns:
        str: absolute path of the generated file (same value received in caminho_saida).
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
