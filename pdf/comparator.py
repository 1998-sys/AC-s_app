from data.utils_db import buscar_instrumento_por_tag

def converter_instrumento_dict(row):
    """
    Docstring for converter_instrumento_dict
    
    :param row: Description
    """ 
    return {
        "tag": row[1],
        "sn_instrumento": row[2],
        "sn_sensor": row[3]
    }

def comparacao(dados_pdf):
    tag_pdf = dados_pdf.get("tag")
    sn_pdf = dados_pdf.get("sn_instrumento")

    row = buscar_instrumento_por_tag(tag_pdf)

    if not row:
        return {
            "status": "nao_encontrado",
            "mensagem": f"TAG {tag_pdf} não existe no banco."
        }
    
    instrumento = converter_instrumento_dict(row)

    # Comparar TAG e SN
    resultado = {
        "tag": {
            "pdf": tag_pdf,
            "banco": instrumento["tag"],
            "ok": tag_pdf.strip().lower() == instrumento["tag"].strip().lower()
        },
        "sn_instrumento": {
            "pdf": sn_pdf,
            "banco": instrumento["sn_instrumento"],
            "ok": str(sn_pdf).strip() == str(instrumento["sn_instrumento"]).strip()
        }
    }

    return {
        "status": "ok",
        "comparacao": resultado,
        "dados_banco": instrumento
    }
