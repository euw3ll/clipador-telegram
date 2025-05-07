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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            nome TEXT,
            nivel INTEGER DEFAULT 1,
            email TEXT,
            tipo_plano TEXT DEFAULT NULL,
            status_pagamento TEXT DEFAULT 'pendente',
            plano_assinado TEXT DEFAULT NULL,
            is_admin INTEGER DEFAULT 0,
            configuracao_finalizada INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes_canal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            id_canal_telegram TEXT,
            link_canal_telegram TEXT,
            streamers_monitorados TEXT,
            modo_monitoramento TEXT,
            slots_ativos INTEGER DEFAULT 1,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def adicionar_usuario(user_id, nome, nivel=1):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios WHERE telegram_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO usuarios (telegram_id, nome, nivel) VALUES (?, ?, ?)",
            (user_id, nome, nivel)
        )

    conn.commit()
    conn.close()

def obter_nivel_usuario(user_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT nivel FROM usuarios WHERE telegram_id = ?", (user_id,))
    resultado = cursor.fetchone()

    conn.close()
    return resultado[0] if resultado else 1

def atualizar_nivel_usuario(user_id, novo_nivel):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE usuarios SET nivel = ? WHERE telegram_id = ?",
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

    cursor.execute("UPDATE usuarios SET tipo_plano = 'mensal' WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def salvar_email_usuario(telegram_id, email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET email = ? WHERE telegram_id = ?", (email, telegram_id))
    conn.commit()
    conn.close()

def buscar_telegram_por_email(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM usuarios WHERE LOWER(email) = ?", (email.strip().lower(),))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

def email_ja_utilizado_por_outro_usuario(email, telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM usuarios WHERE email = ? AND telegram_id != ?", (email, telegram_id))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def revogar_usuario_por_email(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET tipo_plano = NULL WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def definir_admin(user_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET is_admin = 1 WHERE telegram_id = ?", (user_id,))
    conn.commit()
    conn.close()

def eh_admin(user_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM usuarios WHERE telegram_id = ?", (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado and resultado[0] == 1

def salvar_plano_usuario(user_id, plano):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET plano_assinado = ? WHERE telegram_id = ?", (plano, user_id))
    conn.commit()
    conn.close()

def obter_plano_usuario(user_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT plano_assinado FROM usuarios WHERE telegram_id = ?", (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None
def is_usuario_admin(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM usuarios WHERE telegram_id = ?", (telegram_id,))
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
    cursor.execute("UPDATE usuarios SET status_pagamento = ?, plano_assinado = ? WHERE telegram_id = ?", (status, plano, telegram_id))
    conexao.commit()

    # Se a compra estiver aprovada e ainda não tiver telegram_id, atualiza agora
    if status == "aprovado" and telegram_id:
        cursor.execute("UPDATE compras SET telegram_id = ? WHERE email = ? AND telegram_id IS NULL", (telegram_id, email))
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
def registrar_log_pagamento(telegram_id, email, plano, status):
    import datetime
    dados = {
        "telegram_id": telegram_id,
        "email": email,
        "plano": plano,
        "status": status
    }
    with open("memoria/log_pagamentos.txt", "a", encoding="utf-8") as f:
        linha = f"[{datetime.datetime.now()}] {dados}\n"
        f.write(linha)


# Função para atualizar o status_pagamento do usuário
def atualizar_status_pagamento(telegram_id, status):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET status_pagamento = ? WHERE telegram_id = ?", (status, telegram_id))
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

# Função para atualizar o telegram_id de um usuário baseado no ID interno (chave primária)
def atualizar_telegram_id(id_usuario, telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET telegram_id = ? WHERE id = ?", (telegram_id, id_usuario))
    conn.commit()
    conn.close()


# Função para atualizar o plano de um usuário diretamente
def atualizar_plano_usuario(telegram_id, plano):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET plano_assinado = ? WHERE telegram_id = ?", (plano, telegram_id))
    conn.commit()
    conn.close()


# Função para atualizar o telegram_id baseado no e-mail
def atualizar_telegram_id_por_email(email, telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET telegram_id = ? WHERE email = ?", (telegram_id, email))
    conn.commit()
    conn.close()

compra_ja_registrada = sale_id_ja_registrado

# Função para registrar o histórico de eventos do webhook

def registrar_evento_webhook(dados: dict):
    import datetime
    with open("memoria/log_eventos_webhook.txt", "a", encoding="utf-8") as f:
        linha = f"[{datetime.datetime.now()}] {dados}\n"
        f.write(linha)

# Função para atualizar o telegram_id usando o valor antigo como referência
def atualizar_telegram_id_simples(telegram_id_antigo, telegram_id_novo):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET telegram_id = ? WHERE telegram_id = ?", (telegram_id_novo, telegram_id_antigo))
    conn.commit()
    conn.close()


# Função para vincular um e-mail a um usuário, garantindo que o e-mail não esteja em uso por outro
def vincular_email_usuario(telegram_id, email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM usuarios WHERE email = ? AND telegram_id != ?", (email, telegram_id))
    resultado = cursor.fetchone()
    if resultado:
        conn.close()
        return False  # E-mail já está em uso por outro
    cursor.execute("UPDATE usuarios SET email = ? WHERE telegram_id = ?", (email, telegram_id))
    conn.commit()
    conn.close()
    return True


# Função para buscar todas as compras aprovadas (inclusive sem telegram_id vinculado)
def buscar_compras_aprovadas_nao_vinculadas(email):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM compras
        WHERE email = ? AND status = 'aprovado' AND telegram_id IS NULL
        ORDER BY criado_em DESC
    """, (email,))
    resultado = cursor.fetchall()
    conn.close()
    return resultado


# Função para atualizar o status de uma compra específica vinculada ao telegram_id e email

def atualizar_status_compra_telegram(telegram_id, email, novo_status):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE compras SET status = ? WHERE email = ? AND telegram_id = ?",
        (novo_status, email, telegram_id)
    )
    conn.commit()
    conn.close()


# Função para verificar se o canal do usuário está configurado

def verificar_configuracao_canal(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT plano_assinado, status_pagamento FROM usuarios WHERE telegram_id = ?", (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()
    if not resultado:
        return False
    plano, status = resultado
    return bool(plano and status == "aprovado")

# Função para buscar a configuração de canal de um usuário
def buscar_configuracao_canal(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()

    if resultado:
        colunas = [col[0] for col in cursor.description]
        return dict(zip(colunas, resultado))
    return None

def marcar_configuracao_completa(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET configuracao_finalizada = 1 WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def is_configuracao_completa(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT configuracao_finalizada FROM usuarios WHERE telegram_id = ?", (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado and resultado[0] == 1
def assinatura_em_configuracao(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.nivel, c.twitch_client_id, c.streamers_monitorados, c.modo_monitoramento
        FROM usuarios u
        LEFT JOIN configuracoes_canal c ON u.telegram_id = c.telegram_id
        WHERE u.telegram_id = ? AND u.nivel = 2
    """, (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()

    if not resultado:
        return False

    nivel, twitch_id, streamers, modo = resultado
    campos_pendentes = not twitch_id or not streamers or not modo
    return campos_pendentes


# Funções de progresso do funil usando a tabela configuracoes_canal

def salvar_progresso_configuracao(telegram_id, etapa, dados_parciais=None):
    conn = conectar()
    cursor = conn.cursor()

    # Atualiza ou cria linha com progresso parcial
    if buscar_configuracao_canal(telegram_id):
        cursor.execute(f"""
            UPDATE configuracoes_canal
            SET modo_monitoramento = COALESCE(modo_monitoramento, ?),
                streamers_monitorados = COALESCE(streamers_monitorados, ?)
            WHERE telegram_id = ?
        """, (
            dados_parciais.get("modo_monitoramento") if dados_parciais else None,
            dados_parciais.get("streamers_monitorados") if dados_parciais else None,
            telegram_id
        ))
    else:
        cursor.execute(f"""
            INSERT INTO configuracoes_canal (telegram_id, modo_monitoramento, streamers_monitorados)
            VALUES (?, ?, ?)
        """, (
            telegram_id,
            dados_parciais.get("modo_monitoramento") if dados_parciais else None,
            dados_parciais.get("streamers_monitorados") if dados_parciais else None
        ))

    conn.commit()
    conn.close()

def buscar_progresso_configuracao(telegram_id):
    config = buscar_configuracao_canal(telegram_id)
    if not config:
        return None

    progresso = {}
    if config.get("modo_monitoramento"):
        progresso["modo_monitoramento"] = config["modo_monitoramento"]
    if config.get("streamers_monitorados"):
        progresso["streamers_monitorados"] = config["streamers_monitorados"]
    return progresso if progresso else None

def limpar_progresso_configuracao(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()