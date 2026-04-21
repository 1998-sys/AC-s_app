import re
import logging
import pdfplumber
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def extrair_numero_relatorio(texto: str) -> str | None:
    """
    Identifica se o PDF é um CI pelo número de relatório (ex: CI-1300.0000-6252-813-O2C-027).
    Esse padrão é o discriminador principal usado por identificar_uc:
    se não bater, o arquivo não é roteado como CI no utils_parser.
    """
    pattern = r'[A-Z]{2}-\d+\.\d+-\d+-\d+-[A-Z0-9]+-\d+'
    match = re.search(pattern, texto)
    return match.group() if match else None


def extrair_tabelas_uc(caminho_pdf: str) -> dict:
    """
    Extrai duas tabelas específicas do PDF via pdfplumber:
      - 'documentos': lista de instrumentos com TAG e certificado de calibração.
      - 'budget': budget de incerteza com símbolo e contribuição por grandeza.

    A detecção de cada tabela é feita pelo cabeçalho:
      - 'documentos' → linha com "documentos" + "certificado"
      - 'budget'     → linha com "símbolo" + "contribuição"

    Linhas com apenas uma célula preenchida são tratadas como separadores de seção
    e encerram a coleta de dados daquela tabela.
    Retorna imediatamente ao encontrar ambas, sem varrer o restante do PDF.
    """
    resultado = {"documentos": None, "budget": None}

    def e_separador(linha):
        # Uma linha quase vazia indica título ou espaçador entre seções
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
    """
    Extrai vazão (m³/h) e pressão diferencial (kPa) mínimas e máximas
    das tabelas 'DP High' e, se existir, 'DP Low'.

    A seção é localizada pelo cabeçalho 'Tabelas Vazão x Incerteza'.
    Cada linha de dados tem 3 colunas por DP: Vazão | Incerteza | Pressão.
    O regex captura apenas a 1ª e 3ª colunas (ignora a incerteza do meio).

    Com DP Low: 6 colunas por linha → grupos (vazao_H, pressao_H, vazao_L, pressao_L).
    Sem DP Low: 3 colunas por linha → grupos (vazao_H, pressao_H).

    Os pares são ordenados por vazão para garantir que pressao_min/max
    correspondam à menor e maior vazão respectivamente (fisicamente correlatos).
    """
    match = re.search(r'Tabelas\s+Vazão\s+x\s+Incerteza', texto, re.IGNORECASE)
    if not match:
        return {"dp_high": None, "dp_low": None}

    secao = texto[match.start():]
    tem_dp_low = bool(re.search(r'DP\s+Low', secao, re.IGNORECASE))

    num = r'\d[\d.]*(?:,\d+)?'

    # Captura: vazao_high, pressao_high, [vazao_low, pressao_low]
    if tem_dp_low:
        padrao = re.compile(
            rf'^({num})\s+{num}\s+({num})\s+({num})\s+{num}\s+({num})$',
            re.MULTILINE
        )
    else:
        padrao = re.compile(rf'^({num})\s+{num}\s+({num})$', re.MULTILINE)

    matches = padrao.findall(secao)
    if not matches:
        return {"dp_high": None, "dp_low": None}

    def br_float(v: str) -> float:
        return float(v.replace('.', '').replace(',', '.'))

    def min_max(vazoes: list, pressoes: list) -> dict:
        # Ordena pelo valor da vazão para manter o par vazão↔pressão coerente
        pares = sorted(zip(vazoes, pressoes), key=lambda x: br_float(x[0]))
        return {
            "vazao_min":   pares[0][0],
            "vazao_max":   pares[-1][0],
            "pressao_min": pares[0][1],
            "pressao_max": pares[-1][1],
        }

    if tem_dp_low:
        return {
            "dp_high": min_max([m[0] for m in matches], [m[1] for m in matches]),
            "dp_low":  min_max([m[2] for m in matches], [m[3] for m in matches]),
        }
    else:
        return {
            "dp_high": min_max([m[0] for m in matches], [m[1] for m in matches]),
            "dp_low":  None,
        }


def organizar_dados_uc(tabelas: dict, fluxos: dict | None = None) -> dict:
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
        "trecho":      "trecho",
        "placa":       "placa",
        "termômetro":  "termometro",
        "estática":    "pressao_estatica",
        "high":        "dp_high",
        "low":         "dp_low",
    }

    # Instrumentos cujo diâmetro medido está registrado no budget de incerteza
    DIAMETRO_POR_INSTRUMENTO = {
        "trecho": "D",
        "placa":  "d",
    }

    # Indexa o budget por símbolo para lookup O(1) durante o loop de documentos
    budget_por_simbolo = {}
    for linha in (tabelas.get("budget") or []):
        simbolo = linha[2].strip()
        if simbolo:
            budget_por_simbolo[simbolo] = linha[4].strip()

    resultado = {}

    for linha in (tabelas.get("documentos") or []):
        nome        = linha[0].strip()
        tag         = linha[1].strip()
        certificado = normalizar_certificado(linha[7].strip())

        chave = None
        for palavra, k in MAPA_INSTRUMENTOS.items():
            if palavra in nome.lower():
                chave = k
                break
        if chave is None:
            continue  # linha não reconhecida pelo mapa, ignora

        dados_instrumento = {"tag": tag, "certificado": certificado}

        simbolo_d = DIAMETRO_POR_INSTRUMENTO.get(chave)
        if simbolo_d and simbolo_d in budget_por_simbolo:
            dados_instrumento["diametro"] = budget_por_simbolo[simbolo_d]

        # Injeta vazão e pressão para transmissores de pressão diferencial
        if fluxos and chave in ("dp_high", "dp_low"):
            fluxo_dp = fluxos.get(chave)
            if fluxo_dp:
                dados_instrumento.update(fluxo_dp)

        resultado[chave] = dados_instrumento

    return resultado


def extrair_campos_uc(caminho: str) -> dict:
    """
    Ponto de entrada do parser: coordena a extração completa de um PDF de CI.
    Retorna um dict pronto para ser consumido pelo xml_uc_generator.
    """
    texto = extrair_texto(caminho)
    numero_ci = extrair_numero_relatorio(texto)
    tabelas = extrair_tabelas_uc(caminho)
    fluxos = extrair_fluxos_dp(texto)
    dados = organizar_dados_uc(tabelas, fluxos)
    ci_dados = {
        "numero_ci": numero_ci or "NI",
        "tipo": "ci",
        **dados,
    }
    print(ci_dados)
    return ci_dados


def identificar_uc(caminho: str) -> bool:
    """
    Verificação rápida usada pelo utils_parser para rotear o PDF antes de
    processar qualquer dado. Lê apenas o texto e testa o padrão do número CI.
    """
    texto = extrair_texto(caminho)
    return extrair_numero_relatorio(texto) is not None
