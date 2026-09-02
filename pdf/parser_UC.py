# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_UC
# Created       : 21-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses Uncertainty Calculation Report (CI) PDFs, extracting instrument, certificate, and DP flow/pressure data.
#                 Analisa PDFs de Relatório de Cálculo de Incerteza (CI), extraindo dados de instrumentos, certificados e vazão/pressão de DP.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re
import logging
import traceback
import pdfplumber
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado

logging.getLogger("pdfminer").setLevel(logging.ERROR)


ativos = {
    "Ananbé": 1100,
    "Arapaçu": 1200,
    "Cidade de São Miguel dos Campos": 1300,
    "Furado": 1400,
    "Paru": 1500,
    "Pilar": 1600,
    "São Miguel dos Campos": 1700,
    "Conceição": 2100,
    "Querará": 2400,
    "ESGN": 1900
}


def identificar_instalacao(numero_ci: str) -> str | None:
    """Identifies the installation name from the CI number.

    Looks for the assets' 4-digit numeric code (`ativos` dict) embedded
    in the CI number. E.g.: 'CI-1300.0000-...' -> 'Cidade de São Miguel dos
    Campos'; 'CI-FQI-1900002A-...' -> 'ESGN'.

    Args:
        numero_ci: Uncertainty Calculation report number.

    Returns:
        str: Matching installation name, or None if `numero_ci` is empty
        or no asset code is found in it.
    """
    if not numero_ci:
        return None

    for nome, codigo in ativos.items():
        if str(codigo) in numero_ci:
            return nome

    return None


MESES_PT = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "abril": "04",
    "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
    "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
}

def extrair_data_ci(texto: str) -> str | None:
    """Extracts the CI date and converts it to DD/MM/YYYY format.

    Returns the last occurrence of the pattern "<day> <month name>, <year>",
    which corresponds to the issue date in the footer (not the first date
    mentioned in the document body). E.g.: '7 maio, 2026' -> '07/05/2026'.

    Args:
        texto: Text extracted from the CI report.

    Returns:
        str: Date in "DD/MM/YYYY" format, or None if no written-out date
        is found.
    """
    meses = "|".join(MESES_PT.keys())
    matches = re.findall(rf'(\d{{1,2}})\s+({meses}),?\s+(\d{{4}})', texto, re.IGNORECASE)
    if not matches:
        return None
    dia, mes, ano = matches[-1]
    return f"{int(dia):02d}/{MESES_PT[mes.lower()]}/{ano}"


