# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : scripts.migrar_sqlite_para_supabase
# Created       : 06-10-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : One-shot, idempotent migration of the legacy local SQLite 'instrumentos'
#                 table into the normalized 'instrumentos'/'calibracoes' schema on Supabase.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

"""Migrates the old single-table SQLite database (%APPDATA%/ACs Generator/instrumentos.db)
into the new, normalized Postgres (Supabase) schema with two tables: 'instrumentos'
(physical identity of each unit) and 'calibracoes' (append-only calibration history).

This script is self-contained on purpose: it does not import data/conexao.py nor
data/utils_db.py (those modules only know how to talk to the new Postgres schema and
no longer have any SQLite logic). It opens the legacy SQLite file directly and writes
to Postgres via plain psycopg2/SQL.

Usage:
    python scripts/migrar_sqlite_para_supabase.py [--dry-run]

What it does:
    1. Loads SUPABASE_DB_URL from the ".env" file at the project root.
    2. Looks for the legacy SQLite file at
       Path(os.getenv('APPDATA')) / 'ACs Generator' / 'instrumentos.db'. If it isn't
       found, prints a message and exits (not an error: there's simply nothing to
       migrate on this machine).
    3. Connects to Postgres and makes sure the new schema exists (idempotent DDL:
       CREATE TABLE/INDEX IF NOT EXISTS, CREATE OR REPLACE VIEW).
    4. For every row of the old SQLite 'instrumentos' table:
       a. Upserts an 'instrumentos' row (tag, sn_instrumento, tipo, sistema, aplicacao,
          ativo, em_uso=TRUE), using ON CONFLICT (tag, sn_instrumento) DO NOTHING so the
          script can be re-run safely without duplicating instruments.
       b. If any of sn_sensor/min_range/max_range/data_calibracao/proxima_calibracao/
          numero_certificado/laboratorio/observacoes/modificado_por/modificado_em is
          filled (not NULL and not an empty string), inserts one 'calibracoes' row
          referencing that instrument. Empty strings become NULL. data_calibracao and
          proxima_calibracao (free text, usually "dd/mm/aaaa") are parsed into real
          dates; values that fail to parse are stored as NULL and reported at the end.
       c. Rows with none of those fields filled get no 'calibracoes' row (instrument
          without a recorded calibration yet).
    5. Prints a summary: SQLite rows read, instruments inserted vs. already present,
       calibrations inserted vs. skipped (already migrated), and any date/timestamp
       values that couldn't be parsed.
    6. Re-running the script is safe: instruments are deduplicated by
       (tag, sn_instrumento), and calibrations are deduplicated by
       (instrumento_id, numero_certificado) whenever a certificate number is present.
       Calibration rows with no numero_certificado can't be safely deduplicated and are
       inserted again on every run; the summary reports how many times that happened.

Flags:
    --dry-run: Still loads the .env, opens the SQLite file and connects to Postgres
        (running the idempotent DDL for real, since it's harmless), but performs no
        INSERT of migrated data. Instead, it reports how many rows *would* be migrated,
        using read-only SELECTs to tell new rows apart from already-migrated ones.
"""

import argparse
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

CAMPOS_CALIBRACAO = (
    "sn_sensor", "min_range", "max_range", "data_calibracao", "proxima_calibracao",
    "numero_certificado", "laboratorio", "observacoes", "modificado_por", "modificado_em",
)

DDL = """
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
);

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
);

CREATE INDEX IF NOT EXISTS idx_calibracoes_instrumento_data ON calibracoes (instrumento_id, data_calibracao DESC);

CREATE OR REPLACE VIEW vw_calibracao_atual AS
SELECT DISTINCT ON (instrumento_id) *
FROM calibracoes
ORDER BY instrumento_id, data_calibracao DESC NULLS LAST, id DESC;
"""


def get_sqlite_path():
    """Build the path of the legacy SQLite database, the same way data/conexao.py used to.

    Returns:
        Path: Expected location of '%APPDATA%/ACs Generator/instrumentos.db'.
    """
    return Path(os.getenv("APPDATA")) / "ACs Generator" / "instrumentos.db"


