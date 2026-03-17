import re
from pdf.extrator import extrair_texto
from pdf.parser_certificados import (extrair_certificado, extrair_datas, extrair_nome_cliente, endereco_cliente, extrair_local,
SIGNATARIOS_VALIDOS, extrair_assinaturas, separar_signatario, extrair_condicoes_ambientais, extrair_padroes, extrair_sn,
obter_procedimento_por_categoria)



def extrair_item(texto):
   
    matches = re.findall(r'Item:\s*(.+)', texto, re.IGNORECASE)
    if not matches:
        return None
    if len(matches) >= 2:
        return matches[1].strip()
    return matches[0].strip()

def material(texto):
    padrao = r"Material:[ \t]*([^\n\r-]+)"
    matches = re.findall(padrao, texto)
    return matches[-1].strip() if matches else None

def coeficiente_dilatacao(texto):
    padrao = r"Coefficient:\s*([0-9.,]+)"
    m = re.search(padrao, texto, re.IGNORECASE)
    
    if m:
        valor = m.group(1).strip()
        return valor.replace(",", ".")
    
    return None

def diametro_tubo(texto):
    padrao = r"Nominal Pipe Ø \(Dm\):[ \t]*([0-9]+[.,][0-9]+)"
    m = re.search(padrao, texto)
    
    if m:
        valor = m.group(1).strip()
        return valor.replace(",", ".")
    
    return None

def tag_placa(texto):
    padrao= r"TAG:\s*([A-Z0-9/\-\u2010\u2011\u2012\u2013\u2014]+)"
    m = re.search(padrao, texto)

    if m:
        return m.group(1).strip()

    return None

def extrair_campos_po(texto):
    inst = extrair_item(texto)
    certificado = extrair_certificado(texto)
    data_cal, report_date = extrair_datas(texto)
    nome_cliente = extrair_nome_cliente(texto)
    endereco_cli = endereco_cliente(texto)
    unidade = extrair_local(texto)
    exec_sig = separar_signatario(extrair_assinaturas(texto), SIGNATARIOS_VALIDOS)
    cond_amb = extrair_condicoes_ambientais(texto)
    padroes = extrair_padroes(texto)
    sn_inst, _ = extrair_sn(texto)
    tag = tag_placa(texto)
    material_placa = material(texto)
    coef = coeficiente_dilatacao(texto)
    diametro_t = diametro_tubo(texto)
    procediment = obter_procedimento_por_categoria(inst)

    return {
        'certificado': certificado,
        'instrumento': inst,
        'sn_inst': sn_inst,
        'data_calibracao': data_cal,
        'report_date': report_date,
        'cliente': nome_cliente,
        'endereco_cliente': endereco_cli,
        'local': unidade,
        'exec_sig': exec_sig,
        'cond_amb': cond_amb,
        'padroes_utilizados': padroes,
        'sn_inst': sn_inst,
        'tag': tag,
        'material': material_placa,
        'coef': coef,
        'norma': 'ISO 5167-2:2022',
        'diametro_tubo': diametro_t,
        'procedimento': procediment
    }

