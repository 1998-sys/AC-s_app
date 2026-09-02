# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_petro_generator
# Created       : 20-01-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the Petrobras-schema calibration certificate XML (temperature/pressure) from the extracted PDF data and calibration points.
#                 Gera o XML de certificado de calibração no padrão Petrobras (temperatura/pressão) a partir dos dados e pontos de calibração extraídos do PDF.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import xml.etree.ElementTree as ET
import calendar
import os
from datetime import datetime

from xml_model.xml_common import salvar_xml_bonito
from xml_model.xml_table_extractor import processar_pdf
from pdf.parser_certificados import extrair_campos
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado

mapeamento_eng = {
    "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA": 
    {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "mA", "incerteza": "kPa", "erro": "kPa", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
    "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA": 
    {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "mA", "incerteza": "kPa", "erro": "kPa", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
    "TERMORRESISTÊNCIA PT-100 - 4 FIOS":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TERMORRESISTÊNCIA PT-100 - 3 FIOS":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TERMORRESISTÊNCIA PT-100 - 2 FIOS":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TRANSMISSOR DE TEMPERATURA":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TERMÔMETRO DIGITAL":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TERMÔMETRO ANALÓGICO":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
     "MANOMETRO DIGITAL":
     {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "kPa", "incerteza": "kPa", "erro": "kPa", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
     "MANOMETRO ANALÓGICO" :
     {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "kPa", "incerteza": "kPa", "erro": "kPa", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
     "MANOMETRO DIGITAL ABSOLUTO":
    {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "kPa", "incerteza": "kPa", "erro": "kPa", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
     "MANOMETRO DIFERENCIAL DIGITAL":
    {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "kPa", "incerteza": "kPa", "erro": "kPa", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
     "MANOMETRO DIFERENCIAL ANALÓGICO":
    {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "kPa", "incerteza": "kPa", "erro": "kPa", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
    }
    
    

def normalizar_categoria(txt: str) -> str:
    """Normalizes the instrument category text for comparison: unifies hyphen/dash variants and uppercases it.

    Args:
        txt: raw category (e.g. extracted from the PDF), accepts None/empty.

    Returns:
        str: uppercase category, with surrounding spaces removed and the
        characters "‐", "–" and "—" converted to "-"; empty string if
        `txt` is empty/None.
    """
    if not txt:
        return ""

    substituicoes = {
        "‐": "-",  
        "–": "-",  
        "—": "-",  
        "-": "-",  
    }

    for k, v in substituicoes.items():
        txt = txt.replace(k, v)

    return txt.upper().strip()

def obter_unidade_eng(dados):
    """Gets the engineering units map (UNIDADE_ENG) corresponding to the instrument category.

    Searches `mapeamento_eng` for the first category key contained in the
    normalized text of `dados["categoria"]`.

    Args:
        dados: certificate data extracted from the PDF; uses the "categoria" key.

    Returns:
        dict: copy of the units map (faixa_cal, valor_referencia,
        valor_indicado, incerteza, erro, erro_fid, incert_global,
        histerese, rept) for the corresponding category; empty dict if the
        category has no mapping or `dados` has no category.
    """
    categoria = normalizar_categoria(dados.get("categoria", "").upper())

    if not categoria:
        return {}

    categoria = categoria.upper()

    for categoria_map, unidades in mapeamento_eng.items():
        if categoria_map in categoria:
            return unidades.copy()

    return {}


def gerar_caminho_xml(caminho_pdf):
    """Derives the output XML path from the source PDF path, keeping the same folder and name.

    Args:
        caminho_pdf: path of the certificate's PDF.

    Returns:
        str: path of the .xml file, in the same folder and with the same
        base name as `caminho_pdf`.
    """
    pasta = os.path.dirname(caminho_pdf)
    nome = os.path.splitext(os.path.basename(caminho_pdf))[0]
    return os.path.join(pasta, f"{nome}.xml")


def completar_data(data_mes_ano):
    """Completes a date given only as "month/year" with the last day of that month.

    Used for standards' validity, whose certificate usually only brings
    the expiration month/year.

    Args:
        data_mes_ano: date in "MM/YYYY" format (accepts None/empty).

    Returns:
        str | None: full date in "DD/MM/YYYY" format, using the last day
        of the month; None if `data_mes_ano` is empty/None or does not
        contain "/".
    """
    if not data_mes_ano or "/" not in data_mes_ano:
        return None

    mes, ano = data_mes_ano.split("/")
    mes = int(mes)
    ano = int(ano)
    ultimo_dia = calendar.monthrange(ano, mes)[1]

    return f"{ultimo_dia:02d}/{mes:02d}/{ano}"


def data_xs_date(data_str):
    """Converts a "DD/MM/YYYY" date to the xs:date format ("YYYY-MM-DD") required by the Petrobras schema.

    Args:
        data_str: date in "DD/MM/YYYY" format (accepts None/empty).

    Returns:
        str: date in "YYYY-MM-DD" format, or empty string if `data_str` is
        empty/None or not in that format.
    """
    if not data_str:
        return ""
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""

    

def criar_identificacao_certificado(root, dados=None):
    """Creates in `root` the NUMERO_CERTIFICADO, NUMERO_CERTIFICADO_REVISADO and DATA_EMISSAO elements.

    Args:
        root: parent XML element where the elements will be inserted.
        dados: certificate data extracted from the PDF ("certificado",
            "report_date"); if None, the elements are created empty.
    """
    el = ET.SubElement(root, "NUMERO_CERTIFICADO")
    el.text = normalizar_certificado(
        dados.get("certificado", "")
    ) if dados else ""

    ET.SubElement(root, "NUMERO_CERTIFICADO_REVISADO")

    el = ET.SubElement(root, "DATA_EMISSAO")
    el.text = data_xs_date(
        dados.get("report_date", "")
    ) if dados else ""


def sig_ex(root, dados=None):
    """Creates in `root` the TECNICO_SIGNATARIO and TECNICO_EXECUTANTE elements.

    Args:
        root: parent XML element where the elements will be inserted.
        dados: certificate data extracted from the PDF; uses the
            "exec_sig" key (dict with "signatario" and "executante"); if
            None, the elements are created empty.
    """
    el = ET.SubElement(root, "TECNICO_SIGNATARIO")
    el.text = dados.get("exec_sig", {}).get("signatario", "") if dados else ""

    el = ET.SubElement(root, "TECNICO_EXECUTANTE")
    el.text = dados.get("exec_sig", {}).get("executante", "") if dados else ""

# Informações Laboratório
def criar_laboratorio():
    """Creates the LABORATORIO block with ODS's fixed laboratory data (name, address and CAL 0746 accreditation).

    Returns:
        Element: the created LABORATORIO element (not attached to any parent).
    """
    bloco = ET.Element("LABORATORIO")
    ET.SubElement(bloco, "NOME").text = "ODS Lab"
    ET.SubElement(bloco, "ENDERECO").text = "Av. Pierre Simon de Laplace, 830 - Bloco 1 - Techno Park, Campinas - SP, 13069-320"
    ET.SubElement(bloco, "ACREDITACAO").text = "CAL 0746"
    return bloco

# Informações cliente
def criar_cliente(dados=None):
    """Creates the CLIENTE block with name, address and operating unit.

    Args:
        dados: certificate data extracted from the PDF ("cliente",
            "endereco_cliente", "local"); if None, the block is created empty.

    Returns:
        Element: the created CLIENTE element (not attached to any parent).
    """
    bloco = ET.Element("CLIENTE")
    ET.SubElement(bloco, "NOME").text = dados.get("cliente", "") if dados else ""
    ET.SubElement(bloco, "ENDERECO").text = dados.get("endereco_cliente", "") if dados else ""
    ET.SubElement(bloco, "UNIDADE_OPERACIONAL").text = dados.get("local", "") if dados else ""
    return bloco

# Condições ambientais
def criar_condicoes_ambientais(dados=None):
    """Creates the CONDICOES_AMBIENTAIS block with temperature and relative humidity.

    Temperature and humidity variability are not extracted from the PDF
    and are always recorded as "NI" (not informed).

    Args:
        dados: certificate data extracted from the PDF; uses the
            "cond_amb" key (dict with "temperatura_ambiente" and
            "umidade_ambiente"); if None, the values are "NI".

    Returns:
        Element: the created CONDICOES_AMBIENTAIS element (not attached to
        any parent).
    """
    bloco = ET.Element("CONDICOES_AMBIENTAIS")
    cond = dados.get("cond_amb", {}) if dados else {}
    temp = ET.SubElement(bloco, "TEMPERATURA")
    temp_valor = ET.SubElement(temp, "VALOR")
    temp_valor.text = str(cond.get("temperatura_ambiente", "NI"))
    temp_valor.set("UNIDADE_ENG", "°C")
    temp_var = ET.SubElement(temp, "VARIABILIDADE")
    temp_var.text = "NI"
    temp_var.set("UNIDADE_ENG", "NI")

    umid = ET.SubElement(bloco, "UMIDADE_RELATIVA")
    umid_valor = ET.SubElement(umid, "VALOR")
    umid_valor.text = str(cond.get("umidade_ambiente", "NI"))
    umid_valor.set("UNIDADE_ENG", "%")

    umid_var = ET.SubElement(umid, "VARIABILIDADE")
    umid_var.text = "NI"
    umid_var.set("UNIDADE_ENG", "NI")

    return bloco

def criar_procedimento(dados=None):
    """Creates the PROCEDIMENTO_CALIBRACAO block with the procedure's identifier and description.

    Args:
        dados: certificate data extracted from the PDF; uses the
            "procedimento" key (dict with "procedimento" and "descricao");
            if None, the block is created empty.

    Returns:
        Element: the created PROCEDIMENTO_CALIBRACAO element (not attached
        to any parent).
    """
    bloco = ET.Element("PROCEDIMENTO_CALIBRACAO")
    procedimento = (dados.get("procedimento") or {}) if dados else {}
    ET.SubElement(bloco, "IDENTIFICADOR").text = procedimento.get("procedimento", "")
    ET.SubElement(bloco, "DESCRICAO").text = procedimento.get("descricao", "")
    return bloco

def observacoes():
    """Creates the OBSERVACOES block with the fixed note about full reproduction of the document.

    Returns:
        Element: the created OBSERVACOES element (not attached to any parent).
    """
    bloco = ET.Element('OBSERVACOES')
    ET.SubElement(bloco, "OBSERVACAO").text = "A reprodução deste documento somente poderá ser feita integralmente, sem qualquer alteração."
    return bloco

def criar_identificacao_instrumento(dados, pontos ,root):
    """Creates in `root` the instrument identification block (temperature, PT-100 or pressure), according to the category.

    Chooses between three block structures, according to the normalized
    category in `dados["categoria"]`:
    - INSTRUMENTO_TEMPERATURA (temperature transmitters/thermometers),
      including the ELEMENTO_SENSOR sub-block when there is an associated
      sensor, and the TRANSMISSOR sub-block;
    - ELEMENTO_SENSOR_TEMPERATURA (PT-100 2/3/4-wire thermoresistances);
    - INSTRUMENTO_PRESSAO (remaining categories: pressure
      transmitters/gauges).

    In any of the three cases, at the end calls `criar_data_calibracao`
    and `escrever_pontos_calibracao` to complete the block with the
    calibration date and the measured points.

    Args:
        dados: certificate data extracted from the PDF (categoria, TAG,
            serial numbers, manufacturer, model, nominal range etc.).
        pontos: already classified calibration points (see
            `xml_table_extractor.processar_pdf`), passed on to
            `escrever_pontos_calibracao`.
        root: root XML element where the instrument block will be attached.
    """
    informações = dados
    instrumento = normalizar_categoria(dados.get("categoria", "").upper())
    sn_sensor = dados.get("sn_sensor", "")
    if instrumento in ("TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA", "TRANSMISSOR DE TEMPERATURA", "TERMÔMETRO ANALÓGICO", "TERMÔMETRO DIGITAL"):
        bloco_instr = ET.SubElement(root, "INSTRUMENTO_TEMPERATURA")
        if sn_sensor != None:
            bloco_s = ET.SubElement(bloco_instr,"ELEMENTO_SENSOR")
            ET.SubElement(bloco_s,'NUM_SERIE').text = dados.get("sn_sensor","") if dados else ""
            ET.SubElement(bloco_s, "TAG").text = dados.get("tag_sensor", "") if dados else ""
            ET.SubElement(bloco_s, "DESCRICAO").text = dados.get('tipo_sensor', "") if dados else ""
            ET.SubElement(bloco_s, "COMPRIMENTO", UNIDADE_ENG='mm').text = "NI"
            ET.SubElement(bloco_s, 'DIAMETRO', UNIDADE_ENG='mm').text = "NI"

        bloco_t = ET.SubElement(bloco_instr,"TRANSMISSOR")
        ET.SubElement(bloco_t, "NUM_SERIE").text = dados.get('sn_instrumento') if dados else ""
        ET.SubElement(bloco_t, "TAG").text = dados.get('tag') if dados else ""
        ET.SubElement(bloco_t, 'DESCRICAO').text = dados.get('categoria', "") if dados else ""
        ET.SubElement(bloco_t, 'FABRICANTE').text = dados.get('fabricante', "") if dados else ""
        ET.SubElement(bloco_t, 'MODELO').text = dados.get('modelo', "") if dados else ""
        faixa = ET.SubElement(bloco_t, "FAIXA_NOMINAL")
        min_el = ET.SubElement(faixa ,"MIN", UNIDADE_ENG="°C")
        min_el.text = str(dados.get("inmin_range", "")) if dados else ""
        max_el = ET.SubElement(faixa, "MAX", UNIDADE_ENG="°C")
        max_el.text = str(dados.get("inmax_range", "")) if dados else ""

        criar_data_calibracao(bloco_instr, informações)
        escrever_pontos_calibracao(informações, pontos, bloco_instr, obter_unidade_eng(dados))


        


    elif instrumento == "TERMORRESISTÊNCIA PT-100 - 2 FIOS" or instrumento ==  "TERMORRESISTÊNCIA PT-100 - 3 FIOS" or instrumento == "TERMORRESISTÊNCIA PT-100 - 4 FIOS": 
        bloco = ET.SubElement(root, "ELEMENTO_SENSOR_TEMPERATURA")
        ET.SubElement(bloco, "NUM_SERIE").text = dados.get("sn_instrumento","") if dados else ""
        ET.SubElement(bloco, 'TAG').text = dados.get("tag", "") if dados else ""
        ET.SubElement(bloco, "DESCRICAO").text = dados.get("categoria", "") if dados else ""
        ET.SubElement(bloco, "COMPRIMENTO", UNIDADE_ENG='mm').text = str(dados.get("rod_length")) if dados else ""
        ET.SubElement(bloco, 'DIAMETRO', UNIDADE_ENG='mm').text = str(dados.get('probe_diameter') if dados else "")
        criar_data_calibracao(bloco, informações)
        escrever_pontos_calibracao(informações, pontos, bloco, obter_unidade_eng(dados))


    else:
        bloco = ET.SubElement(root, "INSTRUMENTO_PRESSAO")
        ET.SubElement(bloco, "NUM_SERIE").text = dados.get("sn_instrumento","") if dados else ""
        ET.SubElement(bloco, 'TAG').text = dados.get("tag", "") if dados else ""
        ET.SubElement(bloco, "DESCRICAO").text = dados.get("categoria", "") if dados else ""
        ET.SubElement(bloco, "FABRICANTE").text = dados.get('fabricante', "") if dados else ""
        ET.SubElement(bloco, "MODELO").text = dados.get('modelo', "") if dados else ""
        faixa = ET.SubElement(bloco, "FAIXA_NOMINAL")
        min_el = ET.SubElement(faixa, "MIN", UNIDADE_ENG="kPa")
        min_el.text = str(dados.get("inmin_range", "")) if dados else ""
        max_el = ET.SubElement(faixa, "MAX", UNIDADE_ENG="kPa")
        max_el.text = str(dados.get("inmax_range", "")) if dados else ""
        criar_data_calibracao(bloco, informações)
        escrever_pontos_calibracao(informações, pontos, bloco, obter_unidade_eng(dados))
        
# Data calibração
def criar_data_calibracao(root, dados):
    """Creates in `root` the DATA_CALIBRACAO element, converted to xs:date format.

    Args:
        root: parent XML element where the element will be inserted.
        dados: certificate data extracted from the PDF; uses the "data"
            key ("DD/MM/YYYY" format); if None/empty, the element is empty.
    """
    el = ET.SubElement(root, "DATA_CALIBRACAO")
    el.text = data_xs_date(dados.get("data", "")) if dados else ""

# tipo transmissor de pressão
def tipo_transmissor_pressao(dados):
    """Determines the instrument's pressure measurement type (differential or static), for the optional TIPO_TRANSMISSOR_PRESSAO element.

    Args:
        dados: certificate data extracted from the PDF; uses the
            "categoria" key.

    Returns:
        Element: TIPO_TRANSMISSOR_PRESSAO element with text "diferencial"
        (digital pressure gauge or digital differential pressure gauge) or
        "estática" (remaining categories); empty text if `dados` is
        None/empty.

    Notes:
        Function not wired into the generation flow
        (`gerar_xml_certificado` / `criar_identificacao_instrumento`) —
        business decision documented in tasks/TASKS.md: TIPO_TRANSMISSOR_PRESSAO
        is optional in the XSD (minOccurs="0") and enabling it would
        change the content of real certificates, so it was kept but left
        unwired, pending confirmation before use.
    """
    categoria = normalizar_categoria(dados.get("categoria", "")) if dados else ""
    el = ET.Element("TIPO_TRANSMISSOR_PRESSAO")
    if categoria.upper() == "MANOMETRO DIGITAL" or categoria.upper() == "MANOMETRO DIFERENCIAL DIGITAL":
        el.text = "diferencial" if categoria else ""
    else:
        el.text = "estática" if categoria else ""
    return el

# padrões
def criar_identificacao_padroes(dados=None):
    """Creates the PADROES block with one PADRAO for each reference standard used in the calibration.

    Args:
        dados: certificate data extracted from the PDF; uses the
            "padroes_utilizados" key (list of dicts with "tipo",
            "identificacao", "procedimento_calib", "certificado" and
            "validade" in "MM/YYYY" format); if None, the block is empty.

    Returns:
        Element: the created PADROES element (not attached to any parent).
    """
    bloco = ET.Element("PADROES")

    padroes = dados.get("padroes_utilizados", []) if dados else []

    for p in padroes:
        padrao = ET.SubElement(bloco, "PADRAO")

        ET.SubElement(padrao, "DESCRICAO").text = p.get("tipo", "")

        ET.SubElement(padrao, "IDENTIFICADOR").text = p.get("identificacao", "")

        cert = ET.SubElement(padrao, "CERTIFICADO_PADRAO")

        ET.SubElement(cert, "LABORATORIO").text = p.get('procedimento_calib', '')

        ET.SubElement(cert, "NUMERO_CERTIFICADO").text = p.get("certificado", "")

        ET.SubElement(cert, "VALIDADE").text = data_xs_date(completar_data(p.get("validade", ""))) 
    return bloco

# Faixa calibrada
def criar_faixa_calibrada(dados, unidade_eng=None):
    """Creates the FAIXA_CALIBRADA element with the minimum and maximum limits of the calibrated range.

    Args:
        dados: certificate data extracted from the PDF ("min_range",
            "max_range"); if None/empty, the values are "NI".
        unidade_eng: engineering units map (see `obter_unidade_eng`); uses
            the "faixa_cal" key as UNIDADE_ENG for the MIN/MAX elements, or
            "NI" if not provided.

    Returns:
        Element: the created FAIXA_CALIBRADA element (not attached to any
        parent).
    """

    faixa = ET.Element("FAIXA_CALIBRADA")
    unidade = unidade_eng.get("faixa_cal", "NI") if unidade_eng else "NI"

    min_el = ET.SubElement(faixa, "MIN", UNIDADE_ENG=unidade)
    min_el.text = str(dados.get("min_range", "")) if dados else "NI"

    max_el = ET.SubElement(faixa, "MAX", UNIDADE_ENG=unidade)
    max_el.text = str(dados.get("max_range", "")) if dados else "NI"

    return faixa

# gerar pontos calibração pressão
def gerar_pontos_calibracao_pressao(results1, results2, unidade_eng):
    """Builds the PONTOS_DE_CALIBRACAO block of a pressure instrument, combining raw cycle readings with the calculated results.

    Each point combines, paired by index, a record from `results1`
    (reference and ascending/descending readings of the two cycles, see
    `xml_table_extractor.ajustar_transmissor_pressao_eletrico` /
    `ajustar_manometros`) with the corresponding record from `results2`
    (calculated deviation/uncertainty/k/veff). For uncertainty and
    deviation, prefers the value in mA when present
    ("incerteza_ma"/"tendencia_ma"), falling back to the value in kPa
    otherwise.

    Args:
        results1: list of raw reading records (reference and
            ascending/descending cycles).
        results2: list of calculated result records (deviation,
            uncertainty, k, veff), paired by index with `results1`.
        unidade_eng: engineering units map (see `obter_unidade_eng`); uses
            "valor_referencia", "valor_indicado", "incerteza" and "erro",
            or "NI" for those missing.

    Returns:
        Element: the created PONTOS_DE_CALIBRACAO element, with one
        PONTO_DE_CALIBRACAO per pair (results1[i], results2[i]) (not
        attached to any parent).
    """
    pontos = ET.Element("PONTOS_DE_CALIBRACAO")
    unidade_ref = unidade_eng.get("valor_referencia", "NI") if unidade_eng else "NI"
    unidade_indicado = unidade_eng.get("valor_indicado", "NI") if unidade_eng else "NI"
    unidade_incerteza = unidade_eng.get("incerteza", "NI") if unidade_eng else "NI"
    unidade_erro = unidade_eng.get("erro", "NI") if unidade_eng else "NI"

    for bruto, resultado in zip(results1, results2):
        ponto = ET.SubElement(pontos, "PONTO_DE_CALIBRACAO")

        # Valor de referência
        ET.SubElement(
            ponto,
            "VALOR_REFERENCIA",
            UNIDADE_ENG=unidade_ref
        ).text = str(bruto.get("kPa_ref", "NI"))

        # Ciclos
        ciclos = [
            ("p_cic_cresc", "p_cic_decres"),
            ("s_cic_cres", "s_cic_decrs"),
        ]

        for idx, (asc, desc) in enumerate(ciclos, start=1):
            ciclo_el = ET.SubElement(ponto, f"CICLO_{idx}")

            ET.SubElement(
                ciclo_el,
                "VALOR_INDICADO_ASCENDENTE",
                UNIDADE_ENG=unidade_indicado
            ).text = str(bruto.get(asc, "NI"))

            ET.SubElement(
                ciclo_el,
                "VALOR_INDICADO_DESCENDENTE",
                UNIDADE_ENG=unidade_indicado
            ).text = str(bruto.get(desc, "NI"))

        # INCERTEZA (vem do results2)
        valor_incerteza = (
            resultado.get("incerteza_ma")
            if resultado.get("incerteza_ma") is not None
            else resultado.get("incerteza_kpa", "NI")
        )

        inc = ET.SubElement(
            ponto,
            "INCERTEZA",
            UNIDADE_ENG=unidade_incerteza,
            K=str(resultado.get('k', "NI")),
            GRAU_LIBERDADE=str(resultado.get("veff", "NI"))
        )
        inc.text = str(valor_incerteza)

        # ERRO (vem do results2)
        valor_tendencia = (
            resultado.get("tendencia_ma")
            if resultado.get("tendencia_ma") is not None
            else resultado.get("tendencia_kpa", "NI")
        )

        ET.SubElement(
            ponto,
            "ERRO",
            UNIDADE_ENG=unidade_erro
        ).text = str(valor_tendencia)


    return pontos

def gerar_pontos_calibracao_termometro(registros, unidade_eng):
    """Builds the PONTOS_DE_CALIBRACAO block of a temperature transmitter/thermometer from the calibration records.

    Args:
        registros: list of calibration records (see
            `xml_table_extractor.ajustar_transmissor_temperatura_eletrico`
            / `ajustar_transmissor_temperatura`), each with
            "valor_referencia_c", "media_leituras_c", "tendencia_c",
            "incerteza_c", "k" and "veff".
        unidade_eng: engineering units map (see `obter_unidade_eng`); uses
            "valor_referencia", "valor_indicado", "incerteza" and "erro",
            or "NI" for those missing.

    Returns:
        Element: the created PONTOS_DE_CALIBRACAO element, with one
        PONTO_DE_CALIBRACAO per record (not attached to any parent).
    """
    pontos = ET.Element("PONTOS_DE_CALIBRACAO")
    unidade_ref = unidade_eng.get("valor_referencia", "NI") if unidade_eng else "NI"
    unidade_indicado = unidade_eng.get("valor_indicado", "NI") if unidade_eng else "NI"
    unidade_incerteza = unidade_eng.get("incerteza", "NI") if unidade_eng else "NI"
    unidade_erro = unidade_eng.get("erro", "NI") if unidade_eng else "NI"
    for reg in registros:
        ponto = ET.SubElement(pontos, "PONTO_DE_CALIBRACAO")

        
        ET.SubElement(
            ponto,
            "VALOR_REFERENCIA",
            UNIDADE_ENG=unidade_ref
        ).text = str(reg.get("valor_referencia_c", "NI"))

       
        valor_indicado = ET.SubElement(ponto, "VALOR_INDICADO")

        ET.SubElement(
            valor_indicado,
            "VALOR",
            UNIDADE_ENG=unidade_indicado
        ).text = str(reg.get("media_leituras_c", "NI"))

        inc = ET.SubElement(
            valor_indicado,
            "INCERTEZA_EXP",
            UNIDADE_ENG=unidade_incerteza,
            K=str(reg.get("k", "NI")),
            GRAU_LIBERDADE=str(reg.get("veff", "NI"))
        )
        inc.text = str(reg.get("incerteza_c", "NI"))


        ET.SubElement(
            ponto,
            "ERRO",
            UNIDADE_ENG=unidade_erro
        ).text = str(reg.get("tendencia_c", "NI"))

    return pontos

def gerar_pontos_calibracao_pt100(resultados, unidade_eng=None):
    """Builds the PONTOS_DE_CALIBRACAO block of a PT-100 thermoresistance from the calibration records.

    Args:
        resultados: list of calibration records (see
            `xml_table_extractor.ajustar_pt100`), each with
            "valor_referencia", "media_celsius", "tendencia", "incerteza",
            "k" and "veff"; items that are not a dict are ignored.
        unidade_eng: engineering units map (see `obter_unidade_eng`); uses
            "valor_referencia", "valor_indicado", "incerteza" and "erro",
            or "NI" for those missing.

    Returns:
        Element: the created PONTOS_DE_CALIBRACAO element, with one
        PONTO_DE_CALIBRACAO per valid record; empty if `resultados` is not
        a list (not attached to any parent).
    """
    pontos = ET.Element("PONTOS_DE_CALIBRACAO")
    unidade_ref = unidade_eng.get("valor_referencia", "NI") if unidade_eng else "NI"
    unidade_indicado = unidade_eng.get("valor_indicado", "NI") if unidade_eng else "NI"
    unidade_incerteza = unidade_eng.get("incerteza", "NI") if unidade_eng else "NI"
    unidade_erro = unidade_eng.get("erro", "NI") if unidade_eng else "NI"

    if not isinstance(resultados, list):
        return pontos

    for r in resultados:
        if not isinstance(r, dict):
            continue

        ponto = ET.SubElement(pontos, "PONTO_DE_CALIBRACAO")

        
        ET.SubElement(
            ponto,
            "VALOR_REFERENCIA",
            UNIDADE_ENG=unidade_ref
        ).text = str(r.get("valor_referencia", "NI"))

        
        valor_indicado = ET.SubElement(ponto, "VALOR_INDICADO")

        ET.SubElement(
            valor_indicado,
            "VALOR",
            UNIDADE_ENG=unidade_indicado
        ).text = str(r.get("media_celsius", "NI"))

        
        inc = ET.SubElement(
            valor_indicado,
            "INCERTEZA_EXP",
            UNIDADE_ENG=unidade_incerteza,
            K=str(r.get("k", "NI")),
            GRAU_LIBERDADE=str(r.get("veff", "NI"))
        )
        inc.text = str(r.get("incerteza", "NI"))

        
        ET.SubElement(
            ponto,
            "ERRO",
            UNIDADE_ENG=unidade_erro
        ).text = str(r.get("tendencia", "NI"))

    return pontos

#escrever_pontos_calibracao
def escrever_pontos_calibracao(dados, pontos, root, unidade_eng):
    """Creates in `root` the CALIBRACAO_AS_FOUND block and, if present, CALIBRACAO_AS_LEFT, with calibrated range, points and metrological indicators.

    The points layout varies by instrument category:
    - Thermometers/temperature transmitters: uses `pontos["results1"]` as
      AS_FOUND and `pontos["results2"]` (if present) as AS_LEFT, via
      `gerar_pontos_calibracao_termometro`.
    - PT-100 thermoresistances: if only the RESULTADOS table exists
      (without AS FOUND), treats it as the single AS_FOUND; otherwise,
      uses `pontos["tabela1"]`/`pontos["tabela2"]` to know which is AS
      FOUND and which is the RESULTADOS table (treated as AS LEFT), via
      `gerar_pontos_calibracao_pt100`.
    - Remaining categories (pressure): uses
      `pontos["tabela1"]`/`pontos["tabela2"]` to identify the AS FOUND/AS
      LEFT tables and builds the points via
      `gerar_pontos_calibracao_pressao`, cross-referencing each table with
      the following RESULTADOS table.

    In each block created, also attaches the FAIXA_CALIBRADA (via
    `criar_faixa_calibrada`) and the global metrological indicators (via
    `escrever_indicadores_calibracao`).

    Args:
        dados: certificate data extracted from the PDF; uses the
            "categoria" key to decide the layout.
        pontos: already classified calibration points (see
            `xml_table_extractor.processar_pdf`).
        root: parent XML element (instrument block) where the calibration
            blocks will be attached.
        unidade_eng: engineering units map (see `obter_unidade_eng`),
            passed on to the points and calibrated range assembly functions.
    """
    instrumento = normalizar_categoria(dados.get("categoria", "").upper())
    

    if instrumento in ("TERMÔMETRO DIGITAL", "TERMÔMETRO ANALÓGICO", 'TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA', 'TRANSMISSOR DE TEMPERATURA'):

    
        cal_as_found = ET.SubElement(root, "CALIBRACAO_AS_FOUND")
        cal_as_found.append(
            criar_faixa_calibrada(dados, unidade_eng)
        )

        if pontos.get("results1"):
            cal_as_found.append(
                gerar_pontos_calibracao_termometro(
                    pontos["results1"],
                    unidade_eng
                )
            )
            escrever_indicadores_calibracao(
                cal_as_found,
                dados,
                unidade_eng
            )

        if pontos.get("results2"):
            cal_as_left = ET.SubElement(root, "CALIBRACAO_AS_LEFT")
            cal_as_left.append(
                criar_faixa_calibrada(dados, unidade_eng)
            )
            cal_as_left.append(
                gerar_pontos_calibracao_termometro(
                    pontos["results2"],
                    unidade_eng
                )
            )
            escrever_indicadores_calibracao(
                    cal_as_left,
                    dados,
                    unidade_eng
                )




    elif instrumento == "TERMORRESISTÊNCIA PT-100 - 2 FIOS" or instrumento ==  "TERMORRESISTÊNCIA PT-100 - 3 FIOS" or instrumento == "TERMORRESISTÊNCIA PT-100 - 4 FIOS": 
        
        # --- CASO 1: só RESULTADOS → AS FOUND ---
        if pontos.get("tabela1") == "RESULTADOS" and not pontos.get("tabela2"):
            cal_as_found = ET.SubElement(root, "CALIBRACAO_AS_FOUND")
            cal_as_found.append(criar_faixa_calibrada(dados, unidade_eng))
            cal_as_found.append(
                gerar_pontos_calibracao_pt100(
                    pontos.get("results1", []),
                    unidade_eng
                )
            )
            escrever_indicadores_calibracao(
                cal_as_found,
                dados,
                unidade_eng
            )

        # --- CASO 2: AS FOUND + RESULTADOS (AS LEFT) ---
        else:
            if pontos.get("tabela1") == "AS FOUND":
                cal_as_found = ET.SubElement(root, "CALIBRACAO_AS_FOUND")
                cal_as_found.append(criar_faixa_calibrada(dados, unidade_eng))
                cal_as_found.append(
                    gerar_pontos_calibracao_pt100(
                        pontos.get("results1", []),
                        unidade_eng
                    )
                )
                escrever_indicadores_calibracao(
                cal_as_found,
                dados,
                unidade_eng
            )

            if pontos.get("tabela2") == "RESULTADOS":
                cal_as_left = ET.SubElement(root, "CALIBRACAO_AS_LEFT")
                cal_as_left.append(criar_faixa_calibrada(dados, unidade_eng))
                cal_as_left.append(
                    gerar_pontos_calibracao_pt100(
                        pontos.get("results2", []),
                        unidade_eng
                    )
                )
                escrever_indicadores_calibracao(
                cal_as_left,
                dados,
                unidade_eng
            )

    else:
        cal_as_found = ET.SubElement(root, "CALIBRACAO_AS_FOUND")
        cal_as_found.append(
        criar_faixa_calibrada(dados, unidade_eng))

        if pontos.get("tabela1") == "AS FOUND":
            cal_as_found.append(
                gerar_pontos_calibracao_pressao(
                    pontos.get("results1", []),
                    pontos.get("results2", []),
                    unidade_eng
                )
            )
        
            escrever_indicadores_calibracao(
                cal_as_found,
                dados,
                unidade_eng
            )


        if pontos.get("tabela2") == "AS LEFT":
            cal_as_left = ET.SubElement(root, "CALIBRACAO_AS_LEFT")
            cal_as_left.append(
                criar_faixa_calibrada(dados, unidade_eng)
            )
            cal_as_left.append(
                gerar_pontos_calibracao_pressao(
                    pontos.get("results2", []),
                    pontos.get("results3", []),
                    unidade_eng
                )
            )
        
            escrever_indicadores_calibracao(
                cal_as_left,
                dados,
                unidade_eng
            )

CATEGORIAS_TEMPERATURA = (
    "TERMORRESISTÊNCIA PT-100 - 2 FIOS",
    "TERMORRESISTÊNCIA PT-100 - 3 FIOS",
    "TERMORRESISTÊNCIA PT-100 - 4 FIOS",
    "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA",
    "TRANSMISSOR DE TEMPERATURA",
    "TERMÔMETRO ANALÓGICO",
    "TERMÔMETRO DIGITAL"
)

def indicadores_globais(dados, unidade_eng="NI"):
    """Builds the calibration's global metrological indicator elements (fiducial error, uncertainty, hysteresis and repeatability).

    HISTERESE is only included for non-temperature categories (see
    `CATEGORIAS_TEMPERATURA`); INCERTEZA is only included if the
    "incerteza" key is present in `dados["indicadores_metrologicos"]`.

    Args:
        dados: certificate data extracted from the PDF; uses "categoria"
            and "indicadores_metrologicos" (dict with "erro_fiducial",
            "incerteza", "histerese", "repetibilidade").
        unidade_eng: engineering units map (see `obter_unidade_eng`); uses
            "erro_fid", "incert_global", "histerese" and "rept", or "NI"
            for those missing.

    Returns:
        list[Element]: list with the ERRO_FIDUCIAL, INCERTEZA
        (conditional), HISTERESE (conditional) and REPETIBILIDADE
        elements, in that order, each with text "NI" when the
        corresponding indicator is not present/empty in `dados`.
    """

    indicadores = dados.get("indicadores_metrologicos", {}) if dados else {}
    categoria = normalizar_categoria(dados.get("categoria", "").upper()) if dados else ""
    unidade_erro_fid = unidade_eng.get("erro_fid", "NI") if unidade_eng else "NI"
    unidade_incert_global = unidade_eng.get("incert_global", "NI") if unidade_eng else "NI"
    unidade_histerese = unidade_eng.get("histerese", "NI") if unidade_eng else "NI"
    unidade_repetibilidade = unidade_eng.get("rept", "NI") if unidade_eng else "NI"
    elementos = []


    erro_fid = ET.Element(
        "ERRO_FIDUCIAL",
        UNIDADE_ENG=unidade_erro_fid
    )
    erro_fid.text = (
        "NI" if indicadores.get("erro_fiducial") in (None, "", "NI")
        else str(indicadores.get("erro_fiducial"))
    )
    elementos.append(erro_fid)

    
    if "incerteza" in indicadores:
        inc = ET.Element(
            "INCERTEZA",
            UNIDADE_ENG=unidade_incert_global,
            K="NI",
            GRAU_LIBERDADE="NI"
        )
        inc.text = (
            "NI" if indicadores.get("incerteza") in (None, "", "NI")
            else str(indicadores.get("incerteza"))
        )
        elementos.append(inc)

    
    if categoria not in CATEGORIAS_TEMPERATURA:
        hist = ET.Element(
            "HISTERESE",
            UNIDADE_ENG=unidade_histerese
        )
        hist.text = (
            "NI" if indicadores.get("histerese") in (None, "", "NI")
            else str(indicadores.get("histerese"))
        )
        elementos.append(hist)

  
    rep = ET.Element(
        "REPETIBILIDADE",
        UNIDADE_ENG=unidade_repetibilidade
    )
    rep.text = (
        "NI" if indicadores.get("repetibilidade") in (None, "", "NI")
        else str(indicadores.get("repetibilidade"))
    )
    elementos.append(rep)

    return elementos

def escrever_indicadores_calibracao(calibracao_el, dados, unidade_eng):
    """Attaches to `calibracao_el` the global metrological indicators returned by `indicadores_globais`.

    Args:
        calibracao_el: XML element of the calibration block (AS_FOUND or
            AS_LEFT) where the indicators will be attached.
        dados: certificate data, passed on to `indicadores_globais`.
        unidade_eng: engineering units map, passed on to `indicadores_globais`.
    """
    for el in indicadores_globais(dados, unidade_eng):
        calibracao_el.append(el) 
   

def gerar_xml_certificado(informacoes: dict, pontos: list, caminho_saida: str):
    """Generates the Petrobras-standard calibration certificate XML (temperature or pressure) and writes it to disk.

    Chooses the root tag according to the instrument category
    (CERTIFICADO_CALIBRACAO_TEMPERATURA for temperature
    transmitters/thermometers, CERTIFICADO_CALIBRACAO_TEMPERATURA_TE for
    PT-100 thermoresistances, CERTIFICADO_CALIBRACAO_PRESSAO for the
    remaining categories) and builds the full document (certificate
    identification, laboratory, client, signatures, environmental
    conditions, standards, procedure, remarks and instrument
    identification with its calibration points).

    Args:
        informacoes: certificate data extracted from the PDF (categoria,
            identificação, cliente, laboratório, condições ambientais,
            padrões, procedimento etc.).
        pontos: already classified calibration points (see
            `xml_table_extractor.processar_pdf`).
        caminho_saida: path of the output XML file.

    Returns:
        str: `caminho_saida`, passed back unchanged after the XML is written.
    """
    instrumento = normalizar_categoria(
        informacoes.get("categoria", "").upper()
    )
    unidade_eng = obter_unidade_eng(informacoes)

    NAMESPACE = "http://Petrobras/Medicao/Calibracao"
    

    ET.register_namespace("cal", NAMESPACE)
    

    if instrumento in (
        "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA",
        "TRANSMISSOR DE TEMPERATURA",
        "TERMÔMETRO ANALÓGICO",
        "TERMÔMETRO DIGITAL",
    ):
        root_tag = "CERTIFICADO_CALIBRACAO_TEMPERATURA"

    elif instrumento in (
        "TERMORRESISTÊNCIA PT-100 - 2 FIOS",
        "TERMORRESISTÊNCIA PT-100 - 3 FIOS",
        "TERMORRESISTÊNCIA PT-100 - 4 FIOS",
    ):
        root_tag = "CERTIFICADO_CALIBRACAO_TEMPERATURA_TE"

    else:
        root_tag = "CERTIFICADO_CALIBRACAO_PRESSAO"

    root = ET.Element(f"{{{NAMESPACE}}}{root_tag}")

    criar_identificacao_certificado(root, informacoes)
    root.append(criar_laboratorio())
    root.append(criar_cliente(informacoes))
    sig_ex(root, informacoes)
    root.append(criar_condicoes_ambientais(informacoes))
    root.append(criar_identificacao_padroes(informacoes))
    root.append(criar_procedimento(informacoes))
    root.append(observacoes())
    criar_identificacao_instrumento(informacoes, pontos, root)
    salvar_xml_bonito(root, caminho_saida)

    return caminho_saida