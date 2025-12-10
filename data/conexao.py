import sqlite3

db_path = 'instrumentos.db'

def conectar():
    return sqlite3.connect(db_path)

def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instrumentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            sn_instrumento TEXT NOT NULL,
            sn_sensor TEXT,
            min_range REAL,
            max_range REAL
                       
        )
    ''')
    conn.commit()
    conn.close()


