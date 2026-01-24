import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
from datetime import datetime

from xml_table_extractor import processar_pdf
from pdf.parser_certificados import extrair_campos
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado





def gerar_caminho_xml(caminho_pdf):
    pasta = os.path.dirname(caminho_pdf)
    nome = os.path.splitext(os.path.basename(caminho_pdf))[0]
    return os.path.join(pasta, f"{nome}.xml")

# Converte data para o padrão correto
def data_xs_date(data_str):
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

# FALTA COLETAR SIGNATÁRIO e EXECUTOR
def sig_ex(root, dados=None):
    el = ET.SubElement(root, "TECNICO_SIGNATARIO")

    ET.SubElement(root, "TECNICO_EXECUTANTE")

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

def observacoes():
    bloco = ET.Element('OBSERVACOES')
    ET.SubElement(bloco, "OBSERVACAO").text = "A reprodução deste documento somente poderá ser feita integralmente, sem qualquer alteração."
    return bloco

def criar_identificacao_instrumento(dados):
    bloco = ET.Element("INSTRUMENTO_PRESSÃO")
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
    return bloco


# FAIXA NOMINNAL
def criar_faixa_nominal(dados):
    bloco = ET.Element("FAIXA_NOMINAL")
    min_el = ET.SubElement(bloco, "MIN", UNIDADE_ENG="kPa")
    min_el.text = str(dados.get("min_range", "")) if dados else ""

    max_el = ET.SubElement(bloco, "MAX", UNIDADE_ENG="kPa")
    max_el.text = str(dados.get("max_range", "")) if dados else ""

    return bloco

def criar_data_calibracao(root, dados):
    el = ET.SubElement(root, "DATA_CALIBRACAO")
    el.text = data_xs_date(dados.get("data", "")) if dados else ""

# tipo transmissor
def tipo_transmissor_pressao(dados):
    categoria = dados.get("categoria", "") if dados else ""
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

        ET.SubElement(padrao, "FABRICANTE").text

        ET.SubElement(padrao, "MODELO").text 

        ET.SubElement(padrao, "IDENTIFICADOR").text = p.get("identificacao", "")

        cert = ET.SubElement(padrao, "CERTIFICADO_PADRAO")

        ET.SubElement(cert, "LABORATORIO").text = "RBC" # Essa informação não está no PDF

        ET.SubElement(cert, "NUMERO_CERTIFICADO").text = p.get("certificado", "")

        ET.SubElement(cert, "VALIDADE").text = p.get("validade", "") # Confirmar a data correta no certificado só está mês 
    return bloco

# Faixa calibrada

def criar_faixa_calibrada(dados, unidade_eng=None):
    
    faixa = ET.Element("FAIXA_CALIBRADA")

    min_el = ET.SubElement(faixa, "MIN", UNIDADE_ENG="kPa")
    min_el.text = str(dados.get("min_range", "")) if dados else "NI"

    max_el = ET.SubElement(faixa, "MAX", UNIDADE_ENG="kPa")
    max_el.text = str(dados.get("max_range", "")) if dados else "NI"

    return faixa



def gerar_pontos_calibracao(results1, results2, unidade_eng):
    pontos = ET.Element("PONTOS_DE_CALIBRACAO")

    for bruto, resultado in zip(results1, results2):
        ponto = ET.SubElement(pontos, "PONTO_DE_CALIBRACAO")

        # Valor de referência
        ET.SubElement(
            ponto,
            "VALOR_REFERENCIA",
            UNIDADE_ENG=unidade_eng
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
                UNIDADE_ENG=unidade_eng
            ).text = str(bruto.get(asc, "NI"))

            ET.SubElement(
                ciclo_el,
                "VALOR_INDICADO_DESCENDENTE",
                UNIDADE_ENG=unidade_eng
            ).text = str(bruto.get(desc, "NI"))

        # INCERTEZA (vem do results2)
        inc = ET.SubElement(
            ponto,
            "INCERTEZA",
            UNIDADE_ENG=unidade_eng,
            K=str(resultado.get("k", "NI")),
            GRAU_LIBERDADE=str(resultado.get("veff", "NI"))
        )
        inc.text = str(resultado.get("incerteza_ma", "NI"))

        # ERRO (vem do results2)
        ET.SubElement(
            ponto,
            "ERRO",
            UNIDADE_ENG=unidade_eng
        ).text = str(resultado.get("tendencia_ma", "NI"))


    return pontos



