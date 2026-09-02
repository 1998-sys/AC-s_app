# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gui.support
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Provides small shared constants and helpers used across the gui/ services.
#                 Fornece constantes e helpers pequenos compartilhados entre os serviços de gui/.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

"""Constantes e helpers pequenos compartilhados pelos serviços de gui/."""

from pathlib import Path

from data.utils_fs import pasta_documentos

CHECKLIST_ALL = ["extract", "compare", "validate", "build"]

# Pasta onde certificados recebidos por arrastar-e-soltar são salvos
# temporariamente pra viabilizar a geração (ver
# gui.pdf_service.PdfProcessingService.receber_arquivos_soltos). O usuário
# pediu pra não manter o certificado de origem lá — só os PDFs/XMLs gerados.
PASTA_CERTIFICADOS_SOLTOS = "AC's Generator/Certificados Recebidos"


def limpar_certificado_solto(caminho):
    """Removes the copy of a certificate received via drag-and-drop after the report/XML has already been generated from it.

    Args:
        caminho: Path of the certificate to remove.

    Notes:
        Does nothing if `caminho` is not inside `PASTA_CERTIFICADOS_SOLTOS`
        (e.g. it came from the file dialog, where the original belongs to
        the user and must not be touched).
    """
    try:
        pasta = pasta_documentos(PASTA_CERTIFICADOS_SOLTOS)
        if Path(caminho).resolve().parent == pasta.resolve():
            Path(caminho).unlink(missing_ok=True)
    except OSError:
        pass

FOTOS_INSTRUMENTO = {
    "PIT": "instr-pit.jpg",
    "TE": "instr-te.jpg",
    "TT": "instr-tt.jpg",
}


def foto_instrumento(tag):
    """Returns the photo filename associated with the TAG's type prefix (e.g. "PIT-001" -> instr-pit.jpg), or None if no photo is registered."""
    prefixo = (tag or "").split("-")[0].upper()
    return FOTOS_INSTRUMENTO.get(prefixo)


def extrair_tag_base(tag: str) -> str:
    """Removes the last "-"-separated segment of the TAG, used to match instruments from the same set (e.g. "FT-001-A" -> "FT-001")."""
    return "-".join(tag.split("-")[:-1]) if "-" in tag else tag


def to_float_safe(value):
    """Converts `value` to float accepting a comma as the decimal separator, returning None instead of raising if the conversion fails."""
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None
