# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xsd_validator
# Created       : 25-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Validates a generated XML against the Petrobras XSD schema and writes an error log when validation fails.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import sys
from lxml import etree
from pathlib import Path
from datetime import datetime


def _base_path() -> Path:
    """Returns the project's base directory, accounting for frozen mode (PyInstaller).

    Returns:
        Path: temporary extraction folder (`sys._MEIPASS`) when running as a
        frozen executable, or the project root (two levels above this file)
        in normal execution.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

XSD_PATH = _base_path() / "xml_model" / "PetrobrasSchemaV3.0.0 (1) (1).xsd"

# resolve_entities=False prevents expansion of external entities/DTD (XXE) —
# defense in depth even though the XML validated here is generated internally.
_PARSER_SEGURO = etree.XMLParser(resolve_entities=False, no_network=True)


def validar_xml(caminho_xml: Path) -> list:
    """Validates an XML against the Petrobras schema.

    Args:
        caminho_xml: path of the XML file to validate.

    Returns:
        list[str]: list of error messages (empty if the XML is valid).

    Notes:
        Environment failures (missing XSD, no read permission) propagate as
        an exception instead of becoming an item in the error list — only a
        malformed XML or one that violates the schema generates items in
        this list, so as not to confuse "broken environment" with
        "generated XML is invalid".
    """
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
    """Writes a .log file (same name as `caminho_xml`) with the validation error list.

    Args:
        caminho_xml: path of the validated XML; the log is written next to
            it, replacing the extension with .log.
        erros: list of error messages (see `validar_xml`).

    Returns:
        Path | None: path of the written log file, or None if `erros` is
        empty (no log is written in that case).
    """
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
