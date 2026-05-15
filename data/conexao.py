import sqlite3
import os
from pathlib import Path

_app_dir = Path(os.getenv('APPDATA')) / 'ACs Generator'
_app_dir.mkdir(parents=True, exist_ok=True)
db_path = str(_app_dir / 'instrumentos.db')

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
        tipo          (TEXT):    Tipo do instrumento: 'SEC' (secundário) ou 'PO' (placa de orifício).
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
            tipo TEXT NOT NULL DEFAULT 'SEC'
        )
    ''')
    conn.commit()
    conn.close()


def migrar():
    """
    Aplica migrações incrementais ao banco existente.
    Cada bloco ADD COLUMN é idempotente: só executa se a coluna ainda não existir.
    """
    conn = conectar()
    cursor = conn.cursor()
    colunas = [row[1] for row in cursor.execute("PRAGMA table_info(instrumentos)")]

    if "tipo" not in colunas:
        cursor.execute(
            "ALTER TABLE instrumentos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'SEC'"
        )
    if "sistema" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN sistema TEXT")
    if "aplicacao" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN aplicacao TEXT")
    if "ativo" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN ativo TEXT")

    # Normaliza valores legados para as abreviações atuais
    cursor.execute("UPDATE instrumentos SET tipo = 'SEC' WHERE tipo = 'secundario'")
    cursor.execute("UPDATE instrumentos SET tipo = 'PO'  WHERE tipo = 'placa_orificio'")
    conn.commit()
    conn.close()

