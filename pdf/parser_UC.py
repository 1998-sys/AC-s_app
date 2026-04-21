import re
import logging
import pdfplumber
from pdf.extrator import extrair_texto

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def extrair_numero_relatorio(texto: str) -> str | None:
    pattern = r'[A-Z]{2}-\d+\.\d+-\d+-\d+-[A-Z0-9]+-\d+'
    match = re.search(pattern, texto)
    return match.group() if match else None


def extrair_tabelas_uc(caminho_pdf: str) -> dict:
    resultado = {"documentos": None, "budget": None}

    def e_separador(linha):
        return sum(1 for c in linha if c.strip()) <= 1

    def extrair_apos_cabecalho(dados, idx_header):
        linhas = []
        for linha in dados[idx_header + 1:]:
            if e_separador(linha):
                break
            linhas.append(linha)
        return linhas if linhas else None

    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            for pagina in pdf.pages:
                for tabela in pagina.extract_tables():
                    dados = [
                        [c if c is not None else "" for c in linha]
                        for linha in tabela
                    ]
                    for i, linha in enumerate(dados):
                        texto = " ".join(linha).lower()
                        if resultado["documentos"] is None and "documentos" in texto and "certificado" in texto:
                            resultado["documentos"] = extrair_apos_cabecalho(dados, i)
                        if resultado["budget"] is None and "símbolo" in texto and "contribuição" in texto:
                            resultado["budget"] = extrair_apos_cabecalho(dados, i)
                    if all(v is not None for v in resultado.values()):
                        return resultado
    except Exception as e:
        print(f"Erro ao extrair tabelas de '{caminho_pdf}': {e}")

    return resultado


def extrair_fluxos_dp(texto: str) -> dict:
    match = re.search(r'Tabelas\s+Vazão\s+x\s+Incerteza', texto, re.IGNORECASE)
    if not match:
        return {"dp_high": None, "dp_low": None}

    secao = texto[match.start():]
    tem_dp_low = bool(re.search(r'DP\s+Low', secao, re.IGNORECASE))

    num = r'\d[\d.]*(?:,\d+)?'

    if tem_dp_low:
        padrao = re.compile(
            rf'^({num})\s+{num}\s+{num}\s+({num})\s+{num}\s+{num}$',
            re.MULTILINE
        )
    else:
        padrao = re.compile(rf'^({num})\s+{num}\s+{num}$', re.MULTILINE)

    matches = padrao.findall(secao)
    if not matches:
        return {"dp_high": None, "dp_low": None}

    def br_float(v: str) -> float:
        return float(v.replace('.', '').replace(',', '.'))

    def min_max(valores: list) -> dict:
        ordenados = sorted(valores, key=br_float)
        return {"vazao_min": ordenados[0], "vazao_max": ordenados[-1]}

    if tem_dp_low:
        vals_high = [m[0] for m in matches]
        vals_low  = [m[1] for m in matches]
    else:
        vals_high = list(matches)
        vals_low  = []

    return {
        "dp_high": min_max(vals_high),
        "dp_low":  min_max(vals_low) if vals_low else None,
    }


def organizar_dados_uc(tabelas: dict, fluxos: dict | None = None) -> dict:
    MAPA_INSTRUMENTOS = {
        "trecho":      "trecho",
        "placa":       "placa",
        "termômetro":  "termometro",
        "estática":    "pressao_estatica",
        "high":        "dp_high",
        "low":         "dp_low",
    }

    DIAMETRO_POR_INSTRUMENTO = {
        "trecho": "D",
        "placa":  "d",
    }

    budget_por_simbolo = {}
    for linha in (tabelas.get("budget") or []):
        simbolo = linha[2].strip()
        if simbolo:
            budget_por_simbolo[simbolo] = linha[4].strip()

    resultado = {}

    for linha in (tabelas.get("documentos") or []):
        nome        = linha[0].strip()
        tag         = linha[1].strip()
        certificado = linha[7].strip()

        chave = None
        for palavra, k in MAPA_INSTRUMENTOS.items():
            if palavra in nome.lower():
                chave = k
                break
        if chave is None:
            continue

        dados_instrumento = {"tag": tag, "certificado": certificado}

        simbolo_d = DIAMETRO_POR_INSTRUMENTO.get(chave)
        if simbolo_d and simbolo_d in budget_por_simbolo:
            dados_instrumento["diametro"] = budget_por_simbolo[simbolo_d]

        if fluxos and chave in ("dp_high", "dp_low"):
            fluxo_dp = fluxos.get(chave)
            if fluxo_dp:
                dados_instrumento.update(fluxo_dp)

        resultado[chave] = dados_instrumento

    return resultado


def extrair_campos_uc(caminho: str) -> dict:
    texto = extrair_texto(caminho)
    numero_ci = extrair_numero_relatorio(texto)
    tabelas = extrair_tabelas_uc(caminho)
    fluxos = extrair_fluxos_dp(texto)
    dados = organizar_dados_uc(tabelas, fluxos)
    return {
        "numero_ci": numero_ci or "NI",
        "tipo": "ci",
        **dados,
    }


def identificar_uc(caminho: str) -> bool:
    """Retorna True se o PDF for um relatório de cálculo de incerteza (CI)."""
    texto = extrair_texto(caminho)
    return extrair_numero_relatorio(texto) is not None
