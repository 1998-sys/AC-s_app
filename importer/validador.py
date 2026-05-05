from data.utils_db import buscar_instrumento_por_tag, buscar_por_sn_instrumento

TIPOS_VALIDOS = {"SEC", "PO"}


def _to_float(val):
    if val is None:
        return None, None
    try:
        return float(str(val).replace(",", ".")), None
    except Exception:
        return None, str(val)


def validar_linha(n, tag, sn, tipo, sn_sensor, min_raw, max_raw):
    """
    Valida uma linha do xlsx e retorna (categoria, payload).

    Categorias possíveis:
        'aviso'      — linha ignorada, motivo registrado no relatório
        'bloqueado'  — conflito crítico, não pode ser importado
        'mantido'    — registro idêntico já existe no banco
        'divergente' — TAG+tipo existem mas NS é diferente; aguarda decisão do usuário
        'inserir'    — novo registro válido pronto para inserção
    """
    # TAG ou SN vazio
    if not tag or not sn:
        return "aviso", {"linha": n, "tag": tag or "—", "sn": sn or "—",
                         "motivo": "TAG ou SN vazio"}

    # Tipo inválido
    if tipo not in TIPOS_VALIDOS:
        return "aviso", {"linha": n, "tag": tag, "sn": sn,
                         "motivo": f"Tipo inválido: '{tipo}' (use SEC ou PO)"}

    # Validações de range exclusivas para SEC
    min_range = max_range = None
    if tipo == "SEC":
        min_range, err = _to_float(min_raw)
        if err is not None:
            return "aviso", {"linha": n, "tag": tag, "sn": sn,
                             "motivo": f"min_range não numérico: '{err}'"}

        max_range, err = _to_float(max_raw)
        if err is not None:
            return "aviso", {"linha": n, "tag": tag, "sn": sn,
                             "motivo": f"max_range não numérico: '{err}'"}

        if min_range is not None and max_range is not None and min_range >= max_range:
            return "aviso", {"linha": n, "tag": tag, "sn": sn,
                             "motivo": f"min_range >= max_range ({min_range} >= {max_range})"}

    # Consultas ao banco
    reg_tag = buscar_instrumento_por_tag(tag)
    reg_sn  = buscar_por_sn_instrumento(sn)

    # NS já existe com outra TAG
    if reg_sn and reg_sn["tag"] != tag:
        return "bloqueado", {"linha": n, "tag": tag, "sn": sn,
                             "motivo": f"NS já cadastrado com TAG '{reg_sn['tag']}'"}

    if reg_tag:
        # Conflito de tipo
        if reg_tag["tipo"] != tipo:
            return "bloqueado", {"linha": n, "tag": tag, "sn": sn,
                                 "motivo": f"TAG já existe como {reg_tag['tipo']} — conflito com {tipo}"}

        # Mesmo tipo + mesmo NS → já correto
        if reg_tag["sn_instrumento"] == sn:
            return "mantido", {"linha": n, "tag": tag, "sn": sn}

        # Mesmo tipo + NS diferente → aguarda decisão
        return "divergente", {
            "linha": n, "tag": tag, "sn": sn,
            "sn_banco": reg_tag["sn_instrumento"],
            "tipo": tipo, "sn_sensor": sn_sensor,
            "min_range": min_range, "max_range": max_range,
        }

    # Novo registro
    return "inserir", {
        "linha": n, "tag": tag, "sn": sn, "tipo": tipo,
        "sn_sensor": sn_sensor, "min_range": min_range, "max_range": max_range,
    }
