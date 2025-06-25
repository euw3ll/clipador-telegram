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
            status_pagamento TEXT DEFAULT 'pendente',
            plano_assinado TEXT DEFAULT NULL,
            configuracao_finalizada INTEGER DEFAULT 0,
            data_expiracao TIMESTAMP,
            status_canal TEXT DEFAULT 'ativo' -- Ex: ativo, removido, desativado
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes_canal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            id_canal_telegram TEXT,
            twitch_client_id TEXT,
            twitch_client_secret TEXT,
            link_canal_telegram TEXT,
            streamers_monitorados TEXT,
            modo_monitoramento TEXT,
            slots_ativos INTEGER DEFAULT 1,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def salvar_configuracao_canal_completa(telegram_id, twitch_client_id, twitch_client_secret, streamers, modo):
    conn = conectar()
    cursor = conn.cursor()
    streamers_str = ",".join(streamers)

    # Verifica se já existe uma configuração para este usuário
    cursor.execute("SELECT * FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    existe = cursor.fetchone()

    if existe:
        # Atualiza a configuração existente
        cursor.execute("""
            UPDATE configuracoes_canal SET
            twitch_client_id = ?, twitch_client_secret = ?, streamers_monitorados = ?, modo_monitoramento = ?
            WHERE telegram_id = ?
        """, (twitch_client_id, twitch_client_secret, streamers_str, modo, telegram_id))
    else:
        # Insere uma nova configuração
        cursor.execute("""
            INSERT INTO configuracoes_canal (telegram_id, twitch_client_id, twitch_client_secret, streamers_monitorados, modo_monitoramento)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, twitch_client_id, twitch_client_secret, streamers_str, modo))
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
    """
    Verifica se o telegram_id está na lista de administradores definida em configuracoes.py.
    """
    from configuracoes import ADMIN_TELEGRAM_IDS
    return telegram_id in ADMIN_TELEGRAM_IDS

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

    conexao.close()

def vincular_compra_e_ativar_usuario(telegram_id: int, email: str, plano: str, status: str):
    """
    Vincula uma compra aprovada ao telegram_id do usuário e ativa o usuário.
    Esta função deve ser chamada pelo bot, não pelo webhook.
    """
    from datetime import datetime, timedelta

    conn = conectar()
    cursor = conn.cursor()

    # 1. Vincula o telegram_id à compra na tabela 'compras' se ainda não estiver vinculado
    # Isso é importante para compras que chegam via webhook antes do usuário informar o e-mail
    cursor.execute("""
        UPDATE compras SET telegram_id = ?
        WHERE email = ? AND status = 'APPROVED' AND telegram_id IS NULL
    """, (telegram_id, email))

    # 2. Atualiza o e-mail do usuário na tabela 'usuarios'
    cursor.execute("UPDATE usuarios SET email = ? WHERE telegram_id = ?", (email, telegram_id))

    # 3. Calcula a data de expiração e atualiza o status do usuário
    if "Anual" in plano:
        data_expiracao = datetime.now() + timedelta(days=365)
    else:  # Assume mensal para todos os outros
        data_expiracao = datetime.now() + timedelta(days=31) # 31 para dar uma margem

    cursor.execute("""
        UPDATE usuarios SET
            status_pagamento = ?,
            plano_assinado = ?,
            nivel = 2, -- Nível 2 para assinante ativo
            data_expiracao = ?,
            status_canal = 'ativo'
        WHERE telegram_id = ?
    """, (status, plano, data_expiracao, telegram_id))

    conn.commit()
    conn.close()

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

def desativar_assinatura_por_email(email: str, novo_status: str = 'expirado'):
    """
    Desativa a assinatura de um usuário com base no e-mail.
    Atualiza o nível para 4 (expirado), status de pagamento e status do canal.
    Retorna o telegram_id do usuário para ações subsequentes (ex: remoção do canal).
    """
    conn = conectar()
    cursor = conn.cursor()

    # Primeiro, busca o telegram_id do usuário ativo com este e-mail
    cursor.execute("SELECT telegram_id FROM usuarios WHERE LOWER(email) = ? AND nivel = 2", (email.lower(),))
    resultado = cursor.fetchone()
    
    if not resultado:
        conn.close()
        return None # Nenhum usuário ativo encontrado com este e-mail

    telegram_id = resultado[0]

    # Nível 4 é para assinaturas expiradas/canceladas
    cursor.execute("""
        UPDATE usuarios
        SET nivel = 4, status_pagamento = ?, status_canal = 'removido'
        WHERE telegram_id = ?
    """, (novo_status, telegram_id))
    
    conn.commit()
    conn.close()
    
    return telegram_id

def atualizar_data_expiracao(email: str, nova_data: 'datetime'):
    """Atualiza a data de expiração e reativa o usuário caso esteja com nível 4."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE usuarios SET data_expiracao = ?, nivel = 2, status_canal = 'ativo' WHERE LOWER(email) = ?
    """, (nova_data, email.lower()))
    conn.commit()
    conn.close()


# Certifique-se de criar as tabelas ao iniciar o projeto
criar_tabelas()
criar_tabela_compras()


# Função para buscar o pagamento mais recente por email na tabela compras
def buscar_pagamento_por_email(email):
    conn = conectar()
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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

def salvar_link_canal(telegram_id, id_canal, link_canal):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes_canal SET id_canal_telegram = ?, link_canal_telegram = ? WHERE telegram_id = ?", (id_canal, link_canal, telegram_id))
    conn.commit()
    conn.close()

def marcar_configuracao_completa(telegram_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET configuracao_finalizada = 1 WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def marcar_configuracao_completa(telegram_id, status: bool):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET configuracao_finalizada = ? WHERE telegram_id = ?", (1 if status else 0, telegram_id))
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

def resetar_estado_usuario_para_teste(telegram_id: int):
    """
    Reseta o estado de um usuário para que ele apareça como um novo usuário
    para fins de teste.
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE usuarios SET
            nivel = 1, status_pagamento = 'pendente', plano_assinado = NULL,
            configuracao_finalizada = 0, data_expiracao = NULL, status_canal = NULL
        WHERE telegram_id = ?
    """, (telegram_id,))
    conn.commit()
    conn.close()
    deletar_configuracao_canal(telegram_id) # Garante que a configuração do canal também seja removida

def buscar_usuarios_ativos_configurados():
    """
    Busca todos os usuários que são assinantes ativos (nível 2) e que
    finalizaram a configuração do canal. Retorna uma lista de dicionários
    com os dados da configuração.
    """
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.* FROM configuracoes_canal c
        JOIN usuarios u ON c.telegram_id = u.telegram_id
        WHERE u.nivel = 2 AND u.configuracao_finalizada = 1
    """)
    resultados = cursor.fetchall()
    conn.close()
    
    # Converte os resultados (sqlite3.Row) para dicionários
    return [dict(row) for row in resultados]

def deletar_configuracao_canal(telegram_id: int):
    """Remove a linha de configuração de um usuário da tabela configuracoes_canal."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def buscar_usuario_por_id(telegram_id: int):
    """Busca os dados de um usuário pelo seu telegram_id."""
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE telegram_id = ?", (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()
    return dict(resultado) if resultado else None