import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
from datetime import datetime

from xml_table_extractor import processar_pdf
from pdf.parser_certificados import extrair_campos
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado




# =====================================================
# UTIL – CAMINHO DO XML
# =====================================================

def gerar_caminho_xml(caminho_pdf):
    pasta = os.path.dirname(caminho_pdf)
    nome = os.path.splitext(os.path.basename(caminho_pdf))[0]
    return os.path.join(pasta, f"{nome}.xml")

def data_xs_date(data_str):
    if not data_str:
        return ""
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""

# =====================================================
# REGRA DE UNIDADE
# =====================================================

def definir_unidade_eng(categoria):
    categorias_ma = [
        "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA",
        "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA",
    ]
    return "mA" if categoria in categorias_ma else "kPa"


def obter_procedimento_por_categoria(categoria_instrumento):
    if not categoria_instrumento:
        return None

    categoria_norm = categoria_instrumento.lower()

    for item in MAPA_PROCEDIMENTOS:
        for cat in item["categorias"]:
            if cat.lower() in categoria_norm:
                return {
                    "procedimento": item["procedimento"],
                    "descricao": item["descricao"],
                    "observacao": item["observacao"]
                }

    return None


# =====================================================
# BLOCOS BÁSICOS
# =====================================================

def criar_identificacao_certificado(dados=None):
    bloco = ET.Element("IDENTIFICACAO_CERTIFICADO")
    
    ET.SubElement(bloco, "NUMERO_CERTIFICADO").text = (
        normalizar_certificado(dados.get("certificado", "")) if dados else ""
    )
    ET.SubElement(bloco, "NUMERO_CERTIFICADO_REVISADO")
    ET.SubElement(bloco, "DATA_EMISSAO").text = (
        data_xs_date(dados.get("report_date", "")) if dados else ""
    )
    ET.SubElement(bloco, "DATA_CALIBRACAO").text = (
        data_xs_date(dados.get("data", "")) if dados else ""
    )
    return bloco


def criar_laboratorio():
    bloco = ET.Element("LABORATORIO")
    ET.SubElement(bloco, "NOME").text = "ODS Lab"
    ET.SubElement(bloco, "ENDERECO").text = "Av. Pierre Simon de Laplace, 830 - Bloco 1 - Techno Park, Campinas - SP, 13069-320"
    ET.SubElement(bloco, "ACREDITACAO").text = "CAL 0746"
    return bloco


def criar_cliente(dados=None):
    bloco = ET.Element("CLIENTE")
    ET.SubElement(bloco, "NOME").text = dados.get("cliente", "") if dados else ""
    ET.SubElement(bloco, "ENDERECO").text = dados.get("endereco_cliente", "") if dados else ""
    ET.SubElement(bloco, "UNIDADE_OPERACIONAL").text = dados.get("local", "") if dados else ""
    return bloco

# FALTA COLETAR SIGNATÁRIO e EXECUTOR

def criar_condicoes_ambientais(dados=None):
    bloco = ET.Element("CONDICOES_AMBIENTAIS")
    cond = dados.get("cond_amb", {}) if dados else {}
    temp = ET.SubElement(bloco, "TEMPERATURA")
    temp_valor = ET.SubElement(temp, "VALOR")
    temp_valor.text = str(cond.get("temperatura_ambiente", "NI"))
    temp_valor.set("UNIDADE_ENG", "°C")
    temp_var = ET.SubElement(temp, "VARIABILIDADE")
    temp_var.text = "NI"
    temp_var.set("UNIDADE_ENG", "NI")

    pressao = ET.SubElement(bloco, "PRESSAO_ATMOSFERICA")
    pres_valor = ET.SubElement(pressao, "VALOR")
    pres_valor.text = "NI"
    pres_valor.set("UNIDADE_ENG", "NI")
    pres_var = ET.SubElement(pressao, "VARIABILIDADE")
    pres_var.text = "NI"
    pres_var.set("UNIDADE_ENG", "NI")

    umid = ET.SubElement(bloco, "UMIDADE_RELATIVA")
    umid_valor = ET.SubElement(umid, "VALOR")
    umid_valor.text = str(cond.get("umidade_ambiente", "NI"))
    umid_valor.set("UNIDADE_ENG", "%")

    umid_var = ET.SubElement(umid, "VARIABILIDADE")
    umid_var.text = "NI"
    umid_var.set("UNIDADE_ENG", "NI")

    return bloco


