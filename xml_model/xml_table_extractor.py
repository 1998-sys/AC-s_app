import pdfplumber
import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pdf.parser_certificados import extrair_categoria_intrumento



def normalizar_categoria(txt: str) -> str:
    if not txt:
        return ""

    substituicoes = {
        "‐": "-",  
        "–": "-",  
        "—": "-",  
        "-": "-",  
    }


def to_float(valor):
    if valor is None:
        return None

    try:
        v = str(valor).strip()

        v = (
            v.replace("−", "-")
             .replace("–", "-")
             .replace("‐", "-")
        )

        return float(v.replace(",", "."))
    except ValueError:
        return None


def to_valor_eng(valor):
    """
    Usado para:
    - incerteza
    - k
    - tendência
    - veff
    """
    if valor is None:
        return None

    v = str(valor).strip()

    v = (
        v.replace("−", "-")
         .replace("–", "-")
         .replace("‐", "-")
    )

    if v in ("∞", "INFINITO", "infinito"):
        return "INFINITO"

    if v in ("-", "--", "- / -", "NI"):
        return "NI"

    try:
        return float(v.replace(",", "."))
    except ValueError:
        return "NI"


def pegar_primeiro_valor(valor):
    """
    Regra metrológica:
    Para transmissores elétricos, usa sempre o valor antes da barra (/)
    """
    if valor is None:
        return None

    return str(valor).split("/")[0].strip()



def extrair_texto_pagina(pdf, indice):
    try:
        return pdf.pages[indice].extract_text() or ""
    except IndexError:
        return ""


def extrair_tabelas_pagina_2(pdf):
    page = pdf.pages[1]

    tabelas = page.extract_tables({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines"
    })

    if not tabelas:
        tabelas = page.extract_tables({
            "vertical_strategy": "text",
            "horizontal_strategy": "text"
        })

    print(tabelas)
    return tabelas or []


def classificar_tabelas(tabelas):
    classificacao = {
        "AS_FOUND": None,
        "AS_LEFT": None,
        "RESULTADOS": None
    }

    qtd_tabelas = len(tabelas) if tabelas else 0
    
    if not tabelas:
        return classificacao

    classificacao["RESULTADOS"] = tabelas[-1]
    leitura = tabelas[:-1]

    if len(leitura) == 1:
        classificacao["AS_FOUND"] = leitura[0]
    elif len(leitura) >= 2:
        classificacao["AS_FOUND"] = leitura[0]
        classificacao["AS_LEFT"] = leitura[1]

    return classificacao



