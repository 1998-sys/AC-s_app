# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : importer.validador
# Created       : 04-05-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Validates a single spreadsheet row against the instrument registry, classifying it for insertion, conflict or skip.
#                 Valida uma única linha da planilha em relação ao cadastro de instrumentos, classificando-a para inserção, conflito ou descarte.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from data.utils_db import buscar_instrumento_por_tag, buscar_por_sn_instrumento

TIPOS_VALIDOS = {"SEC", "PO"}


def _to_float(val):
    """Converts `val` to float, accepting a decimal comma.

    Returns:
        tuple: (converted value, None) on success; (None, original text) if the
        conversion fails; (None, None) if `val` is None.
    """
    if val is None:
        return None, None
    try:
        return float(str(val).replace(",", ".")), None
    except Exception:
        return None, str(val)


def validar_linha(n, tag, sn, tipo, sn_sensor, min_raw, max_raw,
                  sistema=None, aplicacao=None, ativo=None):
    """Validates a row from the import spreadsheet against the instrument registry.

    Args:
        n: row number in the spreadsheet (used only to build the return payload).
        tag: instrument TAG.
        sn: instrument serial number.
        tipo: instrument type ("SEC" or "PO").
        sn_sensor: sensor serial number (applicable only to SEC).
        min_raw: raw value (str) of the minimum range (applicable only to SEC).
        max_raw: raw value (str) of the maximum range (applicable only to SEC).
        sistema: system associated with the instrument, if provided.
        aplicacao: application associated with the instrument, if provided.
        ativo: instrument's "ativo" (active) field, if provided.

    Returns:
        tuple: (categoria, payload), where categoria is one of the strings below and
        payload is a dict with the row data, whose content varies according to the category:

        - "aviso": row ignored, with "motivo" (reason) recorded for the report.
        - "bloqueado": critical conflict, cannot be imported.
        - "mantido": identical record already exists in the database.
        - "divergente": TAG+type exist but the SN is different; awaits user decision.
        - "mvs_candidato": SN already belongs to another TAG; may be an MVS pending confirmation.
        - "inserir": new valid record, ready for insertion.
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

    # TAG já existe no banco — resolve pelo registro da TAG (ignorando NS de outros)
    if reg_tag:
        # Conflito de tipo
        if reg_tag["tipo"] != tipo and reg_tag["tipo"] != "MVS":
            return "bloqueado", {"linha": n, "tag": tag, "sn": sn,
                                 "motivo": f"TAG já existe como {reg_tag['tipo']} — conflito com {tipo}"}

        # Mesmo NS → já correto
        if reg_tag["sn_instrumento"] == sn:
            return "mantido", {"linha": n, "tag": tag, "sn": sn}

        # NS diferente → aguarda decisão do usuário
        return "divergente", {
            "linha": n, "tag": tag, "sn": sn,
            "sn_banco": reg_tag["sn_instrumento"],
            "tipo": tipo, "sn_sensor": sn_sensor,
            "min_range": min_range, "max_range": max_range,
            "sistema": sistema, "aplicacao": aplicacao, "ativo": ativo,
        }

    # TAG nova: verifica se NS já pertence a outra TAG → candidato a MVS
    if reg_sn and reg_sn["tag"] != tag:
        return "mvs_candidato", {
            "linha": n, "tag": tag, "sn": sn, "tipo": tipo,
            "sn_sensor": sn_sensor, "min_range": min_range, "max_range": max_range,
            "sistema": sistema, "aplicacao": aplicacao, "ativo": ativo,
            "tag_existente": reg_sn["tag"],
        }

    # Novo registro
    return "inserir", {
        "linha": n, "tag": tag, "sn": sn, "tipo": tipo,
        "sn_sensor": sn_sensor, "min_range": min_range, "max_range": max_range,
        "sistema": sistema, "aplicacao": aplicacao, "ativo": ativo,
    }
