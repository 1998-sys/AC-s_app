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
    """
    Identifica o nome da instalação a partir do número do CI,
    buscando o código numérico de 4 dígitos dos ativos embutido no número.
    Ex: 'CI-1300.0000-...' → 'Cidade de São Miguel dos Campos'
        'CI-FQI-1900002A-...' → 'ESGN'
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
    """
    Extrai a data do CI e converte para o formato DD/MM/AAAA.
    Retorna a última ocorrência, que corresponde à data de emissão no rodapé.
    Ex: '7 maio, 2026' → '07/05/2026'
    """
    meses = "|".join(MESES_PT.keys())
    matches = re.findall(rf'(\d{{1,2}})\s+({meses}),?\s+(\d{{4}})', texto, re.IGNORECASE)
    if not matches:
        return None
    dia, mes, ano = matches[-1]
    return f"{int(dia):02d}/{MESES_PT[mes.lower()]}/{ano}"


def extrair_cliente(texto: str) -> str | None:
    """
    Extrai o nome do cliente da linha 'Cliente: <nome>'.
    Ex: 'Cliente: Origem' → 'Origem'
    """
    match = re.search(r'Cliente[:\s]+(.+?)(?:\n|$)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_tag(texto: str) -> str | None:
    """
    Extrai a TAG da malha da linha 'TAG da Malha ( Loop TAG) : <TAG>'.
    Ex: 'TAG da Malha ( Loop TAG) : FQI-1900002A-02' → 'FQI-1900002A-02'
    """
    match = re.search(r'TAG\s+da\s+Malha\s*\([^)]*\)\s*:\s*(.+)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_descricao_malha(texto: str) -> str | None:
    """
    Extrai a descrição da malha da linha 'Descrição da Malha ( Loop Description ) : <desc>'.
    Ex: 'Descrição da Malha ( Loop Description ) : RETIRADA POÇO' → 'RETIRADA POÇO'
    """
    match = re.search(r'Descri[çc][aã]o\s+da\s+Malha\s*\([^)]*\)\s*:\s*(.+)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_numero_relatorio(texto: str) -> str | None:
    """
    Extrai o número do CI. Tenta dois formatos:
    - Formato antigo: CI-1300.0000-6252-813-O2C-027
    - Formato novo:   número após 'Relatório de Cálculo de Incerteza' ou 'Uncertainty Calculation Report'
                      ex: CI-FQI-1900002A-02-01.26
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
    """
    Extrai duas tabelas específicas do PDF via pdfplumber:
      - 'documentos': lista de instrumentos com TAG e certificado de calibração.
      - 'budget': budget de incerteza com símbolo e contribuição por grandeza.

    A detecção é feita pelo cabeçalho com "documentos" + "certificado".
    Retorna assim que encontrar, sem varrer o restante do PDF.
    """
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
                        if "documentos" in texto and "certificado" in texto:
                            return extrair_apos_cabecalho(dados, i)
    except Exception:
        print(f"Erro ao extrair tabelas de '{caminho_pdf}':")
        traceback.print_exc()

    return None


def extrair_fluxos_dp(texto: str) -> dict:
    """
    Extrai vazão (m³/h) e pressão diferencial (kPa) mínimas e máximas
    das tabelas 'DP High' e, se existir, 'DP Low'.

    A seção é localizada pelo cabeçalho 'Tabelas Vazão x Incerteza'.
    Cada linha de dados tem 3 colunas por DP: Vazão | Incerteza | Pressão.
    O regex captura as 3 colunas de cada DP.

    Com DP Low: 6 colunas por linha → grupos (vazao_H, incerteza_H, pressao_H, vazao_L, incerteza_L, pressao_L).
    Sem DP Low: 3 colunas por linha → grupos (vazao_H, incerteza_H, pressao_H).

    Os pares são ordenados por vazão para garantir que pressao_min/max
    correspondam à menor e maior vazão respectivamente (fisicamente correlatos).
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
        return float(v.replace('.', '').replace(',', '.'))

    def min_max(vazoes: list, incertezas: list, pressoes: list) -> dict:
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
    """
    Transforma as linhas brutas das tabelas em um dict estruturado por instrumento.

    O mapeamento entre nome do instrumento (coluna 0 da tabela 'documentos') e
    a chave do resultado é feito por substring — ex. "Trecho de Medição" → "trecho".

    Trecho e Placa recebem também o diâmetro medido extraído do budget de incerteza:
      - trecho → símbolo 'D' (diâmetro interno do trecho de medição)
      - placa  → símbolo 'd' (diâmetro do orifício a 20 °C)

    DP High e DP Low recebem os valores de vazão e pressão vindos de extrair_fluxos_dp,
    pois esses dados não estão na tabela de documentos — apenas na tabela de vazão.

    O número do certificado é normalizado (espaços removidos) via normalizar_certificado.
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
    """
    Ponto de entrada do parser: coordena a extração completa de um PDF de CI.
    Retorna um dict pronto para ser consumido pelo xml_uc_generator.

    `texto` é opcional — se o chamador já extraiu o texto do PDF (ex.:
    select_extract, que já roda extrair_texto antes de rotear), passe-o aqui
    para evitar reabrir e reprocessar o mesmo PDF.
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
    """
    Verificação rápida usada pelo utils_parser para rotear o PDF antes de
    processar qualquer dado — recebe o texto já extraído (não reabre o PDF)
    e testa o padrão do número CI.
    """
    if extrair_numero_relatorio(texto) is not None:
        return True
    return bool(re.search(r"Relatório de Cálculo de Incerteza|Uncertainty Calculation Report", texto, re.IGNORECASE))