def ajustar_transmissor_pressao_eletrico(categoria, tabelas):
    resultado = {"categoria": categoria}
    idx = 1

    # ---------- AS FOUND / AS LEFT ----------
    for tipo in ("AS_FOUND", "AS_LEFT"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 2:
            continue

        registros = []
        for linha in tabela[2:]:
            if len(linha) < 6:
                continue

            registros.append({
                "SI_REF": to_float(linha[0]),
                "kPa_ref": to_float(linha[1]),
                "p_cic_cresc": to_float(linha[2]),
                "p_cic_decres": to_float(linha[3]),
                "s_cic_cres": to_float(linha[4]),
                "s_cic_decrs": to_float(linha[5]),
                "media": to_float(linha[6]) if len(linha) > 6 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    # ---------- RESULTADOS (REGRA mA) ----------
    tabela_res = tabelas.get("RESULTADOS")
    if tabela_res:
        registros = []
        for linha in tabela_res[1:]:
            if len(linha) < 7:
                continue

            registros.append({
                "referencia_si_kpa": to_float(linha[0]),
                "referencia_ma": to_float(linha[1]),
                "media_leituras_ma": to_float(linha[2]),
                "tendencia_ma": to_valor_eng(pegar_primeiro_valor(linha[3])),
                "incerteza_ma": to_valor_eng(pegar_primeiro_valor(linha[4])),
                "k": to_valor_eng(linha[5]),
                "veff": to_valor_eng(linha[6])
            })

        resultado[f"tabela{idx}"] = "RESULTADOS"
        resultado[f"results{idx}"] = registros

    return resultado


def ajustar_transmissor_temperatura_eletrico(categoria, tabelas):
    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT", "RESULTADOS"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 1:
            continue

        registros = []
        for linha in tabela[1:]:
            if len(linha) < 6:
                continue

            registros.append({
                "valor_referencia_c": to_float(linha[0]),
                "media_leituras_c": to_float(linha[1]),
                "media_mA": to_float(linha[2]),
                "tendencia_c": to_float(linha[3]),
                "incerteza_c": to_valor_eng(linha[4]),
                "k": to_valor_eng(linha[5]),
                "veff": to_valor_eng(linha[6]) if len(linha) > 6 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    return resultado


def ajustar_transmissor_temperatura(categoria, tabelas):
    """
    Formato simplificado de Transmissor de Temperatura (6 colunas, sem coluna mA):
    Reference | Average Reading | Error | Expanded Uncertainty | k | Veff
    """
    resultado = {"categoria": categoria}

    tabela = tabelas.get("RESULTADOS")
    if not tabela or len(tabela) <= 1:
        return resultado

    registros = []
    for linha in tabela[1:]:
        if len(linha) < 5:
            continue

        registros.append({
            "valor_referencia_c": to_float(linha[0]),
            "media_leituras_c":   to_float(linha[1]),
            "tendencia_c":        to_float(linha[2]),
            "incerteza_c":        to_valor_eng(linha[3]),
            "k":                  to_valor_eng(linha[4]),
            "veff":               to_valor_eng(linha[5]) if len(linha) > 5 else None,
        })

    resultado["tabela1"] = "RESULTADOS"
    resultado["results1"] = registros
    return resultado


def ajustar_manometros(categoria, tabelas):
    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 2:
            continue

        registros = []
        for linha in tabela[2:]:
            if len(linha) < 6:
                continue

            registros.append({
                "SI_kpa": to_float(linha[0]),
                "kPa_ref": to_float(linha[1]),
                "p_cic_cresc": to_float(linha[2]),
                "p_cic_decres": to_float(linha[3]),
                "s_cic_cres": to_float(linha[4]),
                "s_cic_decrs": to_float(linha[5]),
                "media": to_float(linha[6]) if len(linha) > 6 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    tabela_res = tabelas.get("RESULTADOS")
    if tabela_res:
        registros = []
        for linha in tabela_res[1:]:
            if len(linha) < 7:
                continue

            registros.append({
                "referencia_si_kpa": to_float(linha[0]),
                "p_indicada_kpa": to_float(linha[1]),
                "media_leituras_kpa": to_float(linha[2]),
                "tendencia_kpa": to_valor_eng(linha[3].split("/")[0]) if linha[3] else None,
                "incerteza_kpa": to_valor_eng(linha[4]),
                "k": to_valor_eng(linha[5]),
                "veff": to_valor_eng(linha[6])
            })

        resultado[f"tabela{idx}"] = "RESULTADOS"
        resultado[f"results{idx}"] = registros

    return resultado


def ajustar_pt100(categoria, tabelas):
    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT", 'RESULTADOS'):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 1:
            continue

        registros = []
        for linha in tabela[1:]:
            registros.append({
                "profundidade": linha[0] if len(linha) > 0 else None,
                "padrao_utilizado": linha[1] if len(linha) > 1 else None,
                "valor_referencia": to_float(linha[2]) if len(linha) > 2 else None,
                "media_ohm": to_float(linha[3]) if len(linha) > 3 else None,
                "media_celsius": to_float(linha[4]) if len(linha) > 4 else None,
                "tendencia": to_valor_eng(linha[5]) if len(linha) > 5 else None,
                "incerteza": to_valor_eng(linha[6]) if len(linha) > 6 else None,
                "k": to_valor_eng(linha[7]) if len(linha) > 7 else None,
                "veff": to_valor_eng(linha[8]) if len(linha) > 8 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    return resultado


def ajustar_termometro_digital_analogico(categoria, tabelas):
    """
    Ajuste para certificados de:
    - Termômetro Digital
    - Termômetro Analógico

    Suporta:
    - AS FOUND
    - AS LEFT (se existir)

    Estrutura esperada das tabelas:
    Reference | Reading Medium | Deviation | Uncertainty | k | Veff
    """

    resultado = {"categoria": categoria}
    idx = 1

    for tipo in ("AS_FOUND", "AS_LEFT", "RESULTADOS"):
        tabela = tabelas.get(tipo)
        if not tabela or len(tabela) <= 1:
            continue

        registros = []

        for linha in tabela[1:]:
            if len(linha) < 6:
                continue

            registros.append({
                "valor_referencia_c": to_float(linha[0]),
                "media_leituras_c": to_float(linha[1]),
                "tendencia_c": to_valor_eng(linha[2]),
                "incerteza_c": to_valor_eng(linha[3]),
                "k": to_valor_eng(linha[4]),
                "veff": to_valor_eng(linha[5])
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

    return resultado


def processar_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:

        categoria = extrair_categoria_intrumento(
            extrair_texto_pagina(pdf, 0)
        ).upper()
        
        print(f"Categoria extraída: {categoria}")

        tabelas = extrair_tabelas_pagina_2(pdf)
        classificacao = classificar_tabelas(tabelas)
        
        

        if "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA" in categoria or 'TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA' in categoria:
            return ajustar_transmissor_pressao_eletrico(categoria, classificacao)

        elif "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA" in categoria:
            return ajustar_transmissor_temperatura_eletrico(categoria, classificacao)

        elif "TRANSMISSOR DE TEMPERATURA" in categoria:
            return ajustar_transmissor_temperatura(categoria, classificacao)

        elif any(c in categoria for c in [
            "MANOMETRO DIGITAL",
            "MANOMETRO ANALÓGICO",
            "MANOMETRO DIGITAL ABSOLUTO",
            "MANOMETRO DIFERENCIAL DIGITAL",
            "MANOMETRO DIFERENCIAL ANALÓGICO"
        ]):
            return ajustar_manometros(categoria, classificacao)

        elif any(c in categoria for c in [
            "TERMORRESISTÊNCIA PT-100 - 2 FIOS",
            'TERMORRESISTÊNCIA PT-100 - 3 FIOS',
            'TERMORRESISTÊNCIA PT-100 - 4 FIOS'
        ]):
            return ajustar_pt100(categoria, classificacao)
        
        elif any(c in categoria for c in [
            "TERMÔMETRO DIGITAL",
            "TERMÔMETRO ANALÓGICO",
        ]):
            return ajustar_termometro_digital_analogico(categoria, classificacao)
            

        else:
            raise ValueError(f"Categoria não suportada: {categoria}")


