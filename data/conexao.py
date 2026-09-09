# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : data.conexao
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Manages the SQLite database connection and creates/migrates the 'instrumentos' table schema.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import sqlite3
import os
from pathlib import Path

_app_dir = Path(os.getenv('APPDATA')) / 'ACs Generator'
_app_dir.mkdir(parents=True, exist_ok=True)
db_path = str(_app_dir / 'instrumentos.db')

def conectar():
    """Open and return a connection to the SQLite database located at db_path.

    Returns:
        sqlite3.Connection: Active connection to the database.
    """
    return sqlite3.connect(db_path)

def criar_tabela():
    """Create the 'instrumentos' table if it does not exist yet, with the base columns (id, tag, sn_instrumento, sn_sensor, min_range, max_range, tipo).

    Notes:
        Columns added in later versions of the schema (sistema, aplicacao, etc.)
        are not part of this CREATE TABLE — they are added by migrar().
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
    """Apply incremental migrations to the existing database, adding new columns and normalizing legacy 'tipo' values.

    Notes:
        Each ADD COLUMN block is idempotent: it only runs if the column does not
        exist yet, allowing migrar() to be safely called on every application startup.
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
    if "data_calibracao" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN data_calibracao TEXT")
    if "proxima_calibracao" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN proxima_calibracao TEXT")
    if "numero_certificado" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN numero_certificado TEXT")
    if "laboratorio" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN laboratorio TEXT")
    if "observacoes" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN observacoes TEXT")
    if "modificado_por" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN modificado_por TEXT")
    if "modificado_em" not in colunas:
        cursor.execute("ALTER TABLE instrumentos ADD COLUMN modificado_em TEXT")

    # Normalize legacy values to the current abbreviations
    cursor.execute("UPDATE instrumentos SET tipo = 'SEC' WHERE tipo = 'secundario'")
    cursor.execute("UPDATE instrumentos SET tipo = 'PO'  WHERE tipo = 'placa_orificio'")
    conn.commit()
    conn.close()

