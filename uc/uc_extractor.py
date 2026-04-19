import sys
import os
import re
import pdfplumber
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pdf.extrator import extrair_texto
import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR)


def extrair_numero_relatorio(texto: str) -> str | None:
    """
    Extrai o número do relatório de cálculo de incerteza.
    Exemplo: CI-1300.0000-6252-813-O2C-027
    """
    pattern = r'[A-Z]{2}-\d+\.\d+-\d+-\d+-[A-Z0-9]+-\d+'
    match = re.search(pattern, texto)
    return match.group() if match else None


def extrair_tabelas_uc(caminho_pdf: str) -> dict:
    """
    Extrai as duas tabelas do relatório de incerteza:
      - 'documentos': linhas de instrumentos com certificados de calibração
      - 'budget': linhas do budget de incerteza (contribuições por grandeza)
    Retorna dict com as chaves 'documentos' e 'budget', cada uma com lista de linhas de dados
    (sem a linha de cabeçalho).
    """
    resultado = {"documentos": None, "budget": None}

    def e_separador(linha):
        """Linha com apenas 1 célula preenchida indica título/separador de seção."""
        return sum(1 for c in linha if c.strip()) <= 1

    def extrair_apos_cabecalho(dados, idx_header):
        """Coleta linhas de dados após o cabeçalho até encontrar um separador ou fim."""
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
    Extrai vazão mínima e máxima de DP High e DP Low a partir do texto do PDF.
    Seção identificada pelo cabeçalho 'Tabelas Vazão x Incerteza'.
    DP Low é opcional — retorna None se não existir.
    Retorna: {'dp_high': {'vazao_min': ..., 'vazao_max': ...}, 'dp_low': ... | None}
    """
    match = re.search(r'Tabelas\s+Vazão\s+x\s+Incerteza', texto, re.IGNORECASE)
    if not match:
        return {"dp_high": None, "dp_low": None}

    secao = texto[match.start():]
    tem_dp_low = bool(re.search(r'DP\s+Low', secao, re.IGNORECASE))

    # Número no formato brasileiro: 1324,85 / 62,000 / 369,371
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
    """
    Organiza os dados extraídos de extrair_tabelas_uc em um dicionário estruturado.

    Instrumentos com diâmetro (trecho e placa) recebem também o valor do budget:
      - trecho → diâmetro interno medido (símbolo 'D')
      - placa  → diâmetro do orifício    (símbolo 'd')
    dp_high e dp_low recebem vazao_min e vazao_max se fluxos for informado.
    Os demais instrumentos retornam apenas tag e certificado.
    """
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

        # Adiciona vazao_min / vazao_max para dp_high e dp_low
        if fluxos and chave in ("dp_high", "dp_low"):
            fluxo_dp = fluxos.get(chave)
            if fluxo_dp:
                dados_instrumento.update(fluxo_dp)

        resultado[chave] = dados_instrumento

    return resultado


def gerar_xml_uc(numero_ci: str, dados: dict) -> str:
    """
    Gera o XML do relatório de incerteza a partir do número do CI e do dict
    retornado por organizar_dados_uc.
    SensorTemperatura é incluído com 'NI' quando não há dados.
    TransmissorPD faixa='low' é omitido quando DP Low não existir.
    """
    def v(chave_instrumento: str, campo: str) -> str:
        return dados.get(chave_instrumento, {}).get(campo, "NI")

    def bloco_operation_flow_rate() -> str:
        dp_high = dados.get("dp_high", {})
        dp_low  = dados.get("dp_low",  {})
        max_flow = dp_high.get("vazao_max", "NI")
        min_flow = dp_low.get("vazao_min") or dp_high.get("vazao_min", "NI")
        return (
            f'  <OperationFlowRate>\n'
            f'    <MaxFlowRate>{max_flow}</MaxFlowRate>\n'
            f'    <MinFlowRate>{min_flow}</MinFlowRate>\n'
            f'  </OperationFlowRate>\n'
        )

    def bloco_pd(range_: str, chave: str) -> str:
        if chave not in dados:
            return ""
        d = dados[chave]
        return (
            f'  <DifferentialPressureTransmitter range="{range_}">\n'
            f'    <Certificate>{d.get("tag", "NI")}</Certificate>\n'
            f'    <CertificateNumber>{d.get("certificado", "NI")}</CertificateNumber>\n'
            f'    <MaxFlowRate>{d.get("vazao_max", "NI")}</MaxFlowRate>\n'
            f'    <MinFlowRate>{d.get("vazao_min", "NI")}</MinFlowRate>\n'
            f'  </DifferentialPressureTransmitter>\n'
        )

    xml = (
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<UncertaintyReport company="ODS ENERGY SOLUTIONS">\n\n'
        f'  <CINumber>{numero_ci}</CINumber>\n'
        f'  <Tag>NI</Tag>\n'
        f'  <SystemName>NI</SystemName>\n\n'
        f'  <GasMeterRun>\n'
        f'    <Certificate>{v("trecho", "tag")}</Certificate>\n'
        f'    <InternalDiameter>{v("trecho", "diametro")}</InternalDiameter>\n'
        f'    <CertificateNumber>{v("trecho", "certificado")}</CertificateNumber>\n'
        f'  </GasMeterRun>\n\n'
        f'  <OrificePlace>\n'
        f'    <Certificate>{v("placa", "tag")}</Certificate>\n'
        f'    <DiameterAt20C>{v("placa", "diametro")}</DiameterAt20C>\n'
        f'    <CertificateNumber>{v("placa", "certificado")}</CertificateNumber>\n'
        f'  </OrificePlace>\n\n'

        + bloco_pd("high", "dp_high")
        + ('\n' if "dp_low" in dados else '')
        + bloco_pd("low",  "dp_low")
        + f'\n  <PressureTransmitter>\n'
        + f'    <Certificate>{v("pressao_estatica", "tag")}</Certificate>\n'
        + f'    <CertificateNumber>{v("pressao_estatica", "certificado")}</CertificateNumber>\n'
        + f'  </PressureTransmitter>\n\n'
        + f'  <TemperatureTransmitter>\n'
        + f'    <Certificate>{v("termometro", "tag")}</Certificate>\n'
        + f'    <CertificateNumber>{v("termometro", "certificado")}</CertificateNumber>\n'
        + f'  </TemperatureTransmitter>\n\n'
        + f'  <TemperatureSensor>\n'
        + f'    <Certificate>NI</Certificate>\n'
        + f'    <CertificateNumber>NI</CertificateNumber>\n'
        + f'  </TemperatureSensor>\n\n'
        + bloco_operation_flow_rate()
        + '</UncertaintyReport>'
    )
    return xml


caminho_ci  = 'uc//CI-1300.0000-6252-813-O2C-027.pdf'
uc_completo = extrair_texto(caminho_ci)
numero_rel  = extrair_numero_relatorio(uc_completo)
tabelas     = extrair_tabelas_uc(caminho_ci)
fluxos      = extrair_fluxos_dp(uc_completo)
dados       = organizar_dados_uc(tabelas, fluxos)
xml         = gerar_xml_uc(numero_rel or "NI", dados)

caminho_xml = os.path.splitext(caminho_ci)[0] + ".xml"
with open(caminho_xml, "w", encoding="utf-8") as f:
    f.write(xml)