def extrair_cliente(texto: str) -> str | None:
    """Extracts the client name from the 'Cliente: <name>' line. E.g.: 'Cliente: Origem' -> 'Origem'."""
    match = re.search(r'Cliente[:\s]+(.+?)(?:\n|$)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_tag(texto: str) -> str | None:
    """Extracts the loop TAG from the 'TAG da Malha ( Loop TAG) : <TAG>' line.

    E.g.: 'TAG da Malha ( Loop TAG) : FQI-1900002A-02' -> 'FQI-1900002A-02'.
    """
    match = re.search(r'TAG\s+da\s+Malha\s*\([^)]*\)\s*:\s*(.+)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_descricao_malha(texto: str) -> str | None:
    """Extracts the loop description from the 'Descrição da Malha ( Loop Description ) : <desc>' line.

    E.g.: 'Descrição da Malha ( Loop Description ) : RETIRADA POÇO' -> 'RETIRADA POÇO'.
    """
    match = re.search(r'Descri[çc][aã]o\s+da\s+Malha\s*\([^)]*\)\s*:\s*(.+)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_numero_relatorio(texto: str) -> str | None:
    """Extracts the CI number, trying two formats.

    First tries the old format (e.g.: "CI-1300.0000-6252-813-O2C-027");
    if it doesn't match, tries the new format — the number that follows
    "Relatório de Cálculo de Incerteza" or "Uncertainty Calculation Report"
    (e.g.: "CI-FQI-1900002A-02-01.26").

    Returns:
        str: CI number in whichever format matched, or None if neither
        pattern matches.
    """
    match = re.search(r'[A-Z]{2}-\d+\.\d+-\d+-\d+-[A-Z0-9]+-\d+(?:[_\.]REV\.\d+)?', texto)
    if match:
        return match.group()

    match = re.search(
        r'(?:Relatório de Cálculo de Incerteza|Uncertainty Calculation Report)\s+([\w\-\.]+)',
        texto,
        re.IGNORECASE
    )
    return match.group(1).strip() if match else None


def extrair_tabelas_uc(caminho_pdf: str) -> dict:
    """Extracts the instruments/certificates table from the CI PDF via pdfplumber.

    Searches all pages for the table whose header contains both "documentos"
    and "certificado" (columns: instrument, TAG, ..., calibration
    certificate) and returns the data rows right below it, stopping at the
    first separator (near-empty row) or the end of the table.
    Returns as soon as it finds it, without scanning the rest of the PDF.

    Args:
        caminho_pdf: Path to the CI report's PDF file.

    Returns:
        list | None: List of rows (each one a list of cells) from the
        documents table, or None if the table isn't found or the reading
        fails (the error is logged, not propagated).
    """
    def e_separador(linha):
        """Treats `linha` as a table separator when it has at most one non-empty cell."""
        return sum(1 for c in linha if c.strip()) <= 1

    def extrair_apos_cabecalho(dados, idx_header):
        """Collects the data rows right after the header index, up to the next separator."""
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
                        if "documentos" in texto and "certificado" in texto:
                            return extrair_apos_cabecalho(dados, i)
    except Exception:
        print(f"Erro ao extrair tabelas de '{caminho_pdf}':")
        traceback.print_exc()

    return None


def extrair_fluxos_dp(texto: str) -> dict:
    """Extracts min/max flow rate (m³/h) and differential pressure (kPa)
    from the 'DP High' and, if present, 'DP Low' tables.

    The section is located via the 'Tabelas Vazão x Incerteza' header.
    Each data row has 3 columns per DP: Flow | Uncertainty | Pressure.
    The regex captures the 3 columns for each DP.

    With DP Low: 6 columns per row -> groups (vazao_H, incerteza_H, pressao_H, vazao_L, incerteza_L, pressao_L).
    Without DP Low: 3 columns per row -> groups (vazao_H, incerteza_H, pressao_H).

    Pairs are sorted by flow rate to guarantee that pressao_min/max
    correspond to the lowest and highest flow rate respectively (physically correlated).

    Args:
        texto: Text extracted from the CI report.

    Returns:
        dict: {"dp_high": dict|None, "dp_low": dict|None}, each sub-dict with
        "vazao_min", "vazao_max", "incerteza_min", "incerteza_max",
        "pressao_min" and "pressao_max" (strings in the PDF's original format).
        "dp_high" and "dp_low" are None if the section or the data aren't
        found; "dp_low" is also None when the report has no DP Low.
    """
    match = re.search(r'Tabelas\s+Vazão\s+x\s+Incerteza', texto, re.IGNORECASE)
    if not match:
        return {"dp_high": None, "dp_low": None}

    secao = texto[match.start():]
    tem_dp_low = bool(re.search(r'DP\s+Low', secao, re.IGNORECASE))

    num = r'\d[\d.]*(?:,\d+)?'

    # Captura: vazao_high, incerteza_high, pressao_high, [vazao_low, incerteza_low, pressao_low]
    if tem_dp_low:
        padrao = re.compile(
            rf'^({num})\s+({num})\s+({num})\s+({num})\s+({num})\s+({num})$',
            re.MULTILINE
        )
    else:
        padrao = re.compile(rf'^({num})\s+({num})\s+({num})$', re.MULTILINE)

    matches = padrao.findall(secao)
    if not matches:
        return {"dp_high": None, "dp_low": None}

    def br_float(v: str) -> float:
        """Converts a number in PT-BR format (thousands dot, decimal comma) to float."""
        return float(v.replace('.', '').replace(',', '.'))

    def min_max(vazoes: list, incertezas: list, pressoes: list) -> dict:
        """Sorts the (flow, uncertainty, pressure) triples by flow and returns the lowest/highest-flow pairs."""
        # Ordena pelo valor da vazão para manter o par vazão↔pressão coerente
        pares = sorted(zip(vazoes, incertezas, pressoes), key=lambda x: br_float(x[0]))
        return {
            "vazao_min":      pares[0][0],
            "vazao_max":      pares[-1][0],
            "incerteza_min":  pares[0][1],
            "incerteza_max":  pares[-1][1],
            "pressao_min":    pares[0][2],
            "pressao_max":    pares[-1][2],
        }

    if tem_dp_low:
        return {
            "dp_high": min_max([m[0] for m in matches], [m[1] for m in matches], [m[2] for m in matches]),
            "dp_low":  min_max([m[3] for m in matches], [m[4] for m in matches], [m[5] for m in matches]),
        }
    else:
        return {
            "dp_high": min_max([m[0] for m in matches], [m[1] for m in matches], [m[2] for m in matches]),
            "dp_low":  None,
        }


def organizar_dados_uc(documentos: list | None, fluxos: dict | None = None) -> dict:
    """Turns the tables' raw rows into a dict structured by instrument.

    The mapping between instrument name (column 0 of the 'documentos' table) and
    the result key is done by substring — e.g. "Trecho de Medição" -> "trecho".

    Trecho and Placa also receive the measured diameter extracted from the uncertainty budget:
      - trecho -> symbol 'D' (internal diameter of the meter run)
      - placa  -> symbol 'd' (orifice diameter at 20 °C)

    DP High and DP Low receive the flow and pressure values from extrair_fluxos_dp,
    since that data isn't in the documents table — only in the flow table.

    The certificate number is normalized (spaces removed) via normalizar_certificado.
    """
    MAPA_INSTRUMENTOS = {
        "trecho":        "trecho",
        "placa":         "placa",
        "termômetro":    "termometro",
        "temperatura":   "termometro",
        "termorresist":  "termoresistencia",
        "estática":      "pressao_estatica",
        "high":          "dp_high",
        "low":           "dp_low",
        "diferencial":   "dp_high",
    }

    resultado = {}

    for linha in (documentos or []):
        nome        = linha[0].strip()
        tag         = linha[1].strip()
        certificado = normalizar_certificado(linha[-1].strip())

        chave = None
        for palavra, k in MAPA_INSTRUMENTOS.items():
            if palavra in nome.lower():
                chave = k
                break
        if chave is None:
            continue  # linha não reconhecida pelo mapa, ignora

        dados_instrumento = {
            "tag":         tag,
            "certificado": certificado,
            "u":           linha[3].strip() if len(linha) > 3 else "",
            "fator_k":     linha[4].strip() if len(linha) > 4 else "",
            "erro":        linha[5].strip() if len(linha) > 5 else "",
        }

        if linha[-2].strip() == "mm":
            dados_instrumento["diametro"] = linha[-3].strip()

        # Injeta vazão e pressão para transmissores de pressão diferencial
        if fluxos and chave in ("dp_high", "dp_low"):
            fluxo_dp = fluxos.get(chave)
            if fluxo_dp:
                dados_instrumento.update(fluxo_dp)

        resultado[chave] = dados_instrumento

    return resultado


def extrair_campos_uc(caminho: str, texto: str = None) -> dict:
    """Parser entry point: coordinates the full extraction of a CI PDF.
    Returns a dict ready to be consumed by xml_uc_generator.

    `texto` is optional — if the caller has already extracted the PDF text
    (e.g.: select_extract, which already runs extrair_texto before routing),
    pass it here to avoid reopening and reprocessing the same PDF.
    """
    if texto is None:
        texto = extrair_texto(caminho)
    numero_ci = extrair_numero_relatorio(texto)
    ativo = identificar_instalacao(numero_ci) if numero_ci else None
    data = extrair_data_ci(texto)
    cliente = extrair_cliente(texto)
    tag = extrair_tag(texto)
    nome_sistema = extrair_descricao_malha(texto)
    documentos = extrair_tabelas_uc(caminho)
    fluxos = extrair_fluxos_dp(texto)
    dados = organizar_dados_uc(documentos, fluxos)
    ci_dados = {
        "numero_ci":    numero_ci    or "NI",
        "ativo":       ativo        or "NI",
        "data":        data         or "NI",
        "tag":          tag          or "NI",
        "nome_sistema": nome_sistema or "NI",
        "cliente":      cliente      or "NI",
        "tipo": "ci",
        **dados,
    }
    return ci_dados


def identificar_uc(texto: str) -> bool:
    """Quick check used by utils_parser to route the PDF before processing
    any data — receives the already-extracted text (does not reopen the PDF)
    and tests the CI number pattern.
    """
    if extrair_numero_relatorio(texto) is not None:
        return True
    return bool(re.search(r"Relatório de Cálculo de Incerteza|Uncertainty Calculation Report", texto, re.IGNORECASE))
