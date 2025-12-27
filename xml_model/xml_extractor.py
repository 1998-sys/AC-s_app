import pdfplumber
from pdf.parser_certificados import extrair_curva_calibracao, aplicar_curva_kpa


# =========================================================
# UTILITÁRIOS
# =========================================================

def _to_float(v):
    if v is None:
        return None

    v = str(v).strip()

    if v in ("", "-", "∞"):
        return None

    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _valor_pos_barra(v):
    if v is None:
        return None

    v = str(v)

    if "/" in v:
        v = v.split("/")[-1]

    return _to_float(v)


# =========================================================
# FUNÇÃO PRINCIPAL
# =========================================================

def extrair_pontos_calibracao_pdf(caminho_pdf):
    tabelas = []
    texto = ""

    # ===============================
    # LEITURA DO PDF
    # ===============================
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

    # ===============================
    # CLASSIFICAÇÃO
    # ===============================
    is_te = "THERMORESISTANCE" in texto_upper or "TERMORRESISTÊNCIA" in texto_upper

    is_tt = (
        "DIGITAL THERMOMETER" in texto_upper or
        "TEMPERATURE TRANSMITTER" in texto_upper or
        "-TT" in texto_upper or
        "TRANSMISSOR DE TEMPERATURA" in texto_upper
    )

    is_pt = (
        "PRESSURE" in texto_upper or
        "PRESSÃO" in texto_upper or
        "-PT" in texto_upper
    )

    is_dpt = (
        "DIFFERENTIAL" in texto_upper or
        "DIFERENCIAL" in texto_upper or
        "-DPT" in texto_upper or
        "PDIT" in texto_upper
    )

    # =========================================================
    # TE – Termorresistência
    # =========================================================
    if is_te and not is_tt:
        tabela = tabelas[0]

        for linha in tabela[1:]:
            if len(linha) < 7:
                continue

            referencia = _to_float(linha[2])
            if referencia is None:
                continue

            pontos.append({
                "tipo": "TE",
                "referencia": referencia,
                "media": _to_float(linha[4]),
                "tendencia": _to_float(linha[5]),
                "incerteza": _to_float(linha[6]),
                "k": _to_float(linha[7]) if len(linha) > 7 else None
            })

        return pontos

    # =========================================================
    # TT – Temperatura (DOIS FORMATOS)
    # =========================================================
    if is_tt:
        tabela = tabelas[0]

        # 🔑 DETECÇÃO PELO CABEÇALHO
        cabecalho = " ".join(
            str(c).upper()
            for c in tabela[0]
            if c
        )

        possui_ma_dc = "MA DC" in cabecalho

        for linha in tabela[1:]:
            if len(linha) < 5:
                continue

            referencia = _to_float(linha[0])
            if referencia is None:
                continue

            # ---------------------------------
            # TT TIPO 2 → POSSUI mA DC (IGNORAR)
            # ---------------------------------
            if possui_ma_dc:
                media = _to_float(linha[1])        # °C
                tendencia = _to_float(linha[3])    # °C
                incerteza = _to_float(linha[4])    # °C
                k = _to_float(linha[5]) if len(linha) > 5 else None

            # ---------------------------------
            # TT TIPO 1 → TUDO EM °C
            # ---------------------------------
            else:
                media = _to_float(linha[1])
                tendencia = _to_float(linha[2])
                incerteza = _to_float(linha[3])
                k = _to_float(linha[4]) if len(linha) > 4 else None

            pontos.append({
                "tipo": "TT",
                "referencia": referencia,
                "media": media,
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    # =========================================================
    # PT / DPT – PRESSÃO
    # =========================================================
    if (is_pt or is_dpt) and len(tabelas) >= 2:
        tabela = tabelas[1]
        tipo = "DPT" if is_dpt else "PT"

        cabecalho = " ".join(
            str(c).upper()
            for c in tabela[0]
            if c
        )

        media_em_ma = "MA DC" in cabecalho
        curva_calibracao = extrair_curva_calibracao(texto)

        for linha in tabela[1:]:
            if len(linha) < 4:
                continue

            referencia = _to_float(linha[0])
            if referencia is None:
                continue

            media_ma = _to_float(linha[1])
            media_kpa = _to_float(linha[2])

            if media_em_ma and curva_calibracao:
                media = round(aplicar_curva_kpa(media_ma, curva_calibracao), 3)
            else:
                media = media_kpa

            if "/" in str(linha[3]):
                tendencia = _valor_pos_barra(linha[3])
                incerteza = _valor_pos_barra(linha[4]) if len(linha) > 4 else None
            else:
                tendencia = _to_float(linha[3])
                incerteza = _to_float(linha[4]) if len(linha) > 4 else None

            k = _to_float(linha[5]) if len(linha) > 5 else None

            pontos.append({
                "tipo": tipo,
                "referencia": referencia,
                "media": media,
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    return []