def ler_instrumentos_sqlite(caminho_sqlite):
    """Read every row of the legacy 'instrumentos' table as a list of dicts.

    Args:
        caminho_sqlite: Path to the legacy SQLite database file.

    Returns:
        list[dict]: One dict per row, keyed by column name.
    """
    with closing(sqlite3.connect(caminho_sqlite)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM instrumentos")
        return [dict(row) for row in cur.fetchall()]


def nulo_ou_vazio(valor):
    """Check whether a raw SQLite value should be treated as "not filled".

    Args:
        valor: Raw value read from the legacy SQLite table.

    Returns:
        bool: True if the value is None or an empty string.
    """
    return valor is None or valor == ""


def normalizar(valor):
    """Convert an empty string into None; pass through every other value unchanged.

    Args:
        valor: Raw value read from the legacy SQLite table.

    Returns:
        The original value, or None if it was an empty string.
    """
    return None if valor == "" else valor


def parse_data_br(valor, campo, tag, sn, problemas):
    """Parse a 'dd/mm/aaaa' free-text date into a Python date, tolerating bad input.

    Args:
        valor: Raw text value (may be None, empty, or an unparseable string).
        campo: Name of the source column, used only for reporting.
        tag: Instrument tag, used only for reporting.
        sn: Instrument serial number, used only for reporting.
        problemas: list that failed parses are appended to, as (campo, tag, sn, valor).

    Returns:
        date | None: Parsed date, or None if the value was empty/missing/unparseable.
    """
    if nulo_ou_vazio(valor):
        return None
    try:
        return datetime.strptime(valor.strip(), "%d/%m/%Y").date()
    except ValueError:
        problemas.append((campo, tag, sn, valor))
        return None


def parse_timestamp_br(valor, campo, tag, sn, problemas):
    """Parse a 'dd/mm/aaaa HH:MM[:SS]' free-text timestamp, tolerating bad input.

    Args:
        valor: Raw text value (may be None, empty, or an unparseable string).
        campo: Name of the source column, used only for reporting.
        tag: Instrument tag, used only for reporting.
        sn: Instrument serial number, used only for reporting.
        problemas: list that failed parses are appended to, as (campo, tag, sn, valor).

    Returns:
        datetime | None: Parsed timestamp, or None if empty/missing/unparseable.
    """
    if nulo_ou_vazio(valor):
        return None
    texto = valor.strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    problemas.append((campo, tag, sn, valor))
    return None


def tem_dado_de_calibracao(row):
    """Check whether a legacy SQLite row carries any calibration-related field.

    Args:
        row: Dict for one legacy 'instrumentos' row.

    Returns:
        bool: True if at least one of CAMPOS_CALIBRACAO is filled on this row.
    """
    return any(not nulo_ou_vazio(row.get(campo)) for campo in CAMPOS_CALIBRACAO)


def obter_ou_criar_instrumento(cur, row, dry_run, stats):
    """Upsert the 'instrumentos' row for one legacy record and resolve its new id.

    Args:
        cur: Open psycopg2 cursor.
        row: Dict for one legacy SQLite 'instrumentos' row.
        dry_run: If True, never writes; only resolves/reports what would happen.
        stats: Mutable dict accumulating summary counters.

    Returns:
        int | None: The resolved/would-be instrumento id (None in dry-run when the
        instrument doesn't exist yet, since no id is actually assigned).
    """
    tag = row["tag"]
    sn = row["sn_instrumento"]
    tipo = row["tipo"] or "SEC"

    if dry_run:
        cur.execute(
            "SELECT id FROM instrumentos WHERE tag = %s AND sn_instrumento = %s",
            (tag, sn),
        )
        existente = cur.fetchone()
        if existente:
            stats["instrumentos_existentes"] += 1
            return existente[0]
        stats["instrumentos_a_inserir"] += 1
        return None

    cur.execute(
        """
        INSERT INTO instrumentos (tag, sn_instrumento, tipo, sistema, aplicacao, ativo, em_uso)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (tag, sn_instrumento) DO NOTHING
        RETURNING id
        """,
        (tag, sn, tipo, normalizar(row.get("sistema")), normalizar(row.get("aplicacao")),
         normalizar(row.get("ativo"))),
    )
    inserido = cur.fetchone()
    if inserido:
        stats["instrumentos_inseridos"] += 1
        return inserido[0]

    stats["instrumentos_existentes"] += 1
    cur.execute(
        "SELECT id FROM instrumentos WHERE tag = %s AND sn_instrumento = %s",
        (tag, sn),
    )
    return cur.fetchone()[0]


def migrar_calibracao(cur, instrumento_id, row, dry_run, stats, problemas_data):
    """Insert the 'calibracoes' row for one legacy record, if it carries any such data.

    Args:
        cur: Open psycopg2 cursor.
        instrumento_id: Resolved id in the new 'instrumentos' table (may be None in
            dry-run, when the parent instrument doesn't exist yet).
        row: Dict for one legacy SQLite 'instrumentos' row.
        dry_run: If True, never writes; only reports what would happen.
        stats: Mutable dict accumulating summary counters.
        problemas_data: list that unparseable date/timestamp values are appended to.
    """
    if not tem_dado_de_calibracao(row):
        return

    tag, sn = row["tag"], row["sn_instrumento"]
    numero_certificado = normalizar(row.get("numero_certificado"))

    if numero_certificado is None:
        # Can't be safely deduplicated; always reported, in both dry-run and real runs.
        stats["calibracoes_sem_certificado"] += 1
    elif instrumento_id is not None:
        cur.execute(
            "SELECT id FROM calibracoes WHERE instrumento_id = %s AND numero_certificado = %s",
            (instrumento_id, numero_certificado),
        )
        if cur.fetchone():
            stats["calibracoes_existentes"] += 1
            return

    if dry_run:
        stats["calibracoes_a_inserir"] += 1
        # Parse dates anyway so dry-run reports the same conversion problems a real run would.
        parse_data_br(row.get("data_calibracao"), "data_calibracao", tag, sn, problemas_data)
        parse_data_br(row.get("proxima_calibracao"), "proxima_calibracao", tag, sn, problemas_data)
        parse_timestamp_br(row.get("modificado_em"), "modificado_em", tag, sn, problemas_data)
        return

    data_calibracao = parse_data_br(row.get("data_calibracao"), "data_calibracao", tag, sn, problemas_data)
    proxima_calibracao = parse_data_br(row.get("proxima_calibracao"), "proxima_calibracao", tag, sn, problemas_data)
    modificado_em = parse_timestamp_br(row.get("modificado_em"), "modificado_em", tag, sn, problemas_data)

    cur.execute(
        """
        INSERT INTO calibracoes (
            instrumento_id, sn_sensor, min_range, max_range, numero_certificado,
            laboratorio, data_calibracao, proxima_calibracao, observacoes,
            modificado_por, modificado_em
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            instrumento_id,
            normalizar(row.get("sn_sensor")),
            row.get("min_range"),
            row.get("max_range"),
            numero_certificado,
            normalizar(row.get("laboratorio")),
            data_calibracao,
            proxima_calibracao,
            normalizar(row.get("observacoes")),
            normalizar(row.get("modificado_por")),
            modificado_em,
        ),
    )
    stats["calibracoes_inseridas"] += 1


def migrar(conn, linhas_sqlite, dry_run):
    """Run the full migration (or its dry-run simulation) over every legacy row.

    Args:
        conn: Open psycopg2 connection (DDL must already have been applied).
        linhas_sqlite: List of dicts, one per legacy SQLite 'instrumentos' row.
        dry_run: If True, no data is written; only the summary is computed.

    Returns:
        tuple[dict, list]: (stats, problemas_data) - the summary counters dict and
        the list of (campo, tag, sn, valor_bruto) for dates/timestamps that failed to parse.
    """
    stats = {
        "linhas_lidas": len(linhas_sqlite),
        "instrumentos_inseridos": 0,
        "instrumentos_existentes": 0,
        "instrumentos_a_inserir": 0,
        "calibracoes_inseridas": 0,
        "calibracoes_existentes": 0,
        "calibracoes_a_inserir": 0,
        "calibracoes_sem_certificado": 0,
    }
    problemas_data = []

    with conn.cursor() as cur:
        for row in linhas_sqlite:
            instrumento_id = obter_ou_criar_instrumento(cur, row, dry_run, stats)
            migrar_calibracao(cur, instrumento_id, row, dry_run, stats, problemas_data)
            if not dry_run:
                conn.commit()

    return stats, problemas_data


def imprimir_resumo(stats, problemas_data, dry_run):
    """Print the final human-readable migration summary.

    Args:
        stats: Summary counters dict, as returned by migrar().
        problemas_data: List of unparseable date/timestamp values, as returned by migrar().
        dry_run: Whether this run was a simulation (changes the wording/labels used).
    """
    prefixo = "[DRY-RUN] " if dry_run else ""
    print(f"\n{prefixo}Resumo da migracao")
    print("-" * 60)
    print(f"Linhas lidas do SQLite ................ {stats['linhas_lidas']}")
    if dry_run:
        print(f"Instrumentos a inserir ................. {stats['instrumentos_a_inserir']}")
        print(f"Instrumentos ja existentes ............. {stats['instrumentos_existentes']}")
        print(f"Calibracoes a inserir .................. {stats['calibracoes_a_inserir']}")
        print(f"Calibracoes ja existentes (puladas) ..... {stats['calibracoes_existentes']}")
    else:
        print(f"Instrumentos inseridos ................. {stats['instrumentos_inseridos']}")
        print(f"Instrumentos ja existentes (pulados) .... {stats['instrumentos_existentes']}")
        print(f"Calibracoes inseridas .................. {stats['calibracoes_inseridas']}")
        print(f"Calibracoes ja existentes (puladas) ..... {stats['calibracoes_existentes']}")
    print(f"Calibracoes sem numero_certificado ..... {stats['calibracoes_sem_certificado']} "
          f"(nao deduplicaveis com seguranca; inseridas mesmo assim a cada execucao)")
    print(f"Datas/timestamps nao convertidos ........ {len(problemas_data)}")
    if problemas_data:
        print("  Valores brutos problematicos (campo, tag, sn_instrumento, valor):")
        for campo, tag, sn, valor in problemas_data:
            print(f"    - {campo}: tag={tag!r} sn_instrumento={sn!r} valor={valor!r}")
    print("-" * 60)


def main():
    """Entry point: parse args, load env, read SQLite, ensure schema and migrate."""
    parser = argparse.ArgumentParser(
        description="Migrates the legacy local SQLite 'instrumentos' database into the "
                    "normalized Postgres (Supabase) 'instrumentos'/'calibracoes' schema."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read SQLite, connect to Postgres and apply the DDL, but do not write any migrated data.",
    )
    args = parser.parse_args()

    load_dotenv()
    try:
        db_url = os.environ["SUPABASE_DB_URL"]
    except KeyError:
        print("Erro: variavel SUPABASE_DB_URL nao encontrada. Configure o arquivo .env na raiz do projeto.")
        sys.exit(1)

    caminho_sqlite = get_sqlite_path()
    if not caminho_sqlite.exists():
        print(f"Nenhum banco SQLite legado encontrado em: {caminho_sqlite}")
        print("Nada para migrar nesta maquina.")
        return

    print(f"Lendo banco SQLite legado em: {caminho_sqlite}")
    linhas_sqlite = ler_instrumentos_sqlite(caminho_sqlite)
    print(f"{len(linhas_sqlite)} linha(s) encontrada(s) na tabela 'instrumentos'.")

    print("Conectando ao Postgres (Supabase)...")
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
        print("Schema 'instrumentos'/'calibracoes' conferido/criado com sucesso.")

        if args.dry_run:
            print("Modo --dry-run: nenhum dado sera escrito, apenas simulado.")

        stats, problemas_data = migrar(conn, linhas_sqlite, args.dry_run)
        imprimir_resumo(stats, problemas_data, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