def indicadores_globais(dados, unidade_eng="NI"):
    """
    Cria os indicadores metrológicos globais conforme XSD.
    Retorna uma lista de elementos XML.
    """

    indicadores = dados.get("indicadores_metrologicos", {}) if dados else {}

    elementos = []

    # -------------------------------
    # ERRO_FIDUCIAL (obrigatório)
    # -------------------------------
    erro_fid = ET.Element(
        "ERRO_FIDUCIAL",
        UNIDADE_ENG=unidade_eng
    )
    erro_fid.text = (
        "NI" if indicadores.get("erro_fiducial") in (None, "", "NI")
        else str(indicadores.get("erro_fiducial"))
    )
    elementos.append(erro_fid)

    # -------------------------------
    # INCERTEZA GLOBAL (opcional)
    # -------------------------------
    if "incerteza" in indicadores:
        inc = ET.Element(
            "INCERTEZA",
            UNIDADE_ENG=unidade_eng,
            K="NI",
            GRAU_LIBERDADE="NI"
        )
        inc.text = (
            "NI" if indicadores.get("incerteza") in (None, "", "NI")
            else str(indicadores.get("incerteza"))
        )
        elementos.append(inc)

    # -------------------------------
    # HISTERESE (obrigatório)
    # -------------------------------
    hist = ET.Element(
        "HISTERESE",
        UNIDADE_ENG=unidade_eng
    )
    hist.text = (
        "NI" if indicadores.get("histerese") in (None, "", "NI")
        else str(indicadores.get("histerese"))
    )
    elementos.append(hist)

    # -------------------------------
    # REPETIBILIDADE (obrigatório)
    # -------------------------------
    rep = ET.Element(
        "REPETIBILIDADE",
        UNIDADE_ENG=unidade_eng
    )
    rep.text = (
        "NI" if indicadores.get("repetibilidade") in (None, "", "NI")
        else str(indicadores.get("repetibilidade"))
    )
    elementos.append(rep)

    return elementos
    
   
# =====================================================
# XML COMPLETO
# =====================================================

def gerar_xml_certificado_pressao(informacoes: dict, pontos: list) -> ET.Element:
    root = ET.Element("CERTIFICADO_CALIBRACAO_PRESSAO")

    criar_identificacao_certificado(root,informacoes)
    root.append(criar_laboratorio())
    root.append(criar_cliente(informacoes))
    sig_ex(root, infomacoes)
    root.append(criar_condicoes_ambientais(informacoes))
    root.append(criar_identificacao_padroes(informacoes))    
    root.append(criar_procedimento(informacoes))
    root.append(observacoes())
    root.append(criar_identificacao_instrumento(informacoes))
    criar_data_calibracao(root,infomacoes)
    root.append(tipo_transmissor_pressao(infomacoes))
    
    

    calibracoes = ET.SubElement(root, "CALIBRACOES")
    unidade_eng = definir_unidade_eng(pontos.get("categoria", ""))

    cal_as_found = ET.SubElement(calibracoes, "CALIBRACAO_AS_FOUND")
    cal_as_found.append(
    criar_faixa_calibrada(informacoes, unidade_eng))

    if pontos.get("tabela1") == "AS FOUND":
        cal_as_found.append(
            gerar_pontos_calibracao(
                pontos.get("results1", []),
                pontos.get("results2", []),
                unidade_eng
            )
        )

    # AS LEFT (somente se houver dados reais)
    cal_as_left = ET.SubElement(calibracoes, "CALIBRACAO_AS_LEFT")

    if pontos.get("tabela2") == "AS LEFT":
        cal_as_left.append(
            criar_faixa_calibrada(informacoes, unidade_eng)
        )
        cal_as_left.append(
            gerar_pontos_calibracao(
                pontos.get("results_left_bruto", []),
                pontos.get("results_left_resultados", []),
                unidade_eng
            )
        )

    for el in indicadores_globais(infomacoes, unidade_eng):
        root.append(el)

    return root


# =====================================================
# EXECUÇÃO
# =====================================================

if __name__ == "__main__":

    caminho_pdf = "xml_model\\24-ODS-95-PRE-974_27PT2001.pdf"

    infomacoes = extrair_campos(extrair_texto("xml_model\\24-ODS-95-PRE-974_27PT2001.pdf"))
    print(infomacoes)
    dados_tabela = processar_pdf(caminho_pdf)
    print(f'\n{dados_tabela}')
    xml_root = gerar_xml_certificado_pressao(infomacoes, dados_tabela)

    xml_bruto = ET.tostring(xml_root, encoding="utf-8")
    xml_formatado = minidom.parseString(xml_bruto).toprettyxml(indent="  ", encoding="utf-8")

    caminho_xml = gerar_caminho_xml(caminho_pdf)
    with open(caminho_xml, "wb") as f:
        f.write(xml_formatado)

    print("XML gerado com sucesso em:")
    print(caminho_xml)