import re
import pdfplumber


# =========================================================
# UTILITÁRIOS
# =========================================================

def _to_float(v):
    if v is None:
        return None
    v = str(v).replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", v)
    return float(m.group()) if m else None


def _valor_pos_barra(v):
    if v is None:
        return None
    v = str(v)
    if "/" in v:
        v = v.split("/")[-1]
    return _to_float(v)


# =========================================================
# CURVA DE CALIBRAÇÃO
# =========================================================

def extrair_curva_calibracao(texto):
    """
    Extrai curva do tipo:
        y = a + b.x
    Onde:
        y = mA
        x = kPa
    """

    texto = texto.upper().replace(",", ".")

    padrao = r"Y\s*=\s*([\-0-9.]+)\s*\+\s*([0-9.]+)\s*[\.\*X×]\s*X"
    m = re.search(padrao, texto)

    if not m:
        return None

    return {
        "a": float(m.group(1)),
        "b": float(m.group(2))
    }


def aplicar_curva_kpa(valor_ma, curva):
    """
    Equação REAL do certificado:
        mA = a + b * kPa
        => kPa = (mA - a) / b
    Resultado arredondado para 3 casas decimais.
    """
    if valor_ma is None or not curva:
        return None

    a = curva.get("a")
    b = curva.get("b")

    if a is None or b in (None, 0):
        return None

    kpa = (valor_ma - a) / b
    return round(kpa, 3)

# =========================================================
# FUNÇÃO PRINCIPAL
# =========================================================

def extrair_pontos_calibracao_pdf(caminho_pdf):
    tabelas = []
    texto = ""

    # -------------------------------
    # LEITURA DO PDF
    # -------------------------------
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto += (pagina.extract_text() or "") + "\n"
            for tabela in pagina.extract_tables() or []:
                if tabela and len(tabela) > 2:
                    tabelas.append(tabela)

    if not tabelas:
        return []

    texto_upper = texto.upper()
    pontos = []

    # -------------------------------
    # CURVA DE CALIBRAÇÃO
    # -------------------------------
    curva_calibracao = extrair_curva_calibracao(texto)

    # -------------------------------
    # CLASSIFICAÇÃO
    # -------------------------------
    is_pt = "PRESSURE" in texto_upper or "PRESSÃO" in texto_upper or "-PT" in texto_upper
    is_dpt = (
        "DIFFERENTIAL" in texto_upper or
        "DIFERENCIAL" in texto_upper or
        "-DPT" in texto_upper or
        "PDIT" in texto_upper
    )

    # =========================================================
    # PT / DPT — TRANSMISSOR (SEMPRE mA → kPa)
    # =========================================================
    if (is_pt or is_dpt) and len(tabelas) >= 2:
        tabela = tabelas[1]  # sempre a segunda tabela
        tipo = "DPT" if is_dpt else "PT"

        for linha in tabela[1:]:
            if len(linha) < 2:
                continue

            referencia = _to_float(linha[0])
            if referencia is None:
                continue

            # 🔒 REGRA DEFINITIVA:
            # O VALOR DA TABELA É mA → SEMPRE APLICAR CURVA
            media_ma = _to_float(linha[1])
            media = aplicar_curva_kpa(media_ma, curva_calibracao)

            # Tendência
            tendencia = (
                _valor_pos_barra(linha[3])
                if len(linha) > 3 and "/" in str(linha[3])
                else _to_float(linha[3]) if len(linha) > 3 else None
            )

            # Incerteza
            incerteza = (
                _valor_pos_barra(linha[4])
                if len(linha) > 4 and "/" in str(linha[4])
                else _to_float(linha[4]) if len(linha) > 4 else None
            )

            k = _to_float(linha[5]) if len(linha) > 5 else None

            pontos.append({
                "tipo": tipo,
                "referencia": referencia,
                "media": media,        # ✅ kPa FINAL
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    return []