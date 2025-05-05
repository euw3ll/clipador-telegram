import sqlite3

CAMINHO_BANCO = "banco/clipador.db"

# 🔧 Garantir compatibilidade com coluna 'telegram_id' inexistente
def corrigir_coluna_telegram_id():
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT telegram_id FROM usuarios LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN telegram_id INTEGER")
            cursor.execute("UPDATE usuarios SET telegram_id = id")
            conn.commit()

corrigir_coluna_telegram_id()

# 🧠 READ: Obtem o nível do usuário. Se não existir e nome for fornecido, registra como comum
def get_nivel_usuario(telegram_id, nome=None):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tipo FROM usuarios WHERE id = ?", (telegram_id,))
        row = cursor.fetchone()

        if row:
            return row[0]
        elif nome:
            registrar_usuario(telegram_id, nome, tipo=1)
            return 1
        else:
            return None

# ✅ CREATE: Registra um novo usuário
def registrar_usuario(telegram_id, nome, tipo=1):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO usuarios (id, nome, tipo) VALUES (?, ?, ?)",
            (telegram_id, nome, tipo)
        )
        conn.commit()

# 🔄 UPDATE: Atualiza nome ou tipo do usuário
def atualizar_usuario(telegram_id, nome=None, tipo=None):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        if nome and tipo is not None:
            cursor.execute("UPDATE usuarios SET nome = ?, tipo = ? WHERE id = ?", (nome, tipo, telegram_id))
        elif nome:
            cursor.execute("UPDATE usuarios SET nome = ? WHERE id = ?", (nome, telegram_id))
        elif tipo is not None:
            cursor.execute("UPDATE usuarios SET tipo = ? WHERE id = ?", (tipo, telegram_id))
        conn.commit()

# ❌ DELETE: Remove o usuário do banco
def remover_usuario(telegram_id):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (telegram_id,))
        conn.commit()

# 📋 READ ALL: Lista todos os usuários (opcional para debug)
def listar_usuarios():
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, tipo FROM usuarios")
        return cursor.fetchall()
