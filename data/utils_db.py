# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : data.utils_db
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Database access layer with helper functions to insert, search and update instrument
#                 and calibration records across the 'instrumentos'/'calibracoes' tables.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from contextlib import closing
from datetime import date, datetime

from data.conexao import conectar

_CAMPOS_DATA = {"data_calibracao", "proxima_calibracao"}
_CAMPOS_DATETIME = {"modificado_em"}


def _parse_data_br(valor):
    """Parse a "dd/mm/aaaa" string (as sent by the edit screen) into a date.

    Returns:
        date | None: Parsed date, or None for an empty/invalid string (stored
        as SQL NULL — the screen's text inputs are read-only and only ever
        hold either an empty string or a value this app itself wrote there).
    """
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_datetime_br(valor):
    """Parse a "dd/mm/aaaa HH:MM" string into a datetime, same rules as `_parse_data_br`."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%d/%m/%Y %H:%M")
    except ValueError:
        return None


def _formatar_data_br(valor):
    """Format a date/datetime value back into "dd/mm/aaaa" for the edit screen; "" if None."""
    if valor is None:
        return ""
    return valor.strftime("%d/%m/%Y")


def _formatar_datetime_br(valor):
    """Format a datetime value back into "dd/mm/aaaa HH:MM" for the edit screen; "" if None."""
    if valor is None:
        return ""
    return valor.strftime("%d/%m/%Y %H:%M")


def _converter_campos_cadastro_para_sql(campos):
    """Convert the "dd/mm/aaaa"[ HH:MM] strings of date/datetime fields to date/datetime objects.

    Args:
        campos: dict of field=value pairs, as received from `atualizar_dados_cadastro`.

    Returns:
        dict: Same keys, with `_CAMPOS_DATA`/`_CAMPOS_DATETIME` values parsed.
    """
    convertido = dict(campos)
    for campo in _CAMPOS_DATA & convertido.keys():
        convertido[campo] = _parse_data_br(convertido[campo])
    for campo in _CAMPOS_DATETIME & convertido.keys():
        convertido[campo] = _parse_datetime_br(convertido[campo])
    return convertido


def _query_one(sql, params=()):
    """Run a SELECT and return the first matching row (or None), always closing the connection afterwards.

    Args:
        sql: SQL statement to execute.
        params: Positional parameters for the SQL statement.

    Returns:
        tuple | None: First row of the result, or None if no row is found.
    """
    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()


def _query_all(sql, params=()):
    """Run a SELECT and return all matching rows, always closing the connection afterwards.

    Args:
        sql: SQL statement to execute.
        params: Positional parameters for the SQL statement.

    Returns:
        list[tuple]: All rows of the result (empty list if none are found).
    """
    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def _execute(sql, params=()):
    """Run an INSERT/UPDATE, commit, and always close the connection, even on error.

    Args:
        sql: SQL statement to execute.
        params: Positional parameters for the SQL statement.
    """
    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()


def _instrumento_ativo(tag, tipo=None):
    """Look up the currently active row (em_uso = TRUE) of an instrument/plate identified by its tag.

    Args:
        tag: Instrument/plate identifier.
        tipo: If given, also filters by 'tipo' (e.g. 'PO' for plates).

    Returns:
        tuple | None: (id, sn_instrumento, tipo, sistema, aplicacao, ativo) of the active
        row, or None if there isn't one.
    """
    sql = """
        SELECT id, sn_instrumento, tipo, sistema, aplicacao, ativo
        FROM instrumentos
        WHERE tag = %s AND em_uso = TRUE
    """
    params = [tag]
    if tipo is not None:
        sql += " AND tipo = %s"
        params.append(tipo)

    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()


def _calibracao_mais_recente_id(instrumento_id):
    """Look up the id of the most recent calibration row of an instrument.

    Args:
        instrumento_id: id of the row in 'instrumentos'.

    Returns:
        int | None: id of the most recent row in 'calibracoes', or None if there is none.
    """
    row = _query_one("""
        SELECT id
        FROM calibracoes
        WHERE instrumento_id = %s
        ORDER BY data_calibracao DESC NULLS LAST, id DESC
        LIMIT 1
    """, (instrumento_id,))
    return row[0] if row else None


def _trocar_unidade_ativa(tag, novo_sn, tipo_filtro=None):
    """Swap the active unit (em_uso = TRUE) of a tag to a different serial number.

    Args:
        tag: Instrument/plate identifier.
        novo_sn: Serial number of the unit that should become active.
        tipo_filtro: If given, restricts the lookup of the currently active row to this 'tipo'.

    Notes:
        - If the currently active row already has sn_instrumento == novo_sn, does nothing.
        - If a row for (tag, novo_sn) already exists (a previously known unit being
          reinstalled), that row is reactivated.
        - Otherwise, a new row is inserted for (tag, novo_sn), copying tipo/sistema/
          aplicacao/ativo from the row that is being deactivated.
        - If there is no currently active row (instrument not registered yet), does
          nothing: creating a brand new instrument from scratch is the responsibility
          of inserir_instrumento()/inserir_placa(), not of this helper.
    """
    ativo_atual = _instrumento_ativo(tag, tipo_filtro)
    if ativo_atual and ativo_atual[1] == novo_sn:
        return

    existente = _query_one("""
        SELECT id FROM instrumentos WHERE tag = %s AND sn_instrumento = %s
    """, (tag, novo_sn))

    agora = datetime.now()

    with closing(conectar()) as conn:
        cur = conn.cursor()

        if ativo_atual:
            cur.execute("""
                UPDATE instrumentos
                SET em_uso = FALSE, modificado_em = %s
                WHERE id = %s
            """, (agora, ativo_atual[0]))

        if existente:
            cur.execute("""
                UPDATE instrumentos
                SET em_uso = TRUE, modificado_em = %s
                WHERE id = %s
            """, (agora, existente[0]))
        elif ativo_atual:
            cur.execute("""
                INSERT INTO instrumentos (tag, sn_instrumento, tipo, sistema, aplicacao, ativo, em_uso, modificado_em)
                SELECT tag, %s, tipo, sistema, aplicacao, ativo, TRUE, %s
                FROM instrumentos
                WHERE id = %s
            """, (novo_sn, agora, ativo_atual[0]))

        conn.commit()


def inserir_instrumento(tag, sn_instrumento, sn_sensor=None, min_range=None, max_range=None,
                        sistema=None, aplicacao=None, ativo=None, tipo='SEC'):
    """Insert an instrument into the 'instrumentos' table (and its initial calibration data, if given).

    Args:
        tag: Instrument identifier.
        sn_instrumento: Instrument serial number.
        sn_sensor: Sensor serial number, when applicable.
        min_range: Minimum value of the measurement range.
        max_range: Maximum value of the measurement range.
        sistema: System the instrument belongs to.
        aplicacao: Instrument's application.
        ativo: Plant asset/tag associated with the instrument.
        tipo: Instrument type ('SEC' for secondary, by default).

    Notes:
        A row is also inserted into 'calibracoes' when sn_sensor, min_range or
        max_range is given, so this initial reading isn't lost.
    """
    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO instrumentos (tag, sn_instrumento, tipo, sistema, aplicacao, ativo, em_uso)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id
        ''', (tag, sn_instrumento, tipo, sistema, aplicacao, ativo))
        instrumento_id = cur.fetchone()[0]

        if sn_sensor is not None or min_range is not None or max_range is not None:
            cur.execute('''
                INSERT INTO calibracoes (instrumento_id, sn_sensor, min_range, max_range)
                VALUES (%s, %s, %s, %s)
            ''', (instrumento_id, sn_sensor, min_range, max_range))

        conn.commit()


def inserir_placa(tag, sn_instrumento, sistema=None, aplicacao=None, ativo=None):
    """Insert an orifice plate into the 'instrumentos' table (fixed type 'PO').

    Args:
        tag: Plate identifier.
        sn_instrumento: Plate serial number.
        sistema: System the plate belongs to.
        aplicacao: Plate's application.
        ativo: Plant asset/tag associated with the plate.
    """
    _execute('''
        INSERT INTO instrumentos (tag, sn_instrumento, tipo, sistema, aplicacao, ativo, em_uso)
        VALUES (%s, %s, 'PO', %s, %s, %s, TRUE)
    ''', (tag, sn_instrumento, sistema, aplicacao, ativo))


_CAMPOS_PLACA_PERMITIDOS = {"tag", "sn_instrumento"}


def buscar_placa_por_campo(coluna, valor):
    """Look up an orifice plate (type 'PO') by 'tag' or 'sn_instrumento'.

    Args:
        coluna: Name of the column to search; must be in _CAMPOS_PLACA_PERMITIDOS.
        valor: Value to look for in the given column.

    Returns:
        dict | None: {'tag', 'sn_instrumento'} of the plate found, or None if not found.

    Raises:
        ValueError: If `coluna` is not among the allowed fields.
    """
    if coluna not in _CAMPOS_PLACA_PERMITIDOS:
        raise ValueError(f"Campo não permitido: {coluna}")

    row = _query_one(f"""
        SELECT tag, sn_instrumento
        FROM instrumentos
        WHERE {coluna} = %s AND tipo = 'PO'
    """, (valor,))

    if not row:
        return None
    return {"tag": row[0], "sn_instrumento": row[1]}


def buscar_placa_por_sn(sn):
    """Look up an orifice plate by its serial number (typical use: plates without a registered TAG).

    Returns:
        dict | None: {'tag', 'sn_instrumento'} of the plate found, or None if not found.
    """
    return buscar_placa_por_campo("sn_instrumento", sn)


def buscar_placas_por_tag(tag):
    """Look up all orifice plates registered under a tag (a tag may have more than one
    registered serial number, e.g. a reserve/spare plate used in rotation).

    Args:
        tag: Plate identifier.

    Returns:
        list[dict]: {'tag', 'sn_instrumento'} of every plate found for that tag (empty
        list if none is registered).
    """
    rows = _query_all("""
        SELECT tag, sn_instrumento
        FROM instrumentos
        WHERE tag = %s AND tipo = 'PO'
    """, (tag,))
    return [{"tag": r[0], "sn_instrumento": r[1]} for r in rows]


def atualizar_sn_placa(tag, novo_sn):
    """Update the active serial number of an orifice plate (type 'PO') identified by its tag.

    Args:
        tag: Plate identifier.
        novo_sn: New serial number.

    Notes:
        Swaps which row is active (em_uso = TRUE) for this tag: the previously
        active unit is deactivated (becomes a reserve) and the unit with
        sn_instrumento == novo_sn becomes active, being created if it doesn't
        exist yet for this tag.
    """
    _trocar_unidade_ativa(tag, novo_sn, tipo_filtro='PO')


def buscar_instrumento_por_tag(tag):
    """Look up an instrument by its identifying tag, returning all registered fields (including calibration data and extended registration data).

    Args:
        tag: Instrument identifier.

    Returns:
        dict | None: Dictionary with all fields of the instrument, or None if not found.

    Notes:
        Only the currently active row (em_uso = TRUE) is considered. Calibration
        fields come from the instrument's most recent row in 'calibracoes' and are
        None when the instrument doesn't have any calibration registered yet.
    """
    row = _query_one("""
        SELECT i.tag, i.sn_instrumento, c.sn_sensor, c.min_range, c.max_range, i.tipo, i.sistema, i.aplicacao, i.ativo,
               c.data_calibracao, c.proxima_calibracao, c.numero_certificado, c.laboratorio, c.observacoes,
               c.modificado_por, c.modificado_em
        FROM instrumentos i
        LEFT JOIN calibracoes c ON c.id = (
            SELECT id FROM calibracoes WHERE instrumento_id = i.id ORDER BY data_calibracao DESC NULLS LAST, id DESC LIMIT 1
        )
        WHERE i.tag = %s AND i.em_uso = TRUE
    """, (tag,))

    if not row:
        return None

    return {
        "tag": row[0],
        "sn_instrumento": row[1],
        "sn_sensor": row[2],
        "min_range": row[3],
        "max_range": row[4],
        "tipo": row[5] or "SEC",
        "sistema": row[6],
        "aplicacao": row[7],
        "ativo": row[8],
        "data_calibracao": _formatar_data_br(row[9]),
        "proxima_calibracao": _formatar_data_br(row[10]),
        "numero_certificado": row[11],
        "laboratorio": row[12],
        "observacoes": row[13],
        "modificado_por": row[14],
        "modificado_em": _formatar_datetime_br(row[15]),
    }


def atualizar_sn(tag, novo_sn):
    """Update the active serial number of the instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        novo_sn: New serial number.

    Notes:
        Swaps which row is active (em_uso = TRUE) for this tag: the previously
        active unit is deactivated (becomes a reserve) and the unit with
        sn_instrumento == novo_sn becomes active, being created if it doesn't
        exist yet for this tag.
    """
    _trocar_unidade_ativa(tag, novo_sn, tipo_filtro=None)


def atualizar_sn_sensor(tag, novo_sn_sensor):
    """Update the sensor serial number of an instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        novo_sn_sensor: New sensor serial number.

    Notes:
        Updates the sn_sensor of the instrument's most recent calibration row, or
        inserts a new calibration row if none exists yet. Does nothing if the tag
        doesn't match any active instrument.
    """
    ativo = _instrumento_ativo(tag)
    if not ativo:
        return

    instrumento_id = ativo[0]
    calibracao_id = _calibracao_mais_recente_id(instrumento_id)

    if calibracao_id:
        _execute("""
            UPDATE calibracoes
            SET sn_sensor = %s
            WHERE id = %s
        """, (novo_sn_sensor, calibracao_id))
    else:
        _execute("""
            INSERT INTO calibracoes (instrumento_id, sn_sensor)
            VALUES (%s, %s)
        """, (instrumento_id, novo_sn_sensor))


_CAMPOS_INSTRUMENTO_PERMITIDOS = {"sn_instrumento", "sn_sensor"}


def buscar_por_campo(coluna, valor):
    """Look up an instrument by 'sn_instrumento' or 'sn_sensor'.

    Args:
        coluna: Name of the column to search; must be in _CAMPOS_INSTRUMENTO_PERMITIDOS.
        valor: Value to look for in the given column.

    Returns:
        dict | None: {'tag', 'sn_instrumento', 'sn_sensor'} of the instrument found, or None.

    Raises:
        ValueError: If `coluna` is not among the allowed fields.
    """
    if coluna not in _CAMPOS_INSTRUMENTO_PERMITIDOS:
        raise ValueError(f"Campo não permitido: {coluna}")

    if coluna == "sn_instrumento":
        row = _query_one("""
            SELECT i.tag, i.sn_instrumento, c.sn_sensor
            FROM instrumentos i
            LEFT JOIN calibracoes c ON c.id = (
                SELECT id FROM calibracoes WHERE instrumento_id = i.id ORDER BY data_calibracao DESC NULLS LAST, id DESC LIMIT 1
            )
            WHERE i.sn_instrumento = %s
            LIMIT 1
        """, (valor,))
    else:
        row = _query_one("""
            SELECT i.tag, i.sn_instrumento, c.sn_sensor
            FROM calibracoes c
            JOIN instrumentos i ON i.id = c.instrumento_id
            WHERE c.sn_sensor = %s
            ORDER BY c.data_calibracao DESC NULLS LAST, c.id DESC
            LIMIT 1
        """, (valor,))

    if not row:
        return None

    return {
        "tag": row[0],
        "sn_instrumento": row[1],
        "sn_sensor": row[2],
    }


def buscar_por_sn_instrumento(sn):
    """Look up an instrument by its instrument serial number.

    Args:
        sn: Instrument serial number.

    Returns:
        dict | None: {'tag', 'sn_instrumento', 'sn_sensor'} of the instrument found, or None.
    """
    return buscar_por_campo("sn_instrumento", sn)


def buscar_por_sn_sensor(sn_sensor):
    """Look up an instrument by its sensor serial number.

    Args:
        sn_sensor: Sensor serial number.

    Returns:
        dict | None: {'tag', 'sn_instrumento', 'sn_sensor'} of the instrument found, or None.
    """
    return buscar_por_campo("sn_sensor", sn_sensor)


def listar_todos():
    """Return all instruments in the database (basic fields), ordered by tag.

    Returns:
        list[dict]: One dictionary per instrument, with tag, sn_instrumento, tipo, sn_sensor,
        min_range, max_range, sistema, aplicacao and ativo.

    Notes:
        Returns every row (active and reserve/retired), not only em_uso = TRUE ones.
    """
    rows = _query_all("""
        SELECT i.tag, i.sn_instrumento, i.tipo, c.sn_sensor, c.min_range, c.max_range,
               i.sistema, i.aplicacao, i.ativo
        FROM instrumentos i
        LEFT JOIN calibracoes c ON c.id = (
            SELECT id FROM calibracoes WHERE instrumento_id = i.id ORDER BY data_calibracao DESC NULLS LAST, id DESC LIMIT 1
        )
        ORDER BY i.tag
    """)
    return [
        {
            "tag": r[0], "sn_instrumento": r[1], "tipo": r[2],
            "sn_sensor": r[3], "min_range": r[4], "max_range": r[5],
            "sistema": r[6], "aplicacao": r[7], "ativo": r[8],
        }
        for r in rows
    ]


def atualizar_tag(sn_instrumento, nova_tag):
    """Update the tag of an instrument identified by its serial number.

    Args:
        sn_instrumento: Instrument serial number.
        nova_tag: New identifying tag.

    Notes:
        Only the currently active row (em_uso = TRUE) is updated.
    """
    _execute("""
        UPDATE instrumentos
        SET tag = %s
        WHERE sn_instrumento = %s AND em_uso = TRUE
    """, (nova_tag, sn_instrumento))


def registrar_calibracao(tag, numero_certificado, sn_sensor=None, min_range=None, max_range=None,
                          laboratorio=None, data_calibracao=None, proxima_calibracao=None,
                          modificado_por=None, modificado_em=None):
    """Append a new calibration record for the tag's currently active instrument.

    Args:
        tag: Instrument/plate identifier.
        numero_certificado: Certificate number, as read from the processed PDF.
        sn_sensor: Sensor serial number reported on the certificate, if any.
        min_range: Minimum value of the calibrated range, if any.
        max_range: Maximum value of the calibrated range, if any.
        laboratorio: Calibration laboratory, if known (certificates don't carry
            this as a normalized field today; pass None to leave it for later
            manual entry on the edit screen).
        data_calibracao: Calibration date, "dd/mm/aaaa" (as extracted from the certificate).
        proxima_calibracao: Next calibration due date, "dd/mm/aaaa".
        modificado_por: User who triggered this registration.
        modificado_em: Timestamp of this registration, "dd/mm/aaaa HH:MM".

    Notes:
        Unlike atualizar_dados_cadastro (which edits the instrument's latest
        calibration row in place, for the manual registration screen), this
        always INSERTs a new row — 'calibracoes' is meant to be a true,
        append-only history. It is a no-op if a row for this exact
        (active instrument, numero_certificado) pair already exists, so
        reprocessing/regenerating the same certificate doesn't duplicate
        history, and a no-op if the tag has no active instrument registered
        yet (registering a brand new instrument from scratch remains a
        separate, explicit user action, not something this function does).
    """
    ativo = _instrumento_ativo(tag)
    if not ativo:
        return

    instrumento_id = ativo[0]

    if numero_certificado:
        existente = _query_one("""
            SELECT id FROM calibracoes WHERE instrumento_id = %s AND numero_certificado = %s
        """, (instrumento_id, numero_certificado))
        if existente:
            return

    _execute("""
        INSERT INTO calibracoes (
            instrumento_id, sn_sensor, min_range, max_range, numero_certificado,
            laboratorio, data_calibracao, proxima_calibracao, modificado_por, modificado_em
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        instrumento_id, sn_sensor, min_range, max_range, numero_certificado, laboratorio,
        _parse_data_br(data_calibracao), _parse_data_br(proxima_calibracao),
        modificado_por, _parse_datetime_br(modificado_em),
    ))


