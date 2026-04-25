import sys
from lxml import etree
from pathlib import Path
from datetime import datetime


def _base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

XSD_PATH = _base_path() / "xml_model" / "PetrobrasSchemaV3.0.0 (1) (1).xsd"


def validar_xml(caminho_xml: Path) -> list:
    try:
        with open(XSD_PATH, "rb") as f:
            schema = etree.XMLSchema(etree.parse(f))
        with open(caminho_xml, "rb") as f:
            doc = etree.parse(f)
        schema.validate(doc)
        return [str(e) for e in schema.error_log]
    except Exception as e:
        return [f"Erro interno na validação: {e}"]


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
