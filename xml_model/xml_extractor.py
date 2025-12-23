"""
import pdfplumber
import re


def _to_float(v):
    if v is None:
        return None
    v = str(v).strip()
    if v in ("-", "", "∞"):
        return None
    try:
        return float(v.replace(",", "."))
    except Exception:
        return None


def _extrair_valor_pos_barra(valor):
    
    if not valor:
        return None
    if "/" in valor:
        valor = valor.split("/")[-1]
    return _to_float(valor)


def extrair_pontos_calibracao_pdf(caminho_pdf):
    tabelas = []
    texto = ""

    with pdfplumber.open(caminho_pdf) as pdf:
        for p in pdf.pages:
            texto += (p.extract_text() or "") + "\n"
            for t in p.extract_tables() or []:
                if t and len(t) > 2:
                    tabelas.append(t)

    if not tabelas:
        return []

    texto_upper = texto.upper()

    # ===============================
    # IDENTIFICA TIPO
    # ===============================
    is_pressao = "KPA" in texto_upper and "MA DC" in texto_upper
    is_temperatura = "°C" in texto_upper and not is_pressao

    pontos = []

    # ===============================
    # PRESSÃO → SEMPRE 2ª TABELA
    # ===============================
    if is_pressao and len(tabelas) >= 2:
        tabela = tabelas[1]

        for linha in tabela[1:]:
            if len(linha) < 6:
                continue

            referencia = _to_float(linha[0])       # Reference SI (kPa)
            media = _to_float(linha[2])             # Average Standard (kPa)
            tendencia = _extrair_valor_pos_barra(linha[3])
            incerteza = _extrair_valor_pos_barra(linha[4])
            k = _to_float(linha[5])

            if referencia is None:
                continue

            pontos.append({
                "referencia": referencia,
                "media": media,
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    # ===============================
    # TEMPERATURA → TABELA ÚNICA
    # ===============================
    if is_temperatura:
        tabela = tabelas[0]

        for linha in tabela[1:]:
            if len(linha) < 5:
                continue

            referencia = _to_float(linha[0])   # Reference Value (°C)
            media = _to_float(linha[1])        # Reading Medium (°C)
            tendencia = _to_float(linha[2])    # Deviation (°C)
            incerteza = _to_float(linha[3])    # Uncertainty (°C)
            k = _to_float(linha[4])

            if referencia is None:
                continue

            pontos.append({
                "referencia": referencia,
                "media": media,
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    return []
"""

