# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_petro_tr
# Created       : 25-04-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the Petrobras-schema straight run (gas meter run) inspection certificate XML from the DIM report dimensional data.
#                 Gera o XML de certificado de inspeção do trecho reto (gas meter run) no padrão Petrobras a partir dos dados dimensionais do relatório DIM.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import xml.etree.ElementTree as ET

from xml_model.xml_common import salvar_xml_bonito
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



_TIPO_COMPONENTE_MAP = {
    "porta_placa":                    "PORTA PLACA",
    "flange_de_orificio":             "FLANGE DE ORIFICIO",
    "meter_run_for_flare_ultrasonic": "TRECHO RETO PARA MEDIDOR DE FLARE ULTRASSÔNICO",
}

_MATERIAL_MAP = {
    "carbon steel":        "Aço Carbono",
    "galvanized steel":    "Aço Galvanizado",
    "stainless steel 316": "Aço Inox 316",
    "stainless steel":     "Aço Inox",
    "inox 316":            "Aço Inox 316",
    "inox":                "Aço Inox",
    "duplex":              "Duplex",
    "monel":               "Monel",
}

def _traduzir_material(valor):
    """Translates the material name (English) from the PDF to the Portuguese term used in the XML.

    Args:
        valor: material name as extracted from the PDF.

    Returns:
        str: corresponding Portuguese name, or `valor` itself (untranslated)
        if there is no match in _MATERIAL_MAP.
    """
    return _MATERIAL_MAP.get(valor.strip().lower(), valor)



def criar_trecho_reto(dados, dados_dim, root):
    """Creates the TRECHO_RETO block with the DIM report data.

    Args:
        dados: certificate data extracted from the PDF (calibration date,
            serial number, TAG, material, expansion coefficient, standard,
            pipe diameter, flow conditioner etc.).
        dados_dim: dimensional data extracted from the DIM report (see
            xml_extractor_TR.extrair_dados_dim_tr); uses the first section
            and the first parameter found for the reference diameter.
        root: root XML element where the TRECHO_RETO block will be attached.
    """

    dim = dados_dim or {}

    bloco = ET.SubElement(root, "TRECHO_RETO")

    ET.SubElement(bloco, "DATA_INSPECAO").text = data_xs_date(dados.get("data_calibracao", ""))
    ET.SubElement(bloco, "NUM_SERIE").text     = dados.get("sn_inst", "")
    ET.SubElement(bloco, "TAG").text           = dados.get("tag", "")
    tipo_raw = next(iter(dim), "")
    ET.SubElement(bloco, "TIPO_COMPONENTE").text = _TIPO_COMPONENTE_MAP.get(tipo_raw, tipo_raw.replace("_", " ").upper())
    ET.SubElement(bloco, "MATERIAL").text       = _traduzir_material(dados.get("material", ""))
    ET.SubElement(bloco, "COEF_DILATACAO", UNIDADE_ENG="mm/mm°C").text = str(dados.get("coef", ""))
    ET.SubElement(bloco, "NORMA_AVALIACAO").text         = dados.get("norma", "")
    ET.SubElement(bloco, "DIAMETRO_TUBULACAO", UNIDADE_ENG=dados.get("diametro_tubo_unidade", '"')).text = str(dados.get("diametro_tubo", ""))
    inner  = next(iter(dim.values()), {})
    d_ref  = next(iter(inner.values()), {})
    cref   = ET.SubElement(bloco, "DIAMETRO_TRECHO_COND_REF")
    ET.SubElement(cref, "VALOR",        UNIDADE_ENG=str(d_ref.get("unidade", "mm"))).text = str(d_ref.get("valor", ""))
    ET.SubElement(cref, "INCERTEZA_EXP", UNIDADE_ENG=str(d_ref.get("unidade", "mm")),
                                         K=str(d_ref.get("k", "")),
                                         GRAU_LIBERDADE=str(d_ref.get("veff", ""))).text  = str(d_ref.get("incerteza", ""))
    ET.SubElement(cref, "APROVADO").text = "Sim"
    ET.SubElement(bloco, "TIPO_CONDICIONADOR_FLUXO").text = dados.get("condicionador_fluxo", "")

def demais_componentes(informacoes, root):
    """Creates the DEMAIS_COMPONENTES block from the given component list.

    Args:
        informacoes: general certificate data; uses the "componentes" key
            (list of dicts with "sn" and "tipo").
        root: root XML element where the DEMAIS_COMPONENTES block will be attached.
    """
    demais = ET.SubElement(root, "DEMAIS_COMPONENTES")
    for c in informacoes.get("componentes", []):
        comp = ET.SubElement(demais, "COMPONENTE")
        ET.SubElement(comp, "NUM_SERIE").text = c.get("sn",   "")
        ET.SubElement(comp, "TIPO").text      = c.get("tipo", "")

def gerar_xml_certificado_tr(informacoes, dados_dim, caminho_saida):
    """Generates the Petrobras-standard Straight Run (Gas Meter Run) inspection certificate XML and writes it to disk.

    Args:
        informacoes: general certificate data (identification, client,
            laboratory, environmental conditions, standards, procedure,
            other components).
        dados_dim: dimensional data extracted from the DIM report (see
            xml_extractor_TR.extrair_dados_dim_tr).
        caminho_saida: path of the output XML file.

    Returns:
        str: absolute path of the generated XML file.
    """

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
    criar_trecho_reto(informacoes, dados_dim, root)
    demais_componentes(informacoes, root)

    salvar_xml_bonito(root, caminho_saida)

    return caminho_saida
