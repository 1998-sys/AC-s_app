# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : data.conexao
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Manages the Postgres (Supabase) database connection and creates/migrates
#                 the 'instrumentos'/'calibracoes' schema.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def conectar():
    """Open and return a connection to the Postgres database via SUPABASE_DB_URL.

    Returns:
        psycopg2.extensions.connection: Active connection to the database.
    """
    return psycopg2.connect(os.environ["SUPABASE_DB_URL"])


def criar_tabela():
    """Create the 'instrumentos'/'calibracoes' tables, index and vw_calibracao_atual view if they don't exist yet.

    Notes:
        'instrumentos' holds the physical identity of each unit per tag (a tag may
        have more than one row, e.g. installed unit + reserve unit, each with its
        own sn_instrumento and its own em_uso flag). 'calibracoes' is an append-only
        history table, one row per processed certificate.
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instrumentos (
            id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tag             TEXT NOT NULL,
            sn_instrumento  TEXT NOT NULL,
            tipo            TEXT NOT NULL DEFAULT 'SEC',
            sistema         TEXT,
            aplicacao       TEXT,
            ativo           TEXT,
            em_uso          BOOLEAN NOT NULL DEFAULT TRUE,
            modificado_por  TEXT,
            modificado_em   TIMESTAMPTZ,
            UNIQUE (tag, sn_instrumento)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calibracoes (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            instrumento_id      BIGINT NOT NULL REFERENCES instrumentos(id),
            sn_sensor           TEXT,
            min_range           NUMERIC,
            max_range           NUMERIC,
            numero_certificado  TEXT,
            laboratorio         TEXT,
            data_calibracao     DATE,
            proxima_calibracao  DATE,
            observacoes         TEXT,
            modificado_por      TEXT,
            modificado_em       TIMESTAMPTZ
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibracoes_instrumento_data
        ON calibracoes (instrumento_id, data_calibracao DESC)
    ''')
    cursor.execute('''
        CREATE OR REPLACE VIEW vw_calibracao_atual AS
        SELECT DISTINCT ON (instrumento_id) *
        FROM calibracoes
        ORDER BY instrumento_id, data_calibracao DESC NULLS LAST, id DESC
    ''')
    conn.commit()
    conn.close()


def migrar():
    """Placeholder for future incremental schema migrations.

    Notes:
        Kept for API parity with Ac_app.py's startup sequence, which calls
        criar_tabela() then migrar(). There is nothing to migrate yet, since the
        schema is already created in full by criar_tabela(); this function only
        re-asserts the index and view (both safe to run repeatedly) so it stays
        idempotent and harmless to call on every application startup.
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_calibracoes_instrumento_data
        ON calibracoes (instrumento_id, data_calibracao DESC)
    ''')
    cursor.execute('''
        CREATE OR REPLACE VIEW vw_calibracao_atual AS
        SELECT DISTINCT ON (instrumento_id) *
        FROM calibracoes
        ORDER BY instrumento_id, data_calibracao DESC NULLS LAST, id DESC
    ''')
    conn.commit()
    conn.close()