MAPA_PROCEDIMENTOS = [{
    "categorias": [ "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA", "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA" ],
    "procedimento": "7.2 TM-005  Pressure Transmitters",
    "descricao": "A calibração consistiu na medição de quatro vezes cada ponto de pressão (dois ciclos de carga e descaga) comparando com um padrão, na sua posição de trabalho e utilizando o procedimento 7.2 TM-005  Pressure Transmitters"
},
{
    "categorias": [ "MANOMETRO ANALÓGICO", "MANOMETRO DIGITAL", "MANOMETRO DIGITAL ABSOLUTO", "MANOMETRO DIFERENCIAL ANALÓGICO", "MANOMETRO DIFERENCIAL DIGITAL" ],
    "procedimento": "7.2 TM-002 Manometers",
    "descricao": "A calibração consistiu na medição de quatro vezes cada ponto de pressão (dois ciclos de carga e descaga) comparando com um padrão, na sua posição de trabalho e utilizando o procedimento 7.2 TM-002 Manometers"
},
{
    "categorias": ["TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA"],
    "procedimento": "7.2 TM-004 Temperature Transmitter",
    "descricao": "A calibração consistiu na medição de três vezes cada ponto calibrado em um ciclo de subida e outro de descida, conforme o procedimento 7.2 TM-004 Temperature Transmitter"
},
{
    "categorias": [ "TERMÔMETRO ANALÓGICO", "TERMÔMETRO DIGITAL", ],
    "procedimento": "7.2 TM-001 Temperature Meter with Sensor",
    "descricao": "O sensor do instrumento e o sensor padrão de referência foram introduzidos no banho térmico e a calibração foi realizada através da comparação direta entre as indicações do instrumento e do padrão de referência. As medições foram realizadas após a estabilização, confirmada pelas leituras do padrão em 3 séries de medições alternadas, com intervalos de 1 minuto. A calibração foi realizado conforme procedimento 7.2 TM-001 Temperature Meter with Sensor, , no qual esta de acordo aos requisitos da norma NBR 14610"
},
{
    "categorias": [ "TERMORRESISTÊNCIA PT-100 - 2 FIOS", "TERMORRESISTÊNCIA PT-100 - 3 FIOS", "TERMORRESISTÊNCIA PT-100 - 4 FIOS", ],
    "procedimento": "7.2 TM-006 Thermoresistances",
    "descricao": "O sensor do instrumento e o sensor padrão de referência foram introduzidos no bloco seco e a calibração foi realizada através da comparação direta entre as indicações do instrumento e do padrão de referência. As medições foram realizadas após a estabilização, confirmada pelas leituras do padrão em 3 séries de medições alternadas. A calibração foi realizado conforme procedimento 7.2 TM-006 Thermoresistances, no qual esta de acordo aos requisitos da norma  NBR 13772"
}]


def criar_procedimento(dados=None):
    bloco = ET.Element("PROCEDIMENTO_CALIBRACAO")
    ET.SubElement(bloco, "IDENTIFICADOR").text = dados.get("procedimento", "").get("procedimento", "") if dados else ""
    ET.SubElement(bloco, "DESCRICAO").text = dados.get("procedimento", "").get("descricao", "") if dados else ""
    return bloco


# =====================================================
# BLOCO – IDENTIFICAÇÃO DO INSTRUMENTO (MANTIDO)
# =====================================================

def criar_identificacao_instrumento():
    bloco = ET.Element("IDENTIFICACAO_INSTRUMENTO")
    ET.SubElement(bloco, "TIPO_INSTRUMENTO")
    ET.SubElement(bloco, "FABRICANTE")
    ET.SubElement(bloco, "MODELO")
    ET.SubElement(bloco, "NUMERO_SERIE")
    ET.SubElement(bloco, "TAG")
    ET.SubElement(bloco, "FAIXA")
    ET.SubElement(bloco, "RESOLUCAO")
    ET.SubElement(bloco, "UNIDADE_ENG")
    return bloco


# =====================================================
# PADRÕES (MANTIDO)
# =====================================================

def criar_identificacao_padroes(dados=None):
    bloco = ET.Element("PADROES")

    padroes = dados.get("padroes_utilizados", []) if dados else []

    for p in padroes:
        padrao = ET.SubElement(bloco, "PADRAO")

        ET.SubElement(padrao, "DESCRICAO").text = p.get("tipo", "")

        ET.SubElement(padrao, "FABRICANTE").text

        ET.SubElement(padrao, "MODELO").text 

        ET.SubElement(padrao, "IDENTIFICADOR").text = p.get("identificacao", "")

        cert = ET.SubElement(padrao, "CERTIFICADO_PADRAO")

        ET.SubElement(cert, "LABORATORIO").text = "RBC" # Essa informação não está no PDF

        ET.SubElement(cert, "NUMERO_CERTIFICADO").text = p.get("certificado", "")

        ET.SubElement(cert, "DATA_CALIBRACAO").text = p.get("data_calibracao") # Não obrigatório

        ET.SubElement(cert, "VALIDADE").text = p.get("validade", "") # Confirmar a data correta no certificado só está mês 
    return bloco



# =====================================================
# CALIBRAÇÃO – PONTOS (MANTIDO)
# =====================================================

def gerar_pontos_calibracao(resultados, unidade_eng):
    pontos = ET.Element("PONTOS_DE_CALIBRACAO")

    for linha in resultados:
        ponto = ET.SubElement(pontos, "PONTO_DE_CALIBRACAO")

        ET.SubElement(ponto, "VALOR_REFERENCIA", UNIDADE_ENG=unidade_eng).text = str(linha.get("kPa_ref", ""))

        for idx, ciclo in enumerate(
            [("p_cic_cresc", "p_cic_decres"), ("s_cic_cres", "s_cic_decrs")],
            start=1
        ):
            c = ET.SubElement(ponto, f"CICLO_{idx}")
            ET.SubElement(c, "VALOR_INDICADO_ASCENDENTE", UNIDADE_ENG=unidade_eng).text = str(linha.get(ciclo[0], ""))
            ET.SubElement(c, "VALOR_INDICADO_DESCENDENTE", UNIDADE_ENG=unidade_eng).text = str(linha.get(ciclo[1], ""))

        ET.SubElement(ponto, "MEDIA", UNIDADE_ENG=unidade_eng).text = str(linha.get("media", ""))

    return pontos


