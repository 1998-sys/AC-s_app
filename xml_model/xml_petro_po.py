import xml.etree.ElementTree as ET
import calendar
from xml.dom import minidom
import os
import sys
from datetime import datetime
from pathlib import Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pdf.extrator import extrair_texto
from pdf.parser_po import extrair_campos_po
from pdf.parser_po_ER import extrair_campos_er
from xml_model.xml_extractor_PO import extrair_valores_medidos
from xml_model.xml_petro_generator import (data_xs_date,criar_identificacao_certificado, criar_laboratorio,normalizar_categoria,
criar_cliente, sig_ex, criar_condicoes_ambientais, criar_identificacao_padroes, criar_procedimento, observacoes)


def criar_identificacao_po(dados, valores_medidos, valores_er, root):
    
    valores_d_interno = valores_er.get("valores_d_interno", {})
    valores_expessura = valores_er.get("Valores_Espessura", {})
    valores_expessura_furo = valores_er.get("Valores_Espessura_Furo", {})

    bloco_instr = ET.SubElement(root, "PLACA_ORIFICIO")
    ET.SubElement(bloco_instr,'DATA_INSPECAO').text = data_xs_date(dados.get("data_calibracao","")) if dados else ""
    ET.SubElement(bloco_instr,'NUM_SERIE').text = dados.get("sn_inst","") if dados else ""
    ET.SubElement(bloco_instr,'TAG').text = dados.get("tag","") if dados else ""
    ET.SubElement(bloco_instr,'MATERIAL').text = dados.get("material","") if dados else ""
    ET.SubElement(bloco_instr,'COEF_DILATACAO', UNIDADE_ENG="mm/mm°C").text = dados.get("coef","") if dados else ""
    ET.SubElement(bloco_instr,'NORMA_AVALIACAO').text = "ISO 5167-2:2022"
    ET.SubElement(bloco_instr,'DIAMETRO_TUBULACAO', UNIDADE_ENG="mm").text = dados.get("diametro_tubo","") if dados else ""
    bloco_d_orificio = ET.SubElement(bloco_instr,'DIAMETRO_ORIF_COND_REF')
    bloco_valor_medio = ET.SubElement(bloco_d_orificio,'VALOR_MEDIO')
    ET.SubElement(bloco_valor_medio, 'VALOR', UNIDADE_ENG=valores_medidos.get("d_int", {}).get("unidade", "") if valores_medidos else "").text =(
    str(valores_medidos.get("d_int", {}).get("media", 0)) if valores_medidos else "")
    ET.SubElement(bloco_valor_medio,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("d_int", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("d_int", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("d_int", {}).get("veff", "") if valores_medidos else "NI")).text =(
    str(valores_medidos.get("d_int", {}).get("incerteza", 0)) if valores_medidos else "")
    ET.SubElement(bloco_valor_medio,'APROVADO').text = valores_er.get("Diametro_Interno", "") if valores_er else ""
    for valor in valores_d_interno.values():
        ET.SubElement(
            bloco_d_orificio,
            'MEDIDA_INDIVIDUAL',
            UNIDADE_ENG='mm',
        ).text = valor
    ET.SubElement(bloco_instr,'BETA').text = valores_er.get("Beta", "") if valores_er else ""
    bloco_circularidade = ET.SubElement(bloco_instr,'CIRCULARIDADE_ORIF')
    ET.SubElement(bloco_circularidade, 'VALOR', UNIDADE_ENG="mm").text = str(valores_medidos.get("desv_circ", {}).get("media", "")) if valores_medidos else ""
    ET.SubElement(bloco_circularidade,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("desv_circ", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("desv_circ", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("desv_circ", {}).get("veff", "") if valores_medidos else "NI")).text = str(valores_medidos.get("desv_circ", {}).get("incerteza", "")) if valores_medidos else ""
    ET.SubElement(bloco_circularidade,'APROVADO').text = valores_er.get("Circularidade", "") if valores_er else ""
    bloco_espessura = ET.SubElement(bloco_instr,'ESPESSURA_ORIFICIO')
    bloco_valor_medio = ET.SubElement(bloco_espessura,'VALOR_MEDIO')
    ET.SubElement(bloco_valor_medio, 'VALOR', UNIDADE_ENG='mm').text = str(valores_medidos.get('comp_tr', {}).get('media', '')) if valores_medidos else ''
    ET.SubElement(bloco_valor_medio, 'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get('comp_tr', {}).get('unidade', '') if valores_medidos else '', K=str(valores_medidos.get('comp_tr', {}).get('k', 'NI') if valores_medidos else 'NI'), GRAU_LIBERDADE=str(valores_medidos.get('comp_tr', {}).get('veff', 'NI') if valores_medidos else 'NI')).text = str(valores_medidos.get('comp_tr', {}).get('incerteza', '')) if valores_medidos else ''
    ET.SubElement(bloco_valor_medio, 'APROVADO').text = valores_er.get("Espessura_Furo", "") if valores_er else ""
    for valor in valores_expessura_furo.values():
        ET.SubElement(
            bloco_espessura,
            'MEDIDA_INDIVIDUAL',
            UNIDADE_ENG='mm',
        ).text = str(valor)
    bloco_exp_placa = ET.SubElement(bloco_instr,'ESPESSURA_PLACA')
    bloco_valor_medio = ET.SubElement(bloco_exp_placa,'VALOR_MEDIO')
    ET.SubElement(bloco_valor_medio,'VALOR', UNIDADE_ENG="mm").text = str(valores_medidos.get("exp_po", {}).get("media", "")) if valores_medidos else ""
    ET.SubElement(bloco_valor_medio,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("exp_po", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("exp_po", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("exp_po", {}).get("veff", "") if valores_medidos else "NI")).text = str(valores_medidos.get("exp_po", {}).get("incerteza", "")) if valores_medidos else ""
    ET.SubElement(bloco_valor_medio,'APROVADO').text = valores_er.get("Espessura", "") if valores_er else ""
    for valor in valores_expessura.values():
        ET.SubElement(
            bloco_exp_placa,
            'MEDIDA_INDIVIDUAL',
            UNIDADE_ENG='mm',
        ).text = str(valor)
    bloco_rug_mont = ET.SubElement(bloco_instr,'RUGOSIDADE_MONTANTE')
    ET.SubElement(bloco_rug_mont,'VALOR', UNIDADE_ENG="µm").text = str(valores_medidos.get("rug_mont", {}).get("media", "")) if valores_medidos else ""
    ET.SubElement(bloco_rug_mont,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("rug_mont", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("rug_mont", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("rug_mont", {}).get("veff", "") if valores_medidos else "NI")).text = str(valores_medidos.get("rug_mont", {}).get("incerteza", "")) if valores_medidos else ""
    ET.SubElement(bloco_rug_mont,'APROVADO').text = valores_er.get("Rugosidade", "") if valores_er else ""
    bloco_rug_jus = ET.SubElement(bloco_instr,'RUGOSIDADE_JUSANTE')
    ET.SubElement(bloco_rug_jus,'VALOR', UNIDADE_ENG="µm").text = str(valores_medidos.get("rug_jus", {}).get("media", "")) if valores_medidos else ""
    ET.SubElement(bloco_rug_jus,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("rug_jus", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("rug_jus", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("rug_jus", {}).get("veff", "") if valores_medidos else "NI")).text = str(valores_medidos.get("rug_jus", {}).get("incerteza", "")) if valores_medidos else ""
    ET.SubElement(bloco_rug_jus,'APROVADO').text = valores_er.get("Rugosidade", "") if valores_er else ""
    bloco_planeza = ET.SubElement(bloco_instr,'PLANEZA_MONTANTE')
    ET.SubElement(bloco_planeza,'VALOR', UNIDADE_ENG="mm").text = str(valores_medidos.get("desv_planeza", {}).get("media", "")) if valores_medidos else ""
    ET.SubElement(bloco_planeza,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("desv_planeza", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("desv_planeza", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("desv_planeza", {}).get("veff", "") if valores_medidos else "NI")).text = str(valores_medidos.get("desv_planeza", {}).get("incerteza", "")) if valores_medidos else ""
    ET.SubElement(bloco_planeza,'APROVADO').text = valores_er.get("Planeza", "") if valores_er else ""
    bloco_ang_chanf = ET.SubElement(bloco_instr,'ANGULO_DE_CHANFRO')
    ET.SubElement(bloco_ang_chanf,'VALOR', UNIDADE_ENG="°").text = str(valores_medidos.get("ang_chanf", {}).get("media", "")) if valores_medidos else ""
    ET.SubElement(bloco_ang_chanf,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("ang_chanf", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("ang_chanf", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("ang_chanf", {}).get("veff", "") if valores_medidos else "NI")).text = str(valores_medidos.get("ang_chanf", {}).get("incerteza", "")) if valores_medidos else ""
    ET.SubElement(bloco_ang_chanf,'APROVADO').text = valores_er.get("Angulo_Chanfro", "") if valores_er else ""
    bloco_ang_gh = ET.SubElement(bloco_instr,'ANGULO_BORDA_G')
    ET.SubElement(bloco_ang_gh,'VALOR', UNIDADE_ENG="°").text = str(valores_medidos.get("ang_of_mont", {}).get('media', "")) if valores_er else ""
    ET.SubElement(bloco_ang_gh,'INCERTEZA_EXP', UNIDADE_ENG=valores_medidos.get("ang_of_mont", {}).get("unidade", "") if valores_medidos else "", K=str(valores_medidos.get("ang_of_mont", {}).get("k", "") if valores_medidos else "NI"), GRAU_LIBERDADE=str(valores_medidos.get("ang_of_mont", {}).get("veff", "") if valores_medidos else "NI")).text = str(valores_medidos.get("ang_mont", {}).get("incerteza", "")) if valores_medidos else ""
    ET.SubElement(bloco_ang_gh,'APROVADO').text = "NI"
    bloco_escent = ET.SubElement(bloco_instr,'EXCENTRICIDADE')
    ET.SubElement(bloco_escent,'VALOR', UNIDADE_ENG="NI").text = "NI"
    ET.SubElement(bloco_escent,'INCERTEZA_EXP', UNIDADE_ENG="NI", K="NI", GRAU_LIBERDADE="NI").text = "NI"
    ET.SubElement(bloco_escent,'APROVADO').text = "NI"
    ET.SubElement(bloco_instr,'BORDA_G_SEM_DANOS').text = "NI"
    ET.SubElement(bloco_instr,'BORDA_G_AFIADA').text = "NI"
    


def gerar_xml_certificado_po(informacoes, valores_medidos, valores_er, caminho_saida):
    NAMESPACE = "http://Petrobras/Medicao/Calibracao"
    
    ET.register_namespace("cal", NAMESPACE)

    root = ET.Element(f"{{{NAMESPACE}}}CERTIFICADO_INSPECAO_PLACA_ORIFICIO")

    criar_identificacao_certificado(root, informacoes)
    root.append(criar_laboratorio())
    root.append(criar_cliente(informacoes))
    sig_ex(root, informacoes)
    root.append(criar_condicoes_ambientais(informacoes))
    root.append(criar_identificacao_padroes(informacoes))
    root.append(criar_procedimento(informacoes))
    root.append(observacoes())
    criar_identificacao_po(informacoes, valores_medidos, valores_er, root)



    xml_str = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "wb") as f:
        f.write(pretty_xml)

    return caminho_saida



