import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

from xml_model.xml_petro_generator import (
    data_xs_date,
    criar_identificacao_certificado,
    criar_laboratorio,
    criar_cliente,
    sig_ex,
    criar_condicoes_ambientais,
    criar_identificacao_padroes,
    criar_procedimento,
    observacoes,
)


def _aprovado(valor):
    """Normaliza resultado do ER para 'Sim' / 'Não' / valor original."""
    if not valor:
        return "NÃO ENCONTRADO"
    v = valor.strip()
    if v == "Sim":
        return "Sim"
    if v == "Não":
        return "Não"
    return v


def criar_trecho_reto(dados, dados_er, root):
    """Cria o bloco TRECHO_RETO com os dados do DIM report e do Evaluation Report.
    Creates the TRECHO_RETO block from DIM report and Evaluation Report data."""

    er = dados_er or {}
    d_er = er.get("d_er") or {}

    bloco = ET.SubElement(root, "TRECHO_RETO")

    ET.SubElement(bloco, "DATA_INSPECAO").text = data_xs_date(dados.get("data_calibracao", ""))
    # ET.SubElement(bloco, "NUMERO_EVALUATION").text = er.get("Numero_Evaluation", "")
    # ET.SubElement(bloco, "TAG").text = dados.get("tag", "")
    # ET.SubElement(bloco, "NUM_SERIE").text = dados.get("sn_inst", "")
    # ET.SubElement(bloco, "MATERIAL").text = dados.get("material", "")
    # ET.SubElement(bloco, "COEF_DILATACAO", UNIDADE_ENG="mm/mm°C").text = dados.get("coef", "")
    # ET.SubElement(bloco, "NORMA_AVALIACAO").text = dados.get("norma", "ISO 5167-2:2022")
    # ET.SubElement(bloco, "CONDICIONADOR_FLUXO").text = dados.get("condicionador_fluxo", "Nenhum")

    # # Diâmetro interno médio D (Item 6.4.2 do ER)
    # bloco_d = ET.SubElement(bloco, "DIAMETRO_INTERNO_MEDIO")
    # ET.SubElement(bloco_d, "VALOR", UNIDADE_ENG="mm").text = d_er.get("valor", "")
    # ET.SubElement(bloco_d, "INCERTEZA_EXP", UNIDADE_ENG="mm").text = d_er.get("incerteza", "")

    # # Componentes (Porta Placa, Trecho Montante, Trecho Jusante)
    # bloco_comp = ET.SubElement(bloco, "COMPONENTES")
    # for comp in dados.get("componentes", []):
    #     el = ET.SubElement(bloco_comp, "COMPONENTE", TIPO=comp.get("tipo", ""))
    #     ET.SubElement(el, "TAG").text = comp.get("tag", "")
    #     ET.SubElement(el, "NUM_SERIE").text = comp.get("sn", "")

    # # Avaliação Montante
    # bloco_mont = ET.SubElement(bloco, "AVALIACAO_MONTANTE")
    # ET.SubElement(bloco_mont, "CILINDRICIDADE_ALEM_10D").text = _aprovado(er.get("Cil_Montante_Alem_10D"))
    # ET.SubElement(bloco_mont, "CILINDRICIDADE_2_10D").text = _aprovado(er.get("Cil_Montante_2_10D"))
    # ET.SubElement(bloco_mont, "RUGOSIDADE_2_10D").text = _aprovado(er.get("Rug_Montante_2_10D"))
    # ET.SubElement(bloco_mont, "COMPRIMENTO").text = _aprovado(er.get("Comp_Montante"))

    # # Avaliação Jusante
    # bloco_jus = ET.SubElement(bloco, "AVALIACAO_JUSANTE")
    # ET.SubElement(bloco_jus, "CILINDRICIDADE").text = _aprovado(er.get("Cil_Jusante"))
    # ET.SubElement(bloco_jus, "RUGOSIDADE").text = _aprovado(er.get("Rug_Jusante"))
    # ET.SubElement(bloco_jus, "COMPRIMENTO_TOMADA_TEMPERATURA").text = _aprovado(er.get("Comp_Tomada_Temp"))
    # ET.SubElement(bloco_jus, "COMPRIMENTO_ACIDENTE").text = _aprovado(er.get("Comp_Acidente_Jusante"))

    # # Avaliação Porta Placa (0-2D)
    # bloco_pp = ET.SubElement(bloco, "AVALIACAO_PORTA_PLACA")
    # ET.SubElement(bloco_pp, "CILINDRICIDADE_0_2D").text = _aprovado(er.get("Diametro_D"))
    # ET.SubElement(bloco_pp, "RUGOSIDADE_0_2D").text = _aprovado(er.get("Rug_0_2D"))


def gerar_xml_certificado_tr(informacoes, dados_er, caminho_saida):
    """Gera o XML de inspeção do Trecho Reto (Gas Meter Run) e salva em caminho_saida.
    Generates the Gas Meter Run inspection XML and saves it to caminho_saida."""

    NAMESPACE = "http://Petrobras/Medicao/Calibracao"
    ET.register_namespace("cal", NAMESPACE)

    root = ET.Element(f"{{{NAMESPACE}}}CERTIFICADO_INSPECAO_TRECHO_RETO")

    criar_identificacao_certificado(root, informacoes)
    root.append(criar_laboratorio())
    root.append(criar_cliente(informacoes))
    sig_ex(root, informacoes)
    root.append(criar_condicoes_ambientais(informacoes))
    root.append(criar_identificacao_padroes(informacoes))
    root.append(criar_procedimento(informacoes))
    root.append(observacoes())
    criar_trecho_reto(informacoes, dados_er, root)

    xml_str = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "wb") as f:
        f.write(pretty_xml)

    print(f"[TR] XML gerado: {caminho_saida}")
    return caminho_saida