# =====================================================
# RESULTADOS (MANTIDO)
# =====================================================

def gerar_resultados_xml(resultados, unidade_eng):
    bloco = ET.Element("RESULTADOS_CALIBRACAO")

    for linha in resultados:
        ponto = ET.SubElement(bloco, "RESULTADO")

        ET.SubElement(ponto, "ERRO", UNIDADE_ENG=unidade_eng).text = str(linha.get("tendencia_ma_kpa", ""))

        inc = ET.SubElement(
            ponto,
            "INCERTEZA",
            UNIDADE_ENG=unidade_eng,
            K=str(linha.get("k", "")),
            GRAU_LIBERDADE=str(linha.get("veff", ""))
        )
        inc.text = str(linha.get("incerteza_ma_kpa", ""))

    return bloco


# =====================================================
# BLOCOS FINAIS
# =====================================================

def criar_avaliacao_conformidade():
    bloco = ET.Element("AVALIACAO_CONFORMIDADE")
    ET.SubElement(bloco, "CRITERIO")
    ET.SubElement(bloco, "RESULTADO")
    return bloco


def criar_ajuste():
    bloco = ET.Element("AJUSTE")
    ET.SubElement(bloco, "REALIZADO")
    ET.SubElement(bloco, "DESCRICAO")
    return bloco


def criar_cmc():
    bloco = ET.Element("CMC")
    ET.SubElement(bloco, "EXPRESSAO")
    ET.SubElement(bloco, "UNIDADE")
    return bloco


def criar_rastreabilidade():
    bloco = ET.Element("RASTREABILIDADE")
    ET.SubElement(bloco, "DESCRICAO")
    return bloco


def criar_assinaturas():
    bloco = ET.Element("ASSINATURAS")
    ET.SubElement(bloco, "EXECUTANTE")
    ET.SubElement(bloco, "RESPONSAVEL_TECNICO")
    return bloco


# =====================================================
# XML COMPLETO
# =====================================================

def gerar_xml_certificado_pressao(informacoes: dict, pontos: list) -> ET.Element:
    root = ET.Element("CERTIFICADO_CALIBRACAO_PRESSAO")

    root.append(criar_identificacao_certificado(informacoes))
    root.append(criar_laboratorio())
    root.append(criar_cliente(informacoes))
    root.append(criar_procedimento(informacoes))
    root.append(criar_identificacao_instrumento())
    root.append(criar_identificacao_padroes(informacoes))
    root.append(criar_condicoes_ambientais(informacoes))

    calibracoes = ET.SubElement(root, "CALIBRACOES")
    unidade_eng = definir_unidade_eng(pontos.get("categoria", ""))

    cal_as_found = ET.SubElement(calibracoes, "CALIBRACAO_AS_FOUND")
    if pontos.get("tabela1") == "AS FOUND":
        cal_as_found.append(gerar_pontos_calibracao(pontos.get("results1", []), unidade_eng))

    cal_as_left = ET.SubElement(calibracoes, "CALIBRACAO_AS_LEFT")
    if pontos.get("tabela2") == "AS LEFT":
        cal_as_left.append(gerar_pontos_calibracao(pontos.get("results2", []), unidade_eng))

    resultados = []
    for i in range(1, 10):
        if pontos.get(f"tabela{i}") == "RESULTADOS":
            resultados = pontos.get(f"results{i}", [])

    calibracoes.append(gerar_resultados_xml(resultados, unidade_eng))

    root.append(criar_avaliacao_conformidade())
    root.append(criar_ajuste())
    root.append(criar_cmc())
    root.append(criar_rastreabilidade())
    root.append(criar_assinaturas())

    return root


# =====================================================
# EXECUÇÃO
# =====================================================

if __name__ == "__main__":

    caminho_pdf = "xml_model\\24-ODS-95-PRE-974_27PT2001.pdf"

    infomacoes = extrair_campos(extrair_texto("xml_model\\24-ODS-95-PRE-974_27PT2001.pdf"))
    print(infomacoes)
    dados_tabela = processar_pdf(caminho_pdf)
    xml_root = gerar_xml_certificado_pressao(infomacoes, dados_tabela)

    xml_bruto = ET.tostring(xml_root, encoding="utf-8")
    xml_formatado = minidom.parseString(xml_bruto).toprettyxml(indent="  ", encoding="utf-8")

    caminho_xml = gerar_caminho_xml(caminho_pdf)
    with open(caminho_xml, "wb") as f:
        f.write(xml_formatado)

    print("XML gerado com sucesso em:")
    print(caminho_xml)