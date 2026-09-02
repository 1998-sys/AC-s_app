# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : data.utils_db
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Database access layer with helper functions to insert, search and update instrument records.
#                 Camada de acesso ao banco de dados com funções auxiliares para inserir, buscar e atualizar registros de instrumentos.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from contextlib import closing
from data.conexao import conectar


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


def inserir_instrumento(tag, sn_instrumento, sn_sensor=None, min_range=None, max_range=None,
                        sistema=None, aplicacao=None, ativo=None, tipo='SEC'):
    """Insert an instrument into the 'instrumentos' table.

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
    """
    _execute('''
        INSERT INTO instrumentos (tag, sn_instrumento, sn_sensor, min_range, max_range, tipo,
                                  sistema, aplicacao, ativo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (tag, sn_instrumento, sn_sensor, min_range, max_range, tipo, sistema, aplicacao, ativo))


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
        INSERT INTO instrumentos (tag, sn_instrumento, tipo, sistema, aplicacao, ativo)
        VALUES (?, ?, 'PO', ?, ?, ?)
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
        WHERE {coluna} = ? AND tipo = 'PO'
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


def buscar_placa_por_tag(tag):
    """Look up an orifice plate by its tag.

    Args:
        tag: Plate identifier.

    Returns:
        dict | None: {'tag', 'sn_instrumento'} of the plate found, or None if not found.
    """
    return buscar_placa_por_campo("tag", tag)


def atualizar_sn_placa(tag, novo_sn):
    """Update the serial number of an orifice plate (type 'PO') identified by its tag.

    Args:
        tag: Plate identifier.
        novo_sn: New serial number.
    """
    _execute("""
        UPDATE instrumentos
        SET sn_instrumento = ?
        WHERE tag = ? AND tipo = 'PO'
    """, (novo_sn, tag))


def buscar_instrumento_por_tag(tag):
    """Look up an instrument by its identifying tag, returning all registered fields (including calibration data and extended registration data).

    Args:
        tag: Instrument identifier.

    Returns:
        dict | None: Dictionary with all fields of the instrument, or None if not found.
    """
    row = _query_one("""
        SELECT tag, sn_instrumento, sn_sensor, min_range, max_range, tipo, sistema, aplicacao, ativo,
               data_calibracao, proxima_calibracao, numero_certificado, laboratorio, observacoes,
               modificado_por, modificado_em
        FROM instrumentos
        WHERE tag = ?
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
        "data_calibracao": row[9],
        "proxima_calibracao": row[10],
        "numero_certificado": row[11],
        "laboratorio": row[12],
        "observacoes": row[13],
        "modificado_por": row[14],
        "modificado_em": row[15],
    }


def atualizar_sn(tag, novo_sn):
    """Update the serial number of the instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        novo_sn: New serial number.
    """
    _execute("""
        UPDATE instrumentos
        SET sn_instrumento = ?
        WHERE tag = ?
    """, (novo_sn, tag))


def atualizar_sn_sensor(tag, novo_sn_sensor):
    """Update the sensor serial number of an instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        novo_sn_sensor: New sensor serial number.
    """
    _execute("""
        UPDATE instrumentos
        SET sn_sensor = ?
        WHERE tag = ?
    """, (novo_sn_sensor, tag))


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

    row = _query_one(f"""
        SELECT tag, sn_instrumento, sn_sensor
        FROM instrumentos
        WHERE {coluna} = ?
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
    """
    rows = _query_all("""
        SELECT tag, sn_instrumento, tipo, sn_sensor, min_range, max_range,
               sistema, aplicacao, ativo
        FROM instrumentos
        ORDER BY tag
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
    """
    _execute("""
        UPDATE instrumentos
        SET tag = ?
        WHERE sn_instrumento = ?
    """, (nova_tag, sn_instrumento))


def atualizar_range(tag, min_range, max_range):
    """Update the measurement range of an instrument identified by its tag.

    Args:
        tag: Instrument identifier.
        min_range: New minimum value of the range.
        max_range: New maximum value of the range.
    """
    _execute("""
        UPDATE instrumentos
        SET min_range = ?, max_range = ?
        WHERE tag = ?
    """, (min_range, max_range, tag))


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
        the function does not execute any SQL statement.
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

    sets = ", ".join(f"{c} = ?" for c in campos)
    _execute(
        f"UPDATE instrumentos SET {sets} WHERE tag = ?",
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
    """
    campos = {k: v for k, v in campos.items() if v is not None}
    if not campos:
        return

    if not set(campos).issubset(_CAMPOS_CADASTRO_PERMITIDOS):
        raise ValueError(f"Campo(s) não permitido(s): {set(campos) - _CAMPOS_CADASTRO_PERMITIDOS}")

    sets = ", ".join(f"{c} = ?" for c in campos)
    _execute(
        f"UPDATE instrumentos SET {sets} WHERE tag = ?",
        (*campos.values(), tag)
    )
