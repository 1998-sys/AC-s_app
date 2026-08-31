# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xsd_validator
# Created       : 25-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Validates a generated XML against the Petrobras XSD schema and writes an error log when validation fails.
#                 Valida um XML gerado contra o schema XSD da Petrobras e grava um log de erros quando a validação falha.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import sys
from lxml import etree
from pathlib import Path
from datetime import datetime


def _base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

XSD_PATH = _base_path() / "xml_model" / "PetrobrasSchemaV3.0.0 (1) (1).xsd"

# resolve_entities=False evita expansão de entidades externas/DTD (XXE) —
# defesa em profundidade mesmo o XML validado aqui sendo gerado internamente.
_PARSER_SEGURO = etree.XMLParser(resolve_entities=False, no_network=True)


def validar_xml(caminho_xml: Path) -> list:
    """Valida caminho_xml contra o schema Petrobras e retorna a lista de erros
    (vazia se válido). Só um XML malformado gera itens nessa lista — falhas de
    ambiente (XSD ausente, permissão) propagam como exceção em vez de serem
    confundidas com "XML gerado é inválido"."""
    with open(XSD_PATH, "rb") as f:
        schema = etree.XMLSchema(etree.parse(f))

    try:
        with open(caminho_xml, "rb") as f:
            doc = etree.parse(f, parser=_PARSER_SEGURO)
    except etree.XMLSyntaxError as e:
        return [f"XML malformado: {e}"]

    schema.validate(doc)
    return [str(e) for e in schema.error_log]


def registrar_log(caminho_xml: Path, erros: list):
    if not erros:
        return None
    caminho_log = Path(caminho_xml).with_suffix(".log")
    with open(caminho_log, "w", encoding="utf-8") as f:
        f.write(f"Validação XSD — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Arquivo : {Path(caminho_xml).name}\n")
        f.write(f"Schema  : {XSD_PATH.name}\n")
        f.write("-" * 60 + "\n")
        f.write(f"{len(erros)} erro(s) encontrado(s):\n\n")
        for i, e in enumerate(erros, 1):
            f.write(f"{i}. {e}\n")
    return caminho_log
