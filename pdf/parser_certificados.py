import re
from pdf.extrator import extrair_texto
#from extrator import extrair_texto



def extrair_campos(texto: str) -> dict:
        # TAG — aceita todos os tipos de hífen UNICODE + espaços ao redor
    padrao_tag = r"TAG:\s*([0-9A-Za-z]+(?:\s*[-‐‒–—―]\s*[0-9A-Za-z]+)+)"
    m = re.search(padrao_tag, texto)

    if m:
        tag_val = m.group(1).strip()

        # 1) Normaliza todos os tipos de hífen Unicode para "-"
        tag_val = (
            tag_val.replace("‐", "-")
                   .replace("‒", "-")
                   .replace("–", "-")
                   .replace("—", "-")
                   .replace("―", "-")
        )

        # 2) Remove espaços antes/depois dos hífens
        tag_val = re.sub(r"\s*-\s*", "-", tag_val)

    else:
        tag_val = None

    # ---------------- resto igual ---------------- #

    encontrados = re.findall(r"(?:SN|Num\.?\s*de\s*Série):\s*([^\s]+)", texto)
    sns_validos = [s for s in encontrados if any(c.isdigit() for c in s)]

    sn_instrumento = sns_validos[0] if len(sns_validos) >= 1 else None
    sn_sensor = sns_validos[1] if len(sns_validos) >= 2 else None

    padrao_cert = r"Nº\s*([^\n]+)"
    n_cert = re.search(padrao_cert, texto)
    n_cert = n_cert.group(1).lstrip() if n_cert else None

    padrao_data = r"(Calibration Date|Data da Calibração):\s*([0-9]{2}/[0-9]{2}/[0-9]{4})"
    m_data = re.search(padrao_data, texto)
    data_calibracao = m_data.group(2) if m_data else None

    padrao_bloco_local = r"CALIBRATION LOCATION:(.*?)(?:CALIBRATED ITEM DESCRIPTION|CLIENT INFORMATION|$)"
    m_bloco = re.search(padrao_bloco_local, texto, flags=re.DOTALL)

    padrao_report_date = r"(Report Date|Data do Relatório):\s*([0-9]{2}/[0-9]{2}/[0-9]{4})"
    m_report_date = re.search(padrao_report_date, texto)
    report_date = m_report_date.group(2) if m_report_date else None

    if m_bloco:
        bloco = m_bloco.group(1)
        m_local = re.search(r"(Name|Address|Nome|Endereço):\s*([A-Za-z0-9 \-_/]+)", bloco)
        local_calibracao = m_local.group(2).strip() if m_local else None
    else:
        local_calibracao = None

    padrao_desc = (
        r"(?:System Description|Descrição do Sistema):\s*([\s\S]+?)"
        r"(?=\n(?:Name:|Address:|Calibrated|Classification|Classificação|"
        r"Periodicidade|Periodicity|Next Calibration|Próxima Calibração|"
        r"LOCAL ENVIRONMENTAL|CONDIÇÕES AMBIENTAIS|REFERENCE STANDARDS|"
        r"PADRÕES DE REFERÊNCIA|ITEM|TAG|SN))"
    )

    m_desc = re.search(padrao_desc, texto, flags=re.DOTALL)
    if m_desc:
        descricao_sistema = m_desc.group(1).strip()
        descricao_sistema = re.split(
            r"(Periodicity:|Periodicidade:|Classificação:|Classification:)",
            descricao_sistema
        )[0].strip()
        descricao_sistema = re.sub(r"\s+", " ", descricao_sistema)
    else:
        descricao_sistema = None
    
    padrao_range = r"""
    Calibration\s*Range.*?           # captura trecho 'Calibration Range'
    Min[: ]*([-+]?[0-9.,]+)          # captura APENAS o número do Min
    .*?                              # ignora unidade e qualquer outra coisa
    Max[: ]*([-+]?[0-9.,]+)          # captura APENAS o número do Max
    """
    m_range = re.search(padrao_range, texto, flags=re.IGNORECASE | re.DOTALL | re.VERBOSE)

    if m_range:
        min_kpa = m_range.group(1)
        max_kpa = m_range.group(2)
    else:
        min_kpa = None
        max_kpa = None

    # Comprimento da Haste e diâmetro da Haste

    rod_match = re.search(r"Rod length:\s*([\d,.]+)", texto)
    rod_length = rod_match.group(1).replace(",", ".") if rod_match else None

    probe_match = re.search(r"Probe diameter:\s*([\d,.]+)", texto)
    probe_diameter = probe_match.group(1).replace(",", ".") if probe_match else None
    
    

        
    return {
        "tag": tag_val,
        "sn_instrumento": sn_instrumento,
        "sn_sensor": sn_sensor,
        "certificado": n_cert,
        "data": data_calibracao,
        "local": local_calibracao,
        "sistema": descricao_sistema,
        "report_date": report_date,
        'min_range': min_kpa,
        'max_range': max_kpa,
        'rod_length': rod_length,
        'probe_diameter': probe_diameter
    }




#resultado = (extrair_tabela_referencia('assets\\25-ODS-70-PRE-408 - FIT-1231010D_SP - 28.09.pdf'))
#print(resultado)




