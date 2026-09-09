# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : importer.validador
# Created       : 04-05-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Validates a single spreadsheet row against the instrument registry, classifying it for insertion, conflict or skip.
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
    # Empty TAG or SN
    if not tag or not sn:
        return "aviso", {"linha": n, "tag": tag or "—", "sn": sn or "—",
                         "motivo": "TAG ou SN vazio"}

    # Invalid type
    if tipo not in TIPOS_VALIDOS:
        return "aviso", {"linha": n, "tag": tag, "sn": sn,
                         "motivo": f"Tipo inválido: '{tipo}' (use SEC ou PO)"}

    # Range validations exclusive to SEC
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

    # Database lookups
    reg_tag = buscar_instrumento_por_tag(tag)
    reg_sn  = buscar_por_sn_instrumento(sn)

    # TAG already exists in the database — resolve using the TAG's record (ignoring other SNs)
    if reg_tag:
        # Type conflict
        if reg_tag["tipo"] != tipo and reg_tag["tipo"] != "MVS":
            return "bloqueado", {"linha": n, "tag": tag, "sn": sn,
                                 "motivo": f"TAG já existe como {reg_tag['tipo']} — conflito com {tipo}"}

        # Same SN → already correct
        if reg_tag["sn_instrumento"] == sn:
            return "mantido", {"linha": n, "tag": tag, "sn": sn}

        # Different SN → awaits user decision
        return "divergente", {
            "linha": n, "tag": tag, "sn": sn,
            "sn_banco": reg_tag["sn_instrumento"],
            "tipo": tipo, "sn_sensor": sn_sensor,
            "min_range": min_range, "max_range": max_range,
            "sistema": sistema, "aplicacao": aplicacao, "ativo": ativo,
        }

    # New TAG: check whether the SN already belongs to another TAG → MVS candidate
    if reg_sn and reg_sn["tag"] != tag:
        return "mvs_candidato", {
            "linha": n, "tag": tag, "sn": sn, "tipo": tipo,
            "sn_sensor": sn_sensor, "min_range": min_range, "max_range": max_range,
            "sistema": sistema, "aplicacao": aplicacao, "ativo": ativo,
            "tag_existente": reg_sn["tag"],
        }

    # New record
    return "inserir", {
        "linha": n, "tag": tag, "sn": sn, "tipo": tipo,
        "sn_sensor": sn_sensor, "min_range": min_range, "max_range": max_range,
        "sistema": sistema, "aplicacao": aplicacao, "ativo": ativo,
    }
