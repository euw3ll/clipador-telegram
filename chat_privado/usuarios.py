import sqlite3

CAMINHO_BANCO = "banco/clipador.db"

def get_nivel_usuario(telegram_id, nome=None):
    """
    Obtém o nível do usuário. Se não existir, registra como um novo usuário comum (nível 1).
    """
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nivel FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()

        if row:
            return row[0]
        
        if nome:
            # Usuário não existe, vamos registrá-lo.
            registrar_usuario(telegram_id, nome)
            return 1  # Retorna o nível padrão para novos usuários (1).
        
        return None # Não pode registrar sem nome.

def registrar_usuario(telegram_id, nome):
    """
    Registra um novo usuário no banco de dados com valores padrão.
    Usa INSERT OR IGNORE para evitar erros se o usuário for criado simultaneamente.
    """
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        # A tabela 'usuarios' já tem valores DEFAULT para a maioria das colunas (como nivel=1).
        # O INSERT só precisa do essencial.
        cursor.execute(
            "INSERT OR IGNORE INTO usuarios (telegram_id, nome) VALUES (?, ?)",
            (telegram_id, nome)
        )
        conn.commit()

# 🔄 UPDATE: Atualiza nome, nivel ou is_admin do usuário
def atualizar_usuario(telegram_id, nome=None, nivel=None):
    with sqlite3.connect(CAMINHO_BANCO) as conn:
        cursor = conn.cursor()
        if nome is not None:
            cursor.execute("UPDATE usuarios SET nome = ? WHERE telegram_id = ?", (nome, telegram_id))
        if nivel is not None:
            cursor.execute("UPDATE usuarios SET nivel = ? WHERE telegram_id = ?", (nivel, telegram_id))
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
        cursor.execute("SELECT telegram_id, nome, nivel, email, tipo_plano, plano_assinado FROM usuarios")
        return cursor.fetchall()
