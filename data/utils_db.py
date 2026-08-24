from contextlib import closing
from data.conexao import conectar


def _query_one(sql, params=()):
    """Executa um SELECT e retorna a primeira linha (ou None), fechando a conexão sempre."""
    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()


def _query_all(sql, params=()):
    """Executa um SELECT e retorna todas as linhas, fechando a conexão sempre."""
    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def _execute(sql, params=()):
    """Executa um INSERT/UPDATE, faz commit e fecha a conexão sempre (mesmo em erro)."""
    with closing(conectar()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()


def inserir_instrumento(tag, sn_instrumento, sn_sensor=None, min_range=None, max_range=None,
                        sistema=None, aplicacao=None, ativo=None, tipo='SEC'):
    """
    Insere um instrumento na tabela 'instrumentos'.
    Inserts an instrument into the 'instrumentos' table.
    """
    _execute('''
        INSERT INTO instrumentos (tag, sn_instrumento, sn_sensor, min_range, max_range, tipo,
                                  sistema, aplicacao, ativo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (tag, sn_instrumento, sn_sensor, min_range, max_range, tipo, sistema, aplicacao, ativo))


def inserir_placa(tag, sn_instrumento, sistema=None, aplicacao=None, ativo=None):
    """
    Insere uma placa de orifício na tabela 'instrumentos'.
    Inserts an orifice plate into the 'instrumentos' table.
    """
    _execute('''
        INSERT INTO instrumentos (tag, sn_instrumento, tipo, sistema, aplicacao, ativo)
        VALUES (?, ?, 'PO', ?, ?, ?)
    ''', (tag, sn_instrumento, sistema, aplicacao, ativo))


_CAMPOS_PLACA_PERMITIDOS = {"tag", "sn_instrumento"}


def buscar_placa_por_campo(coluna, valor):
    """Busca uma placa de orifício por 'tag' ou 'sn_instrumento'."""
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
    """Busca uma placa de orifício pelo número de série (para placas sem TAG)."""
    return buscar_placa_por_campo("sn_instrumento", sn)


def buscar_placa_por_tag(tag):
    """
    Busca uma placa de orifício pelo tag.
    Searches for an orifice plate by tag.

    Args:
        tag (str): Identificador da placa / Orifice plate tag identifier.

    Returns:
        dict | None: {'tag', 'sn_instrumento'} ou None se não encontrada.
    """
    return buscar_placa_por_campo("tag", tag)


def atualizar_sn_placa(tag, novo_sn):
    """
    Atualiza o número de série de uma placa de orifício identificada pelo tag.
    Updates the serial number of an orifice plate identified by tag.

    Args:
        tag    (str): Identificador da placa / Orifice plate tag identifier.
        novo_sn(str): Novo número de série / New serial number.
    """
    _execute("""
        UPDATE instrumentos
        SET sn_instrumento = ?
        WHERE tag = ? AND tipo = 'PO'
    """, (novo_sn, tag))


def buscar_instrumento_por_tag(tag):
    """
    Busca um instrumento pelo seu tag identificador.
    Searches for an instrument by its tag identifier.

    Args:
        tag (str): Identificador do instrumento / Instrument tag identifier.

    Returns:
        dict | None: Dicionário com os dados do instrumento ou None se não encontrado.
                     Dictionary with instrument data or None if not found.
    """
    row = _query_one("""
        SELECT tag, sn_instrumento, sn_sensor, min_range, max_range, tipo, sistema, aplicacao, ativo
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
    }


def atualizar_sn(tag, novo_sn):
    """
    Atualiza o número de série do instrumento identificado pelo tag.
    Updates the instrument serial number identified by tag.

    Args:
        tag    (str): Identificador do instrumento / Instrument tag identifier.
        novo_sn(str): Novo número de série / New serial number.
    """
    _execute("""
        UPDATE instrumentos
        SET sn_instrumento = ?
        WHERE tag = ?
    """, (novo_sn, tag))


def atualizar_sn_sensor(tag, novo_sn_sensor):
    """
    Atualiza o número de série do sensor identificado pelo tag.
    Updates the sensor serial number identified by tag.

    Args:
        tag          (str): Identificador do instrumento / Instrument tag identifier.
        novo_sn_sensor(str): Novo número de série do sensor / New sensor serial number.
    """
    _execute("""
        UPDATE instrumentos
        SET sn_sensor = ?
        WHERE tag = ?
    """, (novo_sn_sensor, tag))


_CAMPOS_INSTRUMENTO_PERMITIDOS = {"sn_instrumento", "sn_sensor"}


def buscar_por_campo(coluna, valor):
    """Busca um instrumento por 'sn_instrumento' ou 'sn_sensor'."""
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
    """
    Busca um instrumento pelo número de série do instrumento.
    Searches for an instrument by its serial number.

    Args:
        sn (str): Número de série do instrumento / Instrument serial number.

    Returns:
        dict | None: Dicionário com os dados do instrumento ou None se não encontrado.
                     Dictionary with instrument data or None if not found.
    """
    return buscar_por_campo("sn_instrumento", sn)


def buscar_por_sn_sensor(sn_sensor):
    """
    Busca um instrumento pelo número de série do sensor.
    Searches for an instrument by its sensor serial number.

    Args:
        sn_sensor (str): Número de série do sensor / Sensor serial number.

    Returns:
        dict | None: Dicionário com os dados do instrumento ou None se não encontrado.
                     Dictionary with instrument data or None if not found.
    """
    return buscar_por_campo("sn_sensor", sn_sensor)


def listar_todos():
    """
    Retorna todos os instrumentos do banco ordenados por TAG.
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
    """
    Atualiza o tag de um instrumento identificado pelo número de série.
    Updates the tag of an instrument identified by its serial number.

    Args:
        sn_instrumento(str): Número de série do instrumento / Instrument serial number.
        nova_tag      (str): Novo tag identificador / New tag identifier.
    """
    _execute("""
        UPDATE instrumentos
        SET tag = ?
        WHERE sn_instrumento = ?
    """, (nova_tag, sn_instrumento))


def atualizar_range(tag, min_range, max_range):
    """
    Atualiza a faixa de medição de um instrumento identificado pelo tag.
    Updates the measurement range of an instrument identified by tag.

    Args:
        tag      (str):   Identificador do instrumento / Instrument tag identifier.
        min_range(float): Novo valor mínimo da faixa / New minimum range value.
        max_range(float): Novo valor máximo da faixa / New maximum range value.
    """
    _execute("""
        UPDATE instrumentos
        SET min_range = ?, max_range = ?
        WHERE tag = ?
    """, (min_range, max_range, tag))


_CAMPOS_EXTRAS_PERMITIDOS = {"sistema", "aplicacao", "ativo"}


def atualizar_campos_extras(tag, sistema=None, aplicacao=None, ativo=None):
    """
    Atualiza sistema, aplicacao e ativo de um instrumento identificado pelo tag.
    Apenas sobrescreve campos não-None recebidos.
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
