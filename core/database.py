import sqlite3
import os

CAMINHO_BANCO = os.path.join("banco", "clipador.db")

def conectar():
    return sqlite3.connect(CAMINHO_BANCO)

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            nivel INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()

def adicionar_usuario(user_id, nome, nivel=1):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO usuarios (id, nome, nivel) VALUES (?, ?, ?)",
            (user_id, nome, nivel)
        )

    conn.commit()
    conn.close()

def obter_nivel_usuario(user_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT nivel FROM usuarios WHERE id = ?", (user_id,))
    resultado = cursor.fetchone()

    conn.close()
    return resultado[0] if resultado else 1

def atualizar_nivel_usuario(user_id, novo_nivel):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE usuarios SET nivel = ? WHERE id = ?",
        (novo_nivel, user_id)
    )

    conn.commit()
    conn.close()

def listar_usuarios():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios")
    resultado = cursor.fetchall()

    conn.close()
    return resultado
