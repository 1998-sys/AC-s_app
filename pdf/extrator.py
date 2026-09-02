# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.extrator
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Extracts raw text from calibration certificate PDFs using pdfplumber.
#                 Extrai o texto bruto de PDFs de certificados de calibração usando pdfplumber.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import traceback
import pdfplumber

def extrair_texto(caminho_pdf: str) -> str:
    """Extracts and concatenates the text from all pages of a PDF via pdfplumber.

    Args:
        caminho_pdf: Path to the PDF file to be read.

    Returns:
        str: Extracted text (with "\\xa0" normalized to a regular space), or
        an empty string if the reading fails (the error is logged, not propagated).
    """
    texto_final = ""

    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            for page in pdf.pages:
                texto = page.extract_text()
                if texto:  
                    texto_final += texto + "\n"
                    

        # Normalização 
        texto_final = texto_final.replace("\xa0", " ").strip()
        return texto_final

    except Exception:
        print(f"Erro ao ler PDF '{caminho_pdf}':")
        traceback.print_exc()
        return ""

