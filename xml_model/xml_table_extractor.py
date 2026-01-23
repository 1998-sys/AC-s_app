import pdfplumber
import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pdf.parser_certificados import extrair_categoria_intrumento


# =====================================================
# CONVERSÕES
# =====================================================

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


# =====================================================
# EXTRAÇÃO PDF
# =====================================================

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


# =====================================================
# AJUSTES POR CATEGORIA
# =====================================================

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
                "referencia": to_float(linha[0]),
                "media_celsius": to_float(linha[1]),
                "media_mA": to_float(linha[2]),
                "erro": to_float(linha[3]),
                "incerteza": to_valor_eng(linha[4]),
                "k": to_valor_eng(linha[5]),
                "veff": to_valor_eng(linha[6]) if len(linha) > 6 else None
            })

        resultado[f"tabela{idx}"] = tipo.replace("_", " ")
        resultado[f"results{idx}"] = registros
        idx += 1

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


# =====================================================
# PROCESSAMENTO PRINCIPAL
# =====================================================

def processar_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:

        categoria = extrair_categoria_intrumento(
            extrair_texto_pagina(pdf, 0)
        ).upper()

        tabelas = extrair_tabelas_pagina_2(pdf)
        classificacao = classificar_tabelas(tabelas)
        
        

        if "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA" in categoria:
            return ajustar_transmissor_pressao_eletrico(categoria, classificacao)

        elif "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA" in categoria:
            return ajustar_transmissor_temperatura_eletrico(categoria, classificacao)

        elif any(c in categoria for c in [
            "MANOMETRO DIGITAL",
            "MANOMETRO ANALÓGICO",
            "MANOMETRO DIGITAL ABSOLUTO",
            "MANOMETRO DIFERENCIAL DIGITAL",
            "MANOMETRO DIFERENCIAL ANALÓGICO"
        ]):
            return ajustar_manometros(categoria, classificacao)

        elif any(c in categoria for c in [
            "TERMORRESISTÊNCIA PT‐100 ‐ 2 FIOS",
            "TERMORRESISTÊNCIA PT‐100 ‐ 3 FIOS",
            "TERMORRESISTÊNCIA PT‐100 ‐ 4 FIOS"
        ]):
            return ajustar_pt100(categoria, classificacao)

        else:
            raise ValueError(f"Categoria não suportada: {categoria}")


# =====================================================
# TESTE
# =====================================================

caminho_pdf = "xml_model\\25-ODS-37-PRE-555_044-PT-1020A.pdf"
resultado = processar_pdf(caminho_pdf)
