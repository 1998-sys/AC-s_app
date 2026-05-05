import sqlite3

db_path = 'instrumentos.db'

def conectar():
    """
    Abre e retorna uma conexão com o banco de dados SQLite.
    Opens and returns a connection to the SQLite database.

    Returns:
        sqlite3.Connection: Conexão ativa com o banco / Active database connection.
    """
    return sqlite3.connect(db_path)

def criar_tabela():
    """
    Cria a tabela 'instrumentos' caso ainda não exista.
    Creates the 'instrumentos' table if it does not already exist.

    Columns:
        id            (INTEGER): Chave primária autoincremental / Auto-incremented primary key.
        tag           (TEXT):    Identificador do instrumento / Instrument tag identifier.
        sn_instrumento(TEXT):    Número de série do instrumento / Instrument serial number.
        sn_sensor     (TEXT):    Número de série do sensor, opcional / Sensor serial number, optional.
        min_range     (REAL):    Valor mínimo da faixa de medição / Minimum measurement range value.
        max_range     (REAL):    Valor máximo da faixa de medição / Maximum measurement range value.
        tipo          (TEXT):    Tipo do instrumento: 'secundario' ou 'placa_orificio'.
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instrumentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            sn_instrumento TEXT NOT NULL,
            sn_sensor TEXT,
            min_range REAL,
            max_range REAL,
            tipo TEXT NOT NULL DEFAULT 'secundario'
        )
    ''')
    conn.commit()
    conn.close()


def migrar():
    """
    Aplica migrações incrementais ao banco existente.
    Adiciona a coluna 'tipo' caso ainda não exista (bancos criados antes desta versão).
    """
    conn = conectar()
    cursor = conn.cursor()
    colunas = [row[1] for row in cursor.execute("PRAGMA table_info(instrumentos)")]
    if "tipo" not in colunas:
        cursor.execute(
            "ALTER TABLE instrumentos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'secundario'"
        )
        conn.commit()
    conn.close()