def atualizar_range(tag, min_range, max_range):
    """Update the measurement range of an instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        min_range: New minimum value of the range.
        max_range: New maximum value of the range.

    Notes:
        Updates min_range/max_range of the instrument's most recent calibration
        row, or inserts a new calibration row if none exists yet. Does nothing if
        the tag doesn't match any active instrument.
    """
    ativo = _instrumento_ativo(tag)
    if not ativo:
        return

    instrumento_id = ativo[0]
    calibracao_id = _calibracao_mais_recente_id(instrumento_id)

    if calibracao_id:
        _execute("""
            UPDATE calibracoes
            SET min_range = %s, max_range = %s
            WHERE id = %s
        """, (min_range, max_range, calibracao_id))
    else:
        _execute("""
            INSERT INTO calibracoes (instrumento_id, min_range, max_range)
            VALUES (%s, %s, %s)
        """, (instrumento_id, min_range, max_range))


_CAMPOS_EXTRAS_PERMITIDOS = {"sistema", "aplicacao", "ativo"}


def atualizar_campos_extras(tag, sistema=None, aplicacao=None, ativo=None):
    """Update sistema, aplicacao and/or ativo of an instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        sistema: New value for sistema, or None to leave it unchanged.
        aplicacao: New value for aplicacao, or None to leave it unchanged.
        ativo: New value for ativo, or None to leave it unchanged.

    Notes:
        Only the non-None fields received are overwritten; if none are given,
        the function does not execute any SQL statement. Only the currently
        active row (em_uso = TRUE) is updated.
    """
    campos = {}
    if sistema is not None:
        campos["sistema"] = sistema
    if aplicacao is not None:
        campos["aplicacao"] = aplicacao
    if ativo is not None:
        campos["ativo"] = ativo
    if not campos:
        return

    if not set(campos).issubset(_CAMPOS_EXTRAS_PERMITIDOS):
        raise ValueError(f"Campo(s) não permitido(s): {set(campos) - _CAMPOS_EXTRAS_PERMITIDOS}")

    sets = ", ".join(f"{c} = %s" for c in campos)
    _execute(
        f"UPDATE instrumentos SET {sets} WHERE tag = %s AND em_uso = TRUE",
        (*campos.values(), tag)
    )


