# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_UC
# Created       : 21-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses Uncertainty Calculation Report (CI) PDFs, extracting instrument, certificate, and DP flow/pressure data.
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
    Falls back to a plain "DD/MM/YYYY" match (also the last occurrence) when
    no written-out month name is found — the newer report layout signs only
    with a numeric date, no month name anywhere in the document.

    Args:
        texto: Text extracted from the CI report.

    Returns:
        str: Date in "DD/MM/YYYY" format, or None if neither format is found.
    """
    meses = "|".join(MESES_PT.keys())
    matches = re.findall(rf'(\d{{1,2}})\s+({meses}),?\s+(\d{{4}})', texto, re.IGNORECASE)
    if matches:
        dia, mes, ano = matches[-1]
        return f"{int(dia):02d}/{MESES_PT[mes.lower()]}/{ano}"

    matches_numericas = re.findall(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', texto)
    if matches_numericas:
        dia, mes, ano = matches_numericas[-1]
        return f"{int(dia):02d}/{int(mes):02d}/{ano}"

    return None


def _extrair_rotulo_bilingue(texto: str, *rotulos: str) -> str | None:
    """Extracts the value after any of `rotulos`, regardless of which language comes first.

    The report template has two revisions that differ in the order of the
    bilingual field labels — older: "Cliente ( Customer ): valor"; newer:
    "Customer ( Cliente ): valor". Anchoring on either label and capturing
    up to the first colon after it (lazily, so it skips over the
    parenthetical translation) handles both orders with one pattern.

    Args:
        texto: Text extracted from the CI report.
        *rotulos: Label variants to anchor on (any language/order), as
            regex fragments (not escaped — pass e.g. "TAG\\s+da\\s+Malha"
            for a multi-word label, or a plain word for a single one).

    Returns:
        str: The captured value, or None if none of the labels are found.
    """
    alternativas = "|".join(rotulos)
    match = re.search(rf'(?:{alternativas})\b.*?:\s*(.+?)(?:\n|$)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_cliente(texto: str) -> str | None:
    """Extracts the client name from the 'Cliente'/'Customer' line. E.g.: 'Customer ( Cliente ): Origem' -> 'Origem'."""
    return _extrair_rotulo_bilingue(texto, "Cliente", "Customer")


def extrair_tag(texto: str) -> str | None:
    """Extracts the loop TAG from the 'TAG da Malha'/'Loop Tag' line.

    E.g.: 'Loop Tag ( Tag da Malha ): UT-SG-122101-01' -> 'UT-SG-122101-01'.
    """
    return _extrair_rotulo_bilingue(texto, "TAG\\s+da\\s+Malha", "Loop\\s+Tag")


def extrair_descricao_malha(texto: str) -> str | None:
    """Extracts the loop description from the 'Descrição da Malha'/'Loop Description' line.

    E.g.: 'Loop Description ( Descrição da Malha ): TESTE POÇO - SG-122101-01' -> 'TESTE POÇO - SG-122101-01'.
    """
    return _extrair_rotulo_bilingue(texto, "Descri[çc][aã]o\\s+da\\s+Malha", "Loop\\s+Description")


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


def extrair_tabelas_uc(caminho_pdf: str) -> tuple:
    """Extracts the instruments/certificates table from the CI PDF via pdfplumber.

    Searches all pages for the table whose header contains both "documentos"
    and "certificado" (columns: instrument, TAG, ..., calibration
    certificate) and returns that header row plus the data rows right below
    it, stopping at the first separator (near-empty row) or the end of the
    table. Returns as soon as it finds it, without scanning the rest of the PDF.

    Args:
        caminho_pdf: Path to the CI report's PDF file.

    Returns:
        tuple: (cabecalho, linhas) — cabecalho is the header row (list of
        cells), used by organizar_dados_uc to map columns by name for report
        layouts whose column order/count differs from the original one;
        linhas is the list of data rows below it. Both are None if the
        table isn't found or the reading fails (the error is logged, not
        propagated).
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
                            return linha, extrair_apos_cabecalho(dados, i)
    except Exception:
        print(f"Erro ao extrair tabelas de '{caminho_pdf}':")
        traceback.print_exc()

    return None, None


