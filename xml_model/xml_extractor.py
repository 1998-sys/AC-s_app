import pdfplumber


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
    """
    Retorna sempre o valor após '/' convertido para float.
    Usado quando tendência/incerteza vêm no formato mA/kPa ou mA DC/kPa.
    """
    if v is None:
        return None

    v = str(v)

    if "/" in v:
        v = v.split("/")[-1]

    return _to_float(v)


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
    # CASO TE
    # =========================================================
    if is_te and not is_tt:
        tabela = tabelas[0]

        for linha in tabela[1:]:
            if len(linha) < 7:
                continue

            referencia = _to_float(linha[2])
            media = _to_float(linha[4])
            tendencia = _to_float(linha[5])
            incerteza = _to_float(linha[6])
            k = _to_float(linha[7]) if len(linha) > 7 else None

            if referencia is None:
                continue

            pontos.append({
                "tipo": "TE",
                "referencia": referencia,
                "media": media,
                "tendencia": tendencia,
                "incerteza": incerteza,
                "k": k
            })

        return pontos

    # =========================================================
    # CASO TT
    # =========================================================
    if is_tt:
        tabela = tabelas[0]

        for linha in tabela[1:]:

            # TT – Transmissor (possui mA)
            if len(linha) >= 7 and _to_float(linha[2]) is not None:
                referencia = _to_float(linha[0])
                media = _to_float(linha[1])
                tendencia = _to_float(linha[3])
                incerteza = _to_float(linha[4])
                k = _to_float(linha[5])

                if referencia is not None and media is not None:
                    pontos.append({
                        "tipo": "TT",
                        "referencia": referencia,
                        "media": media,
                        "tendencia": tendencia,
                        "incerteza": incerteza,
                        "k": k
                    })
                continue

            # TT – Termômetro digital
            if len(linha) >= 5:
                referencia = _to_float(linha[0])
                media = _to_float(linha[1])
                tendencia = _to_float(linha[2])
                incerteza = _to_float(linha[3])
                k = _to_float(linha[4])

                if referencia is not None and media is not None:
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
    # CASO PT e DPT (MESMA LÓGICA)
    # =========================================================
    if (is_pt or is_dpt) and len(tabelas) >= 2:
        tabela = tabelas[1]  # sempre segunda tabela

        tipo = "DPT" if is_dpt else "PT"

        for linha in tabela[1:]:
            if len(linha) < 4:
                continue

            referencia = _to_float(linha[0])
            if referencia is None:
                continue

            media_kpa = _to_float(linha[2]) if len(linha) > 2 else None
            media_ma = _to_float(linha[1]) if len(linha) > 1 else None

            # Transmissor (mA/kPa ou apenas mA)
            if "/" in str(linha[3]):
                tendencia = _valor_pos_barra(linha[3])
                incerteza = (
                    _valor_pos_barra(linha[4])
                    if len(linha) > 4 and "/" in str(linha[4])
                    else None
                )
                media = media_kpa if media_kpa is not None else media_ma
                k = _to_float(linha[5]) if len(linha) > 5 else None

            # Manômetro digital (tudo em kPa)
            else:
                media = media_kpa
                tendencia = _to_float(linha[3]) if len(linha) > 3 else None
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