import sqlite3
import os


CAMINHO_BANCO = os.path.join("banco", "clipador.db")
os.makedirs(os.path.dirname(CAMINHO_BANCO), exist_ok=True)

def conectar():
    return sqlite3.connect(CAMINHO_BANCO)

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            nivel INTEGER DEFAULT 1,
            email TEXT,
            tipo INTEGER DEFAULT 1,
            status_pagamento TEXT DEFAULT 'pendente',
            plano_assinado TEXT DEFAULT NULL,
            is_admin INTEGER DEFAULT 0
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

def ativar_usuario_por_telegram_id(telegram_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("UPDATE usuarios SET tipo = 2 WHERE id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def salvar_email_usuario(telegram_id, email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET email = ? WHERE id = ?", (email, telegram_id))
    conn.commit()
    conn.close()

def buscar_telegram_por_email(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE LOWER(email) = ?", (email.strip().lower(),))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

def email_ja_utilizado_por_outro_usuario(email, telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE email = ? AND id != ?", (email, telegram_id))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def revogar_usuario_por_email(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET tipo = 3 WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def definir_admin(user_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET is_admin = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def eh_admin(user_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM usuarios WHERE id = ?", (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado and resultado[0] == 1

def salvar_plano_usuario(user_id, plano):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET plano_assinado = ? WHERE id = ?", (plano, user_id))
    conn.commit()
    conn.close()

def obter_plano_usuario(user_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT plano_assinado FROM usuarios WHERE id = ?", (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None
def is_usuario_admin(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM usuarios WHERE id = ?", (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado and resultado[0] == 1

def criar_tabela_compras():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            email TEXT NOT NULL,
            plano TEXT NOT NULL,
            metodo_pagamento TEXT,
            status TEXT DEFAULT 'aprovado',
            sale_id TEXT,
            data_criacao TEXT,
            offer_id TEXT,
            nome_completo TEXT,
            telefone TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def registrar_compra(telegram_id, email, plano, metodo_pagamento, status, sale_id, data_criacao, offer_id, nome_completo=None, telefone=None):
    conexao = sqlite3.connect("banco/clipador.db")
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO compras (telegram_id, email, plano, metodo_pagamento, status, sale_id, data_criacao, offer_id, nome_completo, telefone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (telegram_id, email, plano, metodo_pagamento, status, sale_id, data_criacao, offer_id, nome_completo, telefone))
    conexao.commit()

    # Atualiza status_pagamento e plano_assinado do usuário
    cursor.execute("UPDATE usuarios SET status_pagamento = ?, plano_assinado = ? WHERE id = ?", (status, plano, telegram_id))
    conexao.commit()

    conexao.close()

def compra_aprovada(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM compras WHERE email = ? AND status = 'aprovado'",
        (email,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado and resultado[0] > 0

def plano_comprado(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT plano FROM compras WHERE email = ? ORDER BY criado_em DESC LIMIT 1",
        (email,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

def atualizar_status_compra(email, novo_status):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE compras SET status = ? WHERE email = ?",
        (novo_status, email)
    )
    conn.commit()
    conn.close()


# Certifique-se de criar as tabelas ao iniciar o projeto
criar_tabelas()
criar_tabela_compras()


# Função para buscar o pagamento mais recente por email na tabela compras
def buscar_pagamento_por_email(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM compras WHERE email = ? ORDER BY criado_em DESC LIMIT 1",
        (email,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado


# Função para buscar a compra aprovada mais recente por email na tabela compras
def buscar_compra_aprovada_por_email(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM compras
        WHERE email = ? AND status = 'aprovado'
        ORDER BY criado_em DESC
        LIMIT 1
    """, (email,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado


# Função para registrar log de pagamento
def registrar_log_pagamento(dados: dict):
    import datetime
    with open("memoria/log_pagamentos.txt", "a", encoding="utf-8") as f:
        linha = f"[{datetime.datetime.now()}] {dados}\n"
        f.write(linha)


# Função para atualizar o status_pagamento do usuário
def atualizar_status_pagamento(telegram_id, status):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET status_pagamento = ? WHERE id = ?", (status, telegram_id))
    conn.commit()
    conn.close()
# Função para atualizar o status_pagamento do usuário
def atualizar_status_pagamento(telegram_id, status):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET status_pagamento = ? WHERE id = ?", (status, telegram_id))
    conn.commit()
    conn.close()

# Função para verificar se sale_id já foi registrado
def sale_id_ja_registrado(sale_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM compras WHERE sale_id = ?", (sale_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado and resultado[0] > 0