import pdfplumber

def extrair_texto(caminho_pdf: str) -> str:
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

    except Exception as e:
        print(f"Erro ao ler PDF '{caminho_pdf}': {e}")
        return ""

