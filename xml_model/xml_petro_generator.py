import xml.etree.ElementTree as ET
import calendar
from xml.dom import minidom
import os
from datetime import datetime
from pathlib import Path

from xml_model.xml_table_extractor import processar_pdf
from pdf.parser_certificados import extrair_campos
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado

mapeamento_eng = {
    "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA": 
    {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "mA", "incerteza": "mA", "erro": "mA", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
    "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA": 
    {'faixa_cal': "kPa", "valor_referencia": "kPa", "valor_indicado": "mA", "incerteza": "mA", "erro": "mA", "erro_fid": "%", "incert_global": "%", "histerese": "%", "rept": "%"},
    "TERMORRESISTÊNCIA PT-100 - 4 FIOS":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TERMORRESISTÊNCIA PT-100 - 3 FIOS":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TERMORRESISTÊNCIA PT-100 - 2 FIOS":
    {'faixa_cal': "°C", "valor_referencia": "°C", "valor_indicado": "°C", "incerteza": "°C", "erro": "°C", "erro_fid": "NI", "incert_global": "NI", "histerese": "NI", "rept": "NI"},
    "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA":
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
    categoria = normalizar_categoria(dados.get("categoria", "").upper())
    print(f"categoria_unidade_eng: {categoria}")

    if not categoria:
        return {}

    categoria = categoria.upper()

    for categoria_map, unidades in mapeamento_eng.items():
        if categoria_map in categoria:
            print(f'Mapeamento_encontrado: {categoria_map}:{unidades}')
            return unidades.copy()

    return {}


def gerar_caminho_xml(caminho_pdf):
    pasta = os.path.dirname(caminho_pdf)
    nome = os.path.splitext(os.path.basename(caminho_pdf))[0]
    return os.path.join(pasta, f"{nome}.xml")


def completar_data(data_mes_ano):
    if not data_mes_ano or "/" not in data_mes_ano:
        return None

    mes, ano = data_mes_ano.split("/")
    mes = int(mes)
    ano = int(ano)
    ultimo_dia = calendar.monthrange(ano, mes)[1]

    return f"{ultimo_dia:02d}/{mes:02d}/{ano}"


def data_xs_date(data_str):
    """
    Docstring for data_xs_date
    
    :param data_str: Description
    """
    if not data_str:
        return ""
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


# regra para a unidade eng istrumento pressão
def definir_unidade_eng(categoria):
    categorias_ma = [
        "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA",
        "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA",
    ]
    categorias_c = [
        "TERMÔMETRO DIGITAL",
        "TERMÔMETRO ANALÓGICO",
        "TERMORRESISTÊNCIA PT-100 - 2 FIOS",
        "TERMORRESISTÊNCIA PT-100 - 3 FIOS",
        "TERMORRESISTÊNCIA PT-100 - 4 FIOS",
        'TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA'
    ]

    if categoria in categorias_ma:
        return "mA"

    if categoria in categorias_c:
        return "°C"

    # fallback (pressão mecânica, etc.)
    return "NI"
    

def criar_identificacao_certificado(root, dados=None):
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
    el = ET.SubElement(root, "TECNICO_SIGNATARIO")
    el.text = dados.get("exec_sig", {}).get("signatario", "") if dados else ""

    el = ET.SubElement(root, "TECNICO_EXECUTANTE")
    el.text = dados.get("exec_sig", {}).get("executante", "") if dados else ""

# Informações Laboratório
def criar_laboratorio():
    bloco = ET.Element("LABORATORIO")
    ET.SubElement(bloco, "NOME").text = "ODS Lab"
    ET.SubElement(bloco, "ENDERECO").text = "Av. Pierre Simon de Laplace, 830 - Bloco 1 - Techno Park, Campinas - SP, 13069-320"
    ET.SubElement(bloco, "ACREDITACAO").text = "CAL 0746"
    return bloco

# Informações cliente
def criar_cliente(dados=None):
    bloco = ET.Element("CLIENTE")
    ET.SubElement(bloco, "NOME").text = dados.get("cliente", "") if dados else ""
    ET.SubElement(bloco, "ENDERECO").text = dados.get("endereco_cliente", "") if dados else ""
    ET.SubElement(bloco, "UNIDADE_OPERACIONAL").text = dados.get("local", "") if dados else ""
    return bloco

# Condições ambientais
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

    umid = ET.SubElement(bloco, "UMIDADE_RELATIVA")
    umid_valor = ET.SubElement(umid, "VALOR")
    umid_valor.text = str(cond.get("umidade_ambiente", "NI"))
    umid_valor.set("UNIDADE_ENG", "%")

    umid_var = ET.SubElement(umid, "VARIABILIDADE")
    umid_var.text = "NI"
    umid_var.set("UNIDADE_ENG", "NI")

    return bloco

def criar_procedimento(dados=None):
    bloco = ET.Element("PROCEDIMENTO_CALIBRACAO")
    ET.SubElement(bloco, "IDENTIFICADOR").text = dados.get("procedimento", "").get("procedimento", "") if dados else ""
    ET.SubElement(bloco, "DESCRICAO").text = dados.get("procedimento", "").get("descricao", "") if dados else ""
    return bloco

def observacoes():
    bloco = ET.Element('OBSERVACOES')
    ET.SubElement(bloco, "OBSERVACAO").text = "A reprodução deste documento somente poderá ser feita integralmente, sem qualquer alteração."
    return bloco

def criar_identificacao_instrumento(dados, pontos ,root):
    informações = dados
    instrumento = normalizar_categoria(dados.get("categoria", "").upper())
    sn_sensor = dados.get("sn_sensor", "")
    if instrumento == "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA" or instrumento == "TERMÔMETRO ANALÓGICO" or instrumento == "TERMÔMETRO DIGITAL":
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
        

# FAIXA NOMINNAL
def criar_faixa_nominal(dados):
    bloco = ET.Element("FAIXA_NOMINAL")
    min_el = ET.SubElement(bloco, "MIN", UNIDADE_ENG="kPa")
    min_el.text = str(dados.get("min_range", "")) if dados else ""

    max_el = ET.SubElement(bloco, "MAX", UNIDADE_ENG="kPa")
    max_el.text = str(dados.get("max_range", "")) if dados else ""

    return bloco

# Data calibração
def criar_data_calibracao(root, dados):
    el = ET.SubElement(root, "DATA_CALIBRACAO")
    el.text = data_xs_date(dados.get("data", "")) if dados else ""

# tipo transmissor de pressão
def tipo_transmissor_pressao(dados):
    categoria = normalizar_categoria(dados.get("categoria", "")) if dados else ""
    el = ET.Element("TIPO_TRANSMISSOR_PRESSAO")
    if categoria.upper() == "MANOMETRO DIGITAL" or categoria.upper() == "MANOMETRO DIFERENCIAL DIGITAL":
        el.text = "diferencial" if categoria else ""
    else:
        el.text = "estática" if categoria else ""
    return el

# padrões
def criar_identificacao_padroes(dados=None):
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
    
    faixa = ET.Element("FAIXA_CALIBRADA")
    unidade = unidade_eng.get("faixa_cal", "NI") if unidade_eng else "NI"

    min_el = ET.SubElement(faixa, "MIN", UNIDADE_ENG=unidade)
    min_el.text = str(dados.get("min_range", "")) if dados else "NI"

    max_el = ET.SubElement(faixa, "MAX", UNIDADE_ENG=unidade)
    max_el.text = str(dados.get("max_range", "")) if dados else "NI"

    return faixa

# gerar pontos calibração pressão
def gerar_pontos_calibracao_pressao(results1, results2, unidade_eng):
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

def gerar_pontos_calibracao_pt100(resultados, unidade_eng="°C"):
    pontos = ET.Element("PONTOS_DE_CALIBRACAO")
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
    instrumento = normalizar_categoria(dados.get("categoria", "").upper())
    

    if instrumento in ("TERMÔMETRO DIGITAL", "TERMÔMETRO ANALÓGICO", 'TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA', ):

    
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
                cal_as_found,
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
                    pontos.get("results1", []),
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
    "TERMÔMETRO ANALÓGICO",
    "TERMÔMETRO DIGITAL"
)

def indicadores_globais(dados, unidade_eng="NI"):
   
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
    for el in indicadores_globais(dados, unidade_eng):
        calibracao_el.append(el) 
   

def gerar_xml_certificado(informacoes: dict, pontos: list, caminho_saida: str):
    instrumento = normalizar_categoria(
        informacoes.get("categoria", "").upper()
    )
    unidade_eng = obter_unidade_eng(informacoes)

    NAMESPACE = "http://Petrobras/Medicao/Calibracao"
    

    ET.register_namespace("cal", NAMESPACE)
    

    if instrumento in (
        "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA",
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
    xml_str = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "wb") as f:
        f.write(pretty_xml)

    return caminho_saida