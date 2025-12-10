from data.conexao import conectar

def inserir_instrumento(tag, sn_instrumento, sn_sensor=None, min_range=None, max_range=None):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO instrumentos (tag, sn_instrumento, sn_sensor, min_range, max_range)
        VALUES (?, ?, ?,?, ?)
    ''', (tag, sn_instrumento, sn_sensor, min_range, max_range))
    conn.commit()
    conn.close()


def buscar_instrumento_por_tag(tag):
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

    # row = (tag, sn_instrumento, sn_sensor)
    return {
        "tag": row[0],
        "sn_instrumento": row[1],
        "sn_sensor": row[2],
        "min_range": row[3],
        'max_range': row[4]
    }

def atualizar_sn(tag, novo_sn):
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
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE instrumentos
        SET min_range = ?, max_range = ?
        WHERE tag = ?
    """, (min_range, max_range, tag))

    conn.commit()
    conn.close()