def extrair_fluxos_dp(texto: str) -> dict:
    """Extracts min/max flow rate (m³/h) and differential pressure (kPa)
    from the 'DP High' and, if present, 'DP Low' tables.

    The section is located via the 'Tabela(s) Vazão x Incerteza'/'Table Flow
    x Uncertainty' header (older revision: plural "Tabelas"; newer: singular
    "Tabela"). Each data row has 3 columns per DP; the column order differs
    between revisions — older: Flow | Uncertainty | Pressure; newer: Flow |
    Pressure | Uncertainty (headed "Qv | DP | U (%)", detected via the "Qv"
    marker, which only appears in the newer layout's header).

    With DP Low: 6 columns per row -> groups (vazao_H, ?, ?, vazao_L, ?, ?).
    Without DP Low: 3 columns per row -> groups (vazao_H, ?, ?).

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
    match = re.search(
        r'Tabelas?\s+Vaz[ãa]o\s+x\s+Incerteza|Table\s+Flow\s+x\s+Uncertainty',
        texto, re.IGNORECASE
    )
    if not match:
        return {"dp_high": None, "dp_low": None}

    secao = texto[match.start():]
    tem_dp_low = bool(re.search(r'DP\s+Low', secao, re.IGNORECASE))
    # "Qv" only appears in the newer revision's header ("Qv | DP | U (%)"),
    # where pressure comes before uncertainty — the older revision uses
    # "Vazão | Incerteza | Pressão", so this marker distinguishes the two
    # without needing an actual sample of each revision to compare.
    pressao_antes_incerteza = bool(re.search(r'\bQv\b', secao[:600], re.IGNORECASE))

    num = r'\d[\d.]*(?:,\d+)?'

    # Captures 3 (or 6, with DP Low) numbers per line — the meaning of each
    # column depends on pressao_antes_incerteza (see _extrair_grupo_dp).
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
        """Converts a number to float, in either PT-BR format (thousands dot,
        decimal comma, e.g. "4.815,70") or plain format (decimal point, no
        thousands separator, e.g. "4815.7" — used by the newer report
        revision). Only treats dots as thousands separators when a comma is
        also present; otherwise the dot is the decimal separator.
        """
        v = v.strip()
        if ',' in v:
            return float(v.replace('.', '').replace(',', '.'))
        return float(v)

    def min_max(vazoes: list, incertezas: list, pressoes: list) -> dict:
        """Sorts the (flow, uncertainty, pressure) triples by flow and returns the lowest/highest-flow pairs."""
        # Sorts by flow rate value to keep the flow↔pressure pair consistent
        pares = sorted(zip(vazoes, incertezas, pressoes), key=lambda x: br_float(x[0]))
        return {
            "vazao_min":      pares[0][0],
            "vazao_max":      pares[-1][0],
            "incerteza_min":  pares[0][1],
            "incerteza_max":  pares[-1][1],
            "pressao_min":    pares[0][2],
            "pressao_max":    pares[-1][2],
        }

    def extrair_grupo(m: tuple, offset: int) -> tuple:
        """Reads one DP's 3-column group starting at `offset`, honoring the detected column order.

        Returns:
            tuple: (vazao, incerteza, pressao), regardless of their original
            column order in the report.
        """
        if pressao_antes_incerteza:
            vazao, pressao, incerteza = m[offset], m[offset + 1], m[offset + 2]
        else:
            vazao, incerteza, pressao = m[offset], m[offset + 1], m[offset + 2]
        return vazao, incerteza, pressao

    if tem_dp_low:
        altos  = [extrair_grupo(m, 0) for m in matches]
        baixos = [extrair_grupo(m, 3) for m in matches]
        return {
            "dp_high": min_max([g[0] for g in altos],  [g[1] for g in altos],  [g[2] for g in altos]),
            "dp_low":  min_max([g[0] for g in baixos], [g[1] for g in baixos], [g[2] for g in baixos]),
        }
    else:
        grupos = [extrair_grupo(m, 0) for m in matches]
        return {
            "dp_high": min_max([g[0] for g in grupos], [g[1] for g in grupos], [g[2] for g in grupos]),
            "dp_low":  None,
        }


def _mapear_colunas_documentos(cabecalho: list | None) -> dict | None:
    """Maps each relevant field to its column index by matching the documents table's header text.

    The original layout (TAG in column 1, certificate in the last column)
    is fixed-position and doesn't have a documented header sample to
    validate a name-based mapping against, so it's kept as the fallback in
    organizar_dados_uc. This function only recognizes the newer, wider
    layout (which added a "Serial Number" column and lists the certificate
    before the trailing blank columns, breaking the old fixed positions) —
    when it can't confidently map all required columns, the caller falls
    back to the original fixed-position logic untouched.

    Args:
        cabecalho: Header row of the documents table (list of cells), or None.

    Returns:
        dict | None: {"tag": i, "u": i, "erro": i, "unidade": i,
        "certificado": i, "diametro": i|None}, or None if `cabecalho` is
        None or any required column isn't found.
    """
    if not cabecalho:
        return None

    indices = {}
    for i, cel in enumerate(cabecalho):
        texto = (cel or "").strip().lower()
        if not texto:
            continue
        if "identifica" in texto and "tag" not in indices:
            indices["tag"] = i
        elif texto == "u":
            indices["u"] = i
        elif "maximum error" in texto or "erro máximo" in texto or "erro maximo" in texto:
            indices["erro"] = i
        elif "diameter" in texto or "diâmetro" in texto or "diametro" in texto:
            indices["diametro"] = i
        elif "unit" in texto or "unidade" in texto:
            indices["unidade"] = i
        elif "certificate" in texto or "certificado" in texto:
            indices["certificado"] = i

    obrigatorias = {"tag", "u", "erro", "unidade", "certificado"}
    return indices if obrigatorias.issubset(indices) else None


def organizar_dados_uc(documentos: list | None, fluxos: dict | None = None, cabecalho: list | None = None) -> dict:
    """Turns the tables' raw rows into a dict structured by instrument.

    The mapping between instrument name (column 0 of the 'documentos' table) and
    the result key is done by substring — e.g. "Trecho de Medição" -> "trecho".

    Column positions differ between report layout revisions (see
    _mapear_colunas_documentos), so columns are mapped by the header's text
    first; only when that mapping isn't confident does this fall back to the
    original fixed positions (column 1 = TAG, last column = certificate)
    that the older layout used.

    Trecho and Placa also receive the measured diameter, when the row's own
    unit column reads "mm" (both layouts place it right next to the
    diameter value, just at a different column index).

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

    colunas = _mapear_colunas_documentos(cabecalho)
    resultado = {}

    for linha in (documentos or []):
        nome = linha[0].strip()

        chave = None
        for palavra, k in MAPA_INSTRUMENTOS.items():
            if palavra in nome.lower():
                chave = k
                break
        if chave is None:
            continue  # row not recognized by the map, skip

        if colunas:
            dados_instrumento = {
                "tag":         linha[colunas["tag"]].strip(),
                "certificado": normalizar_certificado(linha[colunas["certificado"]].strip()),
                "u":           linha[colunas["u"]].strip(),
                "fator_k":     "",  # this layout has no separate coverage-factor column
                "erro":        linha[colunas["erro"]].strip(),
            }
            idx_diametro = colunas.get("diametro")
            if idx_diametro is not None and linha[colunas["unidade"]].strip().lower() == "mm":
                dados_instrumento["diametro"] = linha[idx_diametro].strip()
        else:
            dados_instrumento = {
                "tag":         linha[1].strip(),
                "certificado": normalizar_certificado(linha[-1].strip()),
                "u":           linha[3].strip() if len(linha) > 3 else "",
                "fator_k":     linha[4].strip() if len(linha) > 4 else "",
                "erro":        linha[5].strip() if len(linha) > 5 else "",
            }
            if linha[-2].strip() == "mm":
                dados_instrumento["diametro"] = linha[-3].strip()

        # Injects flow rate and pressure for differential pressure transmitters
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
    cabecalho, documentos = extrair_tabelas_uc(caminho)
    fluxos = extrair_fluxos_dp(texto)
    dados = organizar_dados_uc(documentos, fluxos, cabecalho)
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
