import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

from xml_table_extractor import processar_pdf


# =====================================================
# UTIL – CAMINHO DO XML NA MESMA PASTA DO PDF
# =====================================================

def gerar_caminho_xml(caminho_pdf):
    pasta = os.path.dirname(caminho_pdf)
    nome = os.path.splitext(os.path.basename(caminho_pdf))[0]
    return os.path.join(pasta, f"{nome}.xml")


# =====================================================
# REGRA DE UNIDADE CONFORME CATEGORIA
# =====================================================

def definir_unidade_eng(categoria):
    categorias_ma = [
        "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA",
        "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA",
    ]
    return "mA" if categoria in categorias_ma else "kPa"


# =====================================================
# BLOCO – IDENTIFICAÇÃO DO INSTRUMENTO
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
# BLOCO – IDENTIFICAÇÃO DOS PADRÕES
# =====================================================

def criar_identificacao_padroes():
    bloco = ET.Element("IDENTIFICACAO_PADROES")

    padrao = ET.SubElement(bloco, "PADRAO")
    ET.SubElement(padrao, "DESCRICAO")
    ET.SubElement(padrao, "NUMERO_SERIE")
    ET.SubElement(padrao, "CERTIFICADO")
    ET.SubElement(padrao, "VALIDADE")
    ET.SubElement(padrao, "RASTREAMENTO")

    return bloco


# =====================================================
# BLOCO – CONDIÇÕES AMBIENTAIS
# =====================================================

def criar_condicoes_ambientais():
    bloco = ET.Element("CONDICOES_AMBIENTAIS")

    ET.SubElement(bloco, "TEMPERATURA")
    ET.SubElement(bloco, "UMIDADE_RELATIVA")
    ET.SubElement(bloco, "PRESSAO_ATMOSFERICA")

    return bloco


# =====================================================
# PONTOS DE CALIBRAÇÃO
# =====================================================

def gerar_pontos_calibracao(resultados, unidade_eng):
    pontos = ET.Element("PONTOS_DE_CALIBRACAO")

    for linha in resultados:
        ponto = ET.SubElement(pontos, "PONTO_DE_CALIBRACAO")

        ET.SubElement(
            ponto,
            "VALOR_REFERENCIA",
            UNIDADE_ENG=unidade_eng
        ).text = "" if linha.get("kPa_ref") is None else str(linha.get("kPa_ref"))

        ciclo1 = ET.SubElement(ponto, "CICLO_1")
        ET.SubElement(
            ciclo1,
            "VALOR_INDICADO_ASCENDENTE",
            UNIDADE_ENG=unidade_eng
        ).text = "" if linha.get("p_cic_cresc") is None else str(linha.get("p_cic_cresc"))

        ET.SubElement(
            ciclo1,
            "VALOR_INDICADO_DESCENDENTE",
            UNIDADE_ENG=unidade_eng
        ).text = "" if linha.get("p_cic_decres") is None else str(linha.get("p_cic_decres"))

        ciclo2 = ET.SubElement(ponto, "CICLO_2")
        ET.SubElement(
            ciclo2,
            "VALOR_INDICADO_ASCENDENTE",
            UNIDADE_ENG=unidade_eng
        ).text = "" if linha.get("s_cic_cres") is None else str(linha.get("s_cic_cres"))

        ET.SubElement(
            ciclo2,
            "VALOR_INDICADO_DESCENDENTE",
            UNIDADE_ENG=unidade_eng
        ).text = "" if linha.get("s_cic_decrs") is None else str(linha.get("s_cic_decrs"))

        ET.SubElement(
            ponto,
            "MEDIA",
            UNIDADE_ENG=unidade_eng
        ).text = "" if linha.get("media") is None else str(linha.get("media"))

    return pontos


# =====================================================
# RESULTADOS – ERRO / INCERTEZA / K / GRAU DE LIBERDADE
# =====================================================

def gerar_resultados_xml(resultados, unidade_eng):
    bloco = ET.Element("RESULTADOS_CALIBRACAO")

    for linha in resultados:
        ponto = ET.SubElement(bloco, "RESULTADO")

        ET.SubElement(
            ponto,
            "ERRO",
            UNIDADE_ENG=unidade_eng
        ).text = "" if linha.get("tendencia_ma_kpa") is None else str(linha.get("tendencia_ma_kpa"))

        inc = ET.SubElement(
            ponto,
            "INCERTEZA",
            UNIDADE_ENG=unidade_eng,
            K="" if linha.get("k") is None else str(linha.get("k")),
            GRAU_LIBERDADE="" if linha.get("veff") is None else str(linha.get("veff"))
        )
        inc.text = "" if linha.get("incerteza_ma_kpa") is None else str(linha.get("incerteza_ma_kpa"))

    return bloco


# =====================================================
# LOCALIZA RESULTADOS (DINÂMICO)
# =====================================================

def obter_resultados(dados):
    for i in range(1, 10):
        if dados.get(f"tabela{i}") == "RESULTADOS":
            return dados.get(f"results{i}", [])
    return []


# =====================================================
# XML COMPLETO DO CERTIFICADO (ESTRUTURA TOTAL)
# =====================================================

def gerar_xml_certificado_pressao(dados):
    root = ET.Element("CERTIFICADO_CALIBRACAO_PRESSAO")

    root.append(criar_identificacao_instrumento())
    root.append(criar_identificacao_padroes())
    root.append(criar_condicoes_ambientais())

    calibracoes = ET.SubElement(root, "CALIBRACOES")
    unidade_eng = definir_unidade_eng(dados.get("categoria", ""))

    # CALIBRAÇÃO AS FOUND – SEMPRE EXISTE
    cal_as_found = ET.Element("CALIBRACAO_AS_FOUND")
    if dados.get("tabela1") == "AS FOUND":
        cal_as_found.append(
            gerar_pontos_calibracao(dados.get("results1", []), unidade_eng)
        )
    calibracoes.append(cal_as_found)

    # CALIBRAÇÃO AS LEFT – SEMPRE EXISTE
    cal_as_left = ET.Element("CALIBRACAO_AS_LEFT")
    if dados.get("tabela2") == "AS LEFT":
        cal_as_left.append(
            gerar_pontos_calibracao(dados.get("results2", []), unidade_eng)
        )
    calibracoes.append(cal_as_left)

    # RESULTADOS – SEMPRE EXISTE
    resultados = obter_resultados(dados)
    calibracoes.append(
        gerar_resultados_xml(resultados, unidade_eng)
    )

    return root


# =====================================================
# EXECUÇÃO
# =====================================================

if __name__ == "__main__":

    caminho_pdf = "xml_model\\25-ODS-53-PRE-494 - PIT-3115-51.pdf"

    dados = processar_pdf(caminho_pdf)
    xml_root = gerar_xml_certificado_pressao(dados)

    xml_bruto = ET.tostring(xml_root, encoding="utf-8")
    xml_formatado = minidom.parseString(xml_bruto).toprettyxml(
        indent="  ",
        encoding="utf-8"
    )

    caminho_xml = gerar_caminho_xml(caminho_pdf)
    with open(caminho_xml, "wb") as f:
        f.write(xml_formatado)

    print("XML gerado com sucesso em:")
    print(caminho_xml)
