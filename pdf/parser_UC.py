import re
import logging
import pdfplumber
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def extrair_cliente(texto: str) -> str | None:
    """
    Extrai o nome do cliente da linha 'Cliente: <nome>'.
    Ex: 'Cliente: Origem' → 'Origem'
    """
    match = re.search(r'Cliente[:\s]+(.+?)(?:\n|$)', texto, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extrair_tag_sistema(texto: str) -> tuple[str | None, str | None]:
    """
    Extrai a TAG e o nome do sistema da linha de identificação.
    Ex: 'FT-SG-122101-01 - TESTE POÇO - SG-122101'
         → ('FT-SG-122101-01', 'TESTE POÇO - SG-122101')
    """
    pattern = r'([A-Z]{2,4}-[A-Z]+-\d{5,6}-\d{2})\s*-\s*(.+)'
    match = re.search(pattern, texto, re.MULTILINE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, None


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
    except Exception as e:
        print(f"Erro ao extrair tabelas de '{caminho_pdf}': {e}")

    return None


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

        dados_instrumento = {"tag": tag, "certificado": certificado}

        if linha[-2].strip() == "mm":
            dados_instrumento["diametro"] = linha[-3].strip()

        # Injeta vazão e pressão para transmissores de pressão diferencial
        if fluxos and chave in ("dp_high", "dp_low"):
            fluxo_dp = fluxos.get(chave)
            if fluxo_dp:
                dados_instrumento.update(fluxo_dp)

        resultado[chave] = dados_instrumento
    
    print("Dados organizados por instrumento:", resultado)

    return resultado


def extrair_campos_uc(caminho: str) -> dict:
    """
    Ponto de entrada do parser: coordena a extração completa de um PDF de CI.
    Retorna um dict pronto para ser consumido pelo xml_uc_generator.
    """
    texto = extrair_texto(caminho)
    numero_ci = extrair_numero_relatorio(texto)
    cliente = extrair_cliente(texto)
    tag, nome_sistema = extrair_tag_sistema(texto)
    documentos = extrair_tabelas_uc(caminho)
    print("Tabelas extraídas:", documentos)
    fluxos = extrair_fluxos_dp(texto)
    dados = organizar_dados_uc(documentos, fluxos)
    ci_dados = {
        "numero_ci":    numero_ci    or "NI",
        "tag":          tag          or "NI",
        "nome_sistema": nome_sistema or "NI",
        "cliente":      cliente      or "NI",
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
