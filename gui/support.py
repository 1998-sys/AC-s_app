"""Constantes e helpers pequenos compartilhados pelos serviços de gui/."""

CHECKLIST_ALL = ["extract", "compare", "validate", "build"]

FOTOS_INSTRUMENTO = {
    "PIT": "instr-pit.jpg",
    "TE": "instr-te.jpg",
    "TT": "instr-tt.jpg",
}


def foto_instrumento(tag):
    prefixo = (tag or "").split("-")[0].upper()
    return FOTOS_INSTRUMENTO.get(prefixo)


def extrair_tag_base(tag: str) -> str:
    return "-".join(tag.split("-")[:-1]) if "-" in tag else tag


def to_float_safe(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None
