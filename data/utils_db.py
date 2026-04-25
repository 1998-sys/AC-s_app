from data.conexao import conectar

def inserir_instrumento(tag, sn_instrumento, sn_sensor=None, min_range=None, max_range=None):
    """
    Insere um novo instrumento na tabela 'instrumentos'.
    Inserts a new instrument into the 'instrumentos' table.

    Args:
        tag           (str):   Identificador do instrumento / Instrument tag identifier.
        sn_instrumento(str):   Número de série do instrumento / Instrument serial number.
        sn_sensor     (str):   Número de série do sensor, opcional / Sensor serial number, optional.
        min_range     (float): Valor mínimo da faixa de medição / Minimum measurement range value.
        max_range     (float): Valor máximo da faixa de medição / Maximum measurement range value.
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO instrumentos (tag, sn_instrumento, sn_sensor, min_range, max_range)
        VALUES (?, ?, ?,?, ?)
    ''', (tag, sn_instrumento, sn_sensor, min_range, max_range))
    conn.commit()
    conn.close()


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
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT tag, sn_instrumento, sn_sensor, min_range, max_range
        FROM instrumentos
        WHERE tag = ?
    """, (tag,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "tag": row[0],
        "sn_instrumento": row[1],
        "sn_sensor": row[2],
        "min_range": row[3],
        'max_range': row[4]
    }

def atualizar_sn(tag, novo_sn):
    """
    Atualiza o número de série do instrumento identificado pelo tag.
    Updates the instrument serial number identified by tag.

    Args:
        tag    (str): Identificador do instrumento / Instrument tag identifier.
        novo_sn(str): Novo número de série / New serial number.
    """
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE instrumentos
        SET sn_instrumento = ?
        WHERE tag = ?
    """, (novo_sn, tag))

    conn.commit()
    conn.close()

def atualizar_sn_sensor(tag, novo_sn_sensor):
    """
    Atualiza o número de série do sensor identificado pelo tag.
    Updates the sensor serial number identified by tag.

    Args:
        tag          (str): Identificador do instrumento / Instrument tag identifier.
        novo_sn_sensor(str): Novo número de série do sensor / New sensor serial number.
    """
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE instrumentos
        SET sn_sensor = ?
        WHERE tag = ?
    """, (novo_sn_sensor, tag))

    conn.commit()
    conn.close()

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
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT tag, sn_instrumento, sn_sensor
        FROM instrumentos
        WHERE sn_instrumento = ?
    """, (sn,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "tag": row[0],
        "sn_instrumento": row[1],
        "sn_sensor": row[2]
    }


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
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT tag, sn_instrumento, sn_sensor
        FROM instrumentos
        WHERE sn_sensor = ?
    """, (sn_sensor,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "tag": row[0],
        "sn_instrumento": row[1],
        "sn_sensor": row[2]
    }


def atualizar_tag(sn_instrumento, nova_tag):
    """
    Atualiza o tag de um instrumento identificado pelo número de série.
    Updates the tag of an instrument identified by its serial number.

    Args:
        sn_instrumento(str): Número de série do instrumento / Instrument serial number.
        nova_tag      (str): Novo tag identificador / New tag identifier.
    """
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE instrumentos
        SET tag = ?
        WHERE sn_instrumento = ?
    """, (nova_tag, sn_instrumento))

    conn.commit()
    conn.close()


def atualizar_range(tag, min_range, max_range):
    """
    Atualiza a faixa de medição de um instrumento identificado pelo tag.
    Updates the measurement range of an instrument identified by tag.

    Args:
        tag      (str):   Identificador do instrumento / Instrument tag identifier.
        min_range(float): Novo valor mínimo da faixa / New minimum range value.
        max_range(float): Novo valor máximo da faixa / New maximum range value.
    """
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE instrumentos
        SET min_range = ?, max_range = ?
        WHERE tag = ?
    """, (min_range, max_range, tag))

    conn.commit()
    conn.close()
