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
    """Remove a cópia de um certificado recebido por arrastar-e-soltar depois
    que o relatório/XML já foi gerado a partir dele. Não faz nada se
    `caminho` não estiver dentro dessa pasta (ex.: veio do diálogo de
    arquivo, onde o original é do próprio usuário e não deve ser tocado)."""
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
    prefixo = (tag or "").split("-")[0].upper()
    return FOTOS_INSTRUMENTO.get(prefixo)


def extrair_tag_base(tag: str) -> str:
    return "-".join(tag.split("-")[:-1]) if "-" in tag else tag


def to_float_safe(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None