_CAMPOS_CADASTRO_PERMITIDOS = {
    "data_calibracao", "proxima_calibracao", "numero_certificado",
    "laboratorio", "observacoes", "modificado_por", "modificado_em",
}


def atualizar_dados_cadastro(tag, **campos):
    """Update the extended registration fields (calibration, certificate, laboratory, remarks, last-change metadata) of an instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        **campos: field=value pairs to update; must be in _CAMPOS_CADASTRO_PERMITIDOS.
            Fields with a None value are ignored (they do not overwrite the current value).

    Raises:
        ValueError: If any given field is not among the allowed fields.

    Notes:
        These fields now live in 'calibracoes'. Updates the instrument's most
        recent calibration row, or inserts a new calibration row if none exists
        yet. Does nothing if the tag doesn't match any active instrument.
    """
    campos = {k: v for k, v in campos.items() if v is not None}
    if not campos:
        return

    if not set(campos).issubset(_CAMPOS_CADASTRO_PERMITIDOS):
        raise ValueError(f"Campo(s) não permitido(s): {set(campos) - _CAMPOS_CADASTRO_PERMITIDOS}")

    campos = _converter_campos_cadastro_para_sql(campos)

    ativo = _instrumento_ativo(tag)
    if not ativo:
        return

    instrumento_id = ativo[0]
    calibracao_id = _calibracao_mais_recente_id(instrumento_id)

    if calibracao_id:
        sets = ", ".join(f"{c} = %s" for c in campos)
        _execute(
            f"UPDATE calibracoes SET {sets} WHERE id = %s",
            (*campos.values(), calibracao_id)
        )
    else:
        colunas = ", ".join(campos.keys())
        placeholders = ", ".join(["%s"] * len(campos))
        _execute(
            f"INSERT INTO calibracoes (instrumento_id, {colunas}) VALUES (%s, {placeholders})",
            (instrumento_id, *campos.values())
        )
