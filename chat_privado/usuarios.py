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
        cursor.execute("SELECT nivel FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()

        if row:
            return row[0]
        elif nome:
            registrar_usuario(telegram_id, nome, plano=None)
            return 0
        else:
            return None

# ✅ CREATE: Registra um novo usuário
def registrar_usuario(telegram_id, nome, plano, tipo=0):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        # Garante que a coluna 'nivel', 'is_admin' e 'tipo_plano' existam
        try:
            cursor.execute("SELECT nivel FROM usuarios LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN nivel INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE usuarios ADD COLUMN is_admin INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE usuarios ADD COLUMN tipo_plano TEXT")
            conn.commit()
        cursor.execute(
            "INSERT INTO usuarios (telegram_id, nome, nivel, is_admin, tipo_plano, plano) VALUES (?, ?, ?, ?, ?, ?)",
            (telegram_id, nome, 0, 0, None, plano)
        )
        conn.commit()

# 🔄 UPDATE: Atualiza nome, nivel ou is_admin do usuário
def atualizar_usuario(telegram_id, nome=None, nivel=None, is_admin=None):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        if nome is not None:
            cursor.execute("UPDATE usuarios SET nome = ? WHERE telegram_id = ?", (nome, telegram_id))
        if nivel is not None:
            cursor.execute("UPDATE usuarios SET nivel = ? WHERE telegram_id = ?", (nivel, telegram_id))
        if is_admin is not None:
            cursor.execute("UPDATE usuarios SET is_admin = ? WHERE telegram_id = ?", (is_admin, telegram_id))
        conn.commit()

# ❌ DELETE: Remove o usuário do banco
def remover_usuario(telegram_id):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        conn.commit()

# 📋 READ ALL: Lista todos os usuários (opcional para debug)
def listar_usuarios():
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, nome, nivel, is_admin, tipo_plano FROM usuarios")
        return cursor.fetchall()
