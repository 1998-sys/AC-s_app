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
    return _MATERIAL_MAP.get(valor.strip().lower(), valor)



def criar_trecho_reto(dados, dados_dim, root):
    """Cria o bloco TRECHO_RETO com os dados do DIM report.
    Creates the TRECHO_RETO block from DIM report data."""

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
    demais = ET.SubElement(root, "DEMAIS_COMPONENTES")
    for c in informacoes.get("componentes", []):
        comp = ET.SubElement(demais, "COMPONENTE")
        ET.SubElement(comp, "NUM_SERIE").text = c.get("sn",   "")
        ET.SubElement(comp, "TIPO").text      = c.get("tipo", "")

def gerar_xml_certificado_tr(informacoes, dados_dim, caminho_saida):
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
    criar_trecho_reto(informacoes, dados_dim, root)
    demais_componentes(informacoes, root)

    salvar_xml_bonito(root, caminho_saida)

    return caminho_saida
