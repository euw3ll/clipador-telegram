import sqlite3
import os
import logging

from core.telethon_criar_canal import deletar_canal_telegram
logger = logging.getLogger(__name__)


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
            email TEXT UNIQUE,
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
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Data de criação do registro
            streamers_ultima_modificacao TIMESTAMP,
            -- Configurações para o modo manual
            manual_min_clips INTEGER,
            manual_interval_sec INTEGER,
            -- Configurações para o plano Parceiro
            clipador_chefe_username TEXT,
            modo_parceiro TEXT -- 'somente_chefe', 'chefe_e_bot', 'somente_bot'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            clipe_id TEXT, -- Adicionado para rastrear clipes individuais do chefe
            streamer_id TEXT NOT NULL,
            grupo_inicio TIMESTAMP NOT NULL,
            grupo_fim TIMESTAMP NOT NULL,
            enviado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def salvar_configuracao_canal_completa(telegram_id, twitch_client_id, twitch_client_secret, streamers, modo, clipador_chefe=None, modo_parceiro='somente_bot'):
    conn = conectar()
    cursor = conn.cursor()
    streamers_str = ",".join(streamers)

    # Define a quantidade de slots com base no plano do usuário
    plano = obter_plano_usuario(telegram_id)
    slots_iniciais = 1
    if plano == "Mensal Plus":
        slots_iniciais = 3
    elif plano == "Anual Pro":
        slots_iniciais = 4  # 3 do plano + 1 de bônus
    elif plano == "PARCEIRO":
        slots_iniciais = 1  # Plano para parceiros
    elif plano == "SUPER":
        slots_iniciais = 999 # Plano de admin sem limites

    # Verifica se já existe uma configuração para este usuário
    cursor.execute("SELECT * FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    existe = cursor.fetchone()

    if existe:
        # Atualiza a configuração existente
        cursor.execute("""
            UPDATE configuracoes_canal
            SET twitch_client_id = ?, twitch_client_secret = ?, streamers_monitorados = ?, modo_monitoramento = ?, slots_ativos = ?, streamers_ultima_modificacao = CURRENT_TIMESTAMP, clipador_chefe_username = ?, modo_parceiro = ?
            WHERE telegram_id = ?
        """, (twitch_client_id, twitch_client_secret, streamers_str, modo, slots_iniciais, clipador_chefe, modo_parceiro, telegram_id))
    else:
        # Insere uma nova configuração
        cursor.execute("""
            INSERT INTO configuracoes_canal (telegram_id, twitch_client_id, twitch_client_secret, streamers_monitorados, modo_monitoramento, slots_ativos, streamers_ultima_modificacao, clipador_chefe_username, modo_parceiro)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """, (telegram_id, twitch_client_id, twitch_client_secret, streamers_str, modo, slots_iniciais, clipador_chefe, modo_parceiro))
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

def migrar_tabelas():
    """Adiciona colunas faltantes a tabelas existentes para evitar erros após atualizações."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        # Migração para a tabela configuracoes_canal
        cursor.execute("PRAGMA table_info(configuracoes_canal)")
        colunas_existentes = [col[1] for col in cursor.fetchall()]

        colunas_a_adicionar = {
            "manual_min_clips": "INTEGER",
            "manual_interval_sec": "INTEGER",
            "clipador_chefe_username": "TEXT",
            "modo_parceiro": "TEXT"
        }

        for nome_coluna, tipo_coluna in colunas_a_adicionar.items():
            if nome_coluna not in colunas_existentes:
                cursor.execute(f"ALTER TABLE configuracoes_canal ADD COLUMN {nome_coluna} {tipo_coluna}")
                logger.info(f"Migração: Coluna '{nome_coluna}' adicionada à tabela 'configuracoes_canal'.")
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Erro durante a migração do banco de dados: {e}")
    finally:
        conn.close()


# Certifique-se de criar as tabelas ao iniciar o projeto
criar_tabelas()
migrar_tabelas()
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

def buscar_link_canal(telegram_id):
    """Busca o link do canal do Telegram de um usuário."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT link_canal_telegram FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

def obter_slots_base_plano(plano: str) -> int:
    """Retorna a quantidade base de slots para um determinado plano."""
    if plano == "Mensal Plus":
        return 3
    elif plano == "Anual Pro":
        return 4  # 3 do plano + 1 de bônus
    elif plano == "PARCEIRO":
        return 1
    elif plano == "SUPER":
        return 999
    return 1  # Padrão para Mensal Solo

def salvar_link_canal(telegram_id, id_canal, link_canal):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes_canal SET id_canal_telegram = ?, link_canal_telegram = ? WHERE telegram_id = ?", (id_canal, link_canal, telegram_id))
    conn.commit()
    conn.close()

def marcar_configuracao_completa(telegram_id, status: bool):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET configuracao_finalizada = ? WHERE telegram_id = ?", (1 if status else 0, telegram_id))
    conn.commit()
    conn.close()

def adicionar_slot_extra(telegram_id: int, quantidade: int = 1):
    """Adiciona um ou mais slots extras para o usuário, incrementando o contador."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE configuracoes_canal
        SET slots_ativos = slots_ativos + ?
        WHERE telegram_id = ?
    """, (quantidade, telegram_id))
    conn.commit()
    conn.close()
    logger.info(f"{quantidade} slot(s) extra(s) adicionado(s) para o usuário {telegram_id}.")

def remover_slots_extras(telegram_id: int):
    """Reseta os slots de um usuário para o valor base do seu plano."""
    conn = conectar()
    cursor = conn.cursor()

    # 1. Descobrir o plano do usuário para saber o valor base de slots
    plano = obter_plano_usuario(telegram_id)
    slots_base = 1
    if plano == "Mensal Plus":
        slots_base = 3
    elif plano == "Anual Pro":
        slots_base = 4  # 3 do plano + 1 de bônus
    elif plano == "PARCEIRO":
        slots_base = 1
    elif plano == "SUPER":
        slots_base = 999

    # 2. Atualizar a tabela de configurações com o valor base
    cursor.execute("UPDATE configuracoes_canal SET slots_ativos = ? WHERE telegram_id = ?", (slots_base, telegram_id))
    
    if cursor.rowcount == 0:
        conn.close()
        raise ValueError(f"Usuário {telegram_id} não possui um canal configurado para remover slots.")

    conn.commit()
    conn.close()
    logger.info(f"Slots extras removidos para o usuário {telegram_id}. Slots resetados para {slots_base}.")

def atualizar_configuracao_manual(telegram_id: int, min_clips: int = None, interval_sec: int = None):
    """Atualiza os parâmetros de configuração manual de um usuário."""
    conn = conectar()
    cursor = conn.cursor()

    updates = []
    params = []

    if min_clips is not None:
        updates.append("manual_min_clips = ?")
        params.append(min_clips)
    if interval_sec is not None:
        updates.append("manual_interval_sec = ?")
        params.append(interval_sec)

    if not updates:
        conn.close()
        return

    params.append(telegram_id)
    query = f"UPDATE configuracoes_canal SET {', '.join(updates)} WHERE telegram_id = ?"
    
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()
    logger.info(f"Configuração manual atualizada para o usuário {telegram_id}.")

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


def salvar_progresso_configuracao(telegram_id, etapa, dados_parciais=None):
    conn = conectar()
    cursor = conn.cursor()

    # Busca a configuração existente para o usuário
    existing_config = buscar_configuracao_canal(telegram_id)

    update_fields = []
    update_values = []

    if dados_parciais:
        if "twitch_client_id" in dados_parciais:
            update_fields.append("twitch_client_id = ?")
            update_values.append(dados_parciais["twitch_client_id"])
        if "twitch_client_secret" in dados_parciais:
            update_fields.append("twitch_client_secret = ?")
            update_values.append(dados_parciais["twitch_client_secret"])
        if "streamers" in dados_parciais:
            streamers_str = ",".join(dados_parciais["streamers"])
            update_fields.append("streamers_monitorados = ?")
            update_values.append(streamers_str)
            # Atualiza o timestamp de modificação de streamers se a lista de streamers mudou
            # ou se está sendo definida pela primeira vez
            if etapa == "streamers" and (not existing_config or existing_config.get("streamers_monitorados") != streamers_str):
                update_fields.append("streamers_ultima_modificacao = CURRENT_TIMESTAMP")
        if "modo" in dados_parciais:
            update_fields.append("modo_monitoramento = ?")
            update_values.append(dados_parciais["modo"])

    if existing_config:
        if update_fields:
            query = f"UPDATE configuracoes_canal SET {', '.join(update_fields)} WHERE telegram_id = ?"
            cursor.execute(query, tuple(update_values + [telegram_id]))
    else:
        # Se não existe, cria um novo registro
        insert_fields = ["telegram_id"]
        insert_values = [telegram_id]
        if "twitch_client_id" in dados_parciais:
            insert_fields.append("twitch_client_id")
            insert_values.append(dados_parciais["twitch_client_id"])
        if "twitch_client_secret" in dados_parciais:
            insert_fields.append("twitch_client_secret")
            insert_values.append(dados_parciais["twitch_client_secret"])
        if "streamers" in dados_parciais:
            insert_fields.append("streamers_monitorados")
            insert_values.append(",".join(dados_parciais["streamers"]))
            insert_fields.append("streamers_ultima_modificacao") # Set timestamp on initial save
            insert_values.append("CURRENT_TIMESTAMP")
        if "modo" in dados_parciais:
            insert_fields.append("modo_monitoramento")
            insert_values.append(dados_parciais["modo"])
        
        query = f"INSERT INTO configuracoes_canal ({', '.join(insert_fields)}) VALUES ({', '.join(['?' for _ in insert_values])})"
        cursor.execute(query, tuple(insert_values))

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
    # Altera para atualizar os campos de progresso para NULL, mantendo o registro do canal
    cursor.execute("""
        UPDATE configuracoes_canal
        SET twitch_client_id = NULL, twitch_client_secret = NULL, streamers_monitorados = NULL, modo_monitoramento = NULL
        WHERE telegram_id = ?
    """, (telegram_id,))
    conn.commit()
    conn.close()
async def resetar_estado_usuario_para_teste(telegram_id: int):
    """
    APAGA COMPLETAMENTE um usuário e todos os seus dados associados do banco de dados,
    e também apaga o canal do Telegram associado, para fins de teste.
    """
    # 1. Buscar e deletar o canal do Telegram
    config = buscar_configuracao_canal(telegram_id)
    if config and config.get('id_canal_telegram'):
        try:
            id_canal = int(config['id_canal_telegram'])
            await deletar_canal_telegram(id_canal)
            logger.info(f"Canal do Telegram {id_canal} para o usuário {telegram_id} deletado com sucesso via Telethon.")
        except Exception as e:
            logger.error(f"Erro ao tentar deletar o canal do Telegram {config.get('id_canal_telegram')} para o usuário {telegram_id}: {e}", exc_info=True)

    # 2. Deletar todos os registros do banco de dados associados ao telegram_id em uma única transação
    conn = conectar()
    cursor = conn.cursor()
    try:
        # Deletar da tabela de configurações
        cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
        # Deletar do histórico de envios
        cursor.execute("DELETE FROM historico_envios WHERE telegram_id = ?", (telegram_id,))
        # Deletar da tabela de compras
        cursor.execute("DELETE FROM compras WHERE telegram_id = ?", (telegram_id,))
        # Deletar da tabela de usuários
        cursor.execute("DELETE FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        logger.info(f"Todos os dados do usuário {telegram_id} foram removidos do banco de dados.")
    except Exception as e:
        logger.error(f"Erro ao deletar dados do usuário {telegram_id} do banco de dados: {e}")
        conn.rollback()
    finally:
        conn.close()

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

def registrar_grupo_enviado(telegram_id: int, streamer_id: str, grupo_inicio: 'datetime', grupo_fim: 'datetime'):
    """Registra que um grupo de clipes foi enviado para um usuário."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO historico_envios (telegram_id, streamer_id, grupo_inicio, grupo_fim)
        VALUES (?, ?, ?, ?)
    """, (telegram_id, streamer_id, grupo_inicio, grupo_fim))
    conn.commit()
    conn.close()

def verificar_grupo_ja_enviado(telegram_id: int, streamer_id: str, grupo_inicio: 'datetime', grupo_fim: 'datetime') -> bool:
    """
    Verifica se um grupo de clipes já foi enviado para um usuário,
    considerando sobreposição de tempo.
    """
    conn = conectar()
    cursor = conn.cursor()
    # CORREÇÃO: A consulta anterior verificava uma correspondência exata e com parâmetros trocados.
    # A nova consulta implementa a lógica correta de sobreposição de tempo para evitar duplicatas.
    # Condição de sobreposição: (start_existente <= end_novo) E (start_novo <= end_existente)
    cursor.execute("""
        SELECT 1 FROM historico_envios
        WHERE telegram_id = ? AND streamer_id = ? AND grupo_inicio <= ? AND ? <= grupo_fim
        LIMIT 1
    """, (telegram_id, streamer_id, grupo_fim, grupo_inicio))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def registrar_clipe_chefe_enviado(telegram_id: int, clipe_id: str):
    """Registra que um clipe individual do chefe foi enviado."""
    conn = conectar()
    cursor = conn.cursor()
    # Usamos o clipe_id para identificar unicamente o clipe do chefe.
    # Os outros campos NOT NULL são preenchidos com valores padrão.
    cursor.execute("""
        INSERT INTO historico_envios (telegram_id, clipe_id, streamer_id, grupo_inicio, grupo_fim)
        VALUES (?, ?, 'clipador_chefe', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (telegram_id, clipe_id))
    conn.commit()
    conn.close()

def verificar_clipe_chefe_ja_enviado(telegram_id: int, clipe_id: str) -> bool:
    """Verifica se um clipe específico do chefe já foi enviado."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM historico_envios
        WHERE telegram_id = ? AND clipe_id = ?
        LIMIT 1
    """, (telegram_id, clipe_id))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def deletar_configuracao_canal(telegram_id: int):
    """Remove a linha de configuração de um usuário da tabela configuracoes_canal."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def atualizar_modo_monitoramento(telegram_id: int, novo_modo: str):
    """Atualiza apenas o modo de monitoramento de um canal."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes_canal SET modo_monitoramento = ? WHERE telegram_id = ?", (novo_modo, telegram_id))
    conn.commit()
    conn.close()

def atualizar_streamers_monitorados(telegram_id: int, nova_lista_streamers: list[str]):
    """
    Atualiza a lista de streamers monitorados.
    O timestamp 'streamers_ultima_modificacao' NÃO é atualizado aqui,
    pois ele marca o início do período de 1 hora para alterações,
    e não deve ser resetado a cada modificação.
    """
    conn = conectar()
    cursor = conn.cursor()
    streamers_str = ",".join(nova_lista_streamers)
    cursor.execute("""
        UPDATE configuracoes_canal -- Remove a atualização do timestamp aqui
        SET streamers_monitorados = ?
        WHERE telegram_id = ?
    """, (streamers_str, telegram_id))
    conn.commit()
    conn.close()

def resetar_cooldown_streamers(telegram_id: int):
    """Reseta o cooldown para alteração de streamers, permitindo modificações."""
    conn = conectar()
    cursor = conn.cursor()
    # Definir o timestamp como NULL efetivamente reseta o timer,
    # pois a lógica de verificação permitirá a alteração.
    cursor.execute("""
        UPDATE configuracoes_canal
        SET streamers_ultima_modificacao = NULL
        WHERE telegram_id = ?
    """, (telegram_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise ValueError(f"Usuário {telegram_id} não possui um canal configurado.")

    conn.commit()
    conn.close()
    logger.info(f"Cooldown de alteração de streamers resetado para o usuário {telegram_id}.")

def buscar_usuario_por_id(telegram_id: int):
    """Busca os dados de um usuário pelo seu telegram_id."""
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE telegram_id = ?", (telegram_id,))
    resultado = cursor.fetchone()
    conn.close()
    return dict(resultado) if resultado else None

def buscar_usuario_por_email(email: str):
    """Busca os dados de um usuário pelo seu email."""
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE LOWER(email) = ?", (email.strip().lower(),))
    resultado = cursor.fetchone()
    conn.close()
    return dict(resultado) if resultado else None

def buscar_ids_assinantes_ativos():
    """Busca os IDs de todos os usuários que são assinantes ativos (nível 2)."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM usuarios WHERE nivel = 2")
    resultados = cursor.fetchall()
    conn.close()
    return [row[0] for row in resultados]

def conceder_plano_usuario(telegram_id: int, plano: str, dias: int):
    """Concede um plano a um usuário, ativando-o e definindo a data de expiração."""
    from datetime import datetime, timedelta
    conn = conectar()
    cursor = conn.cursor()

    # Pega o plano antigo para calcular os slots extras comprados
    cursor.execute("SELECT plano_assinado FROM usuarios WHERE telegram_id = ?", (telegram_id,))
    resultado_plano_antigo = cursor.fetchone()
    plano_antigo = resultado_plano_antigo[0] if resultado_plano_antigo else None

    # 1. Calcula a data de expiração
    data_expiracao = datetime.now() + timedelta(days=dias)

    # 2. Atualiza os dados do usuário
    cursor.execute("""
        UPDATE usuarios SET
            plano_assinado = ?, nivel = 2, data_expiracao = ?,
            status_pagamento = 'approved_admin', status_canal = 'ativo'
        WHERE telegram_id = ?
    """, (plano, data_expiracao, telegram_id))

    # 3. Atualiza os slots na tabela de configuração, preservando slots extras
    slots_base_novo = 1
    if plano == "Mensal Plus": slots_base_novo = 3
    elif plano == "Anual Pro": slots_base_novo = 4
    elif plano == "PARCEIRO": slots_base_novo = 1
    elif plano == "SUPER": slots_base_novo = 999
    
    cursor.execute("SELECT slots_ativos FROM configuracoes_canal WHERE telegram_id = ?", (telegram_id,))
    config_result = cursor.fetchone()
    
    if config_result:
        slots_atuais = config_result[0]
        slots_base_antigo = 1
        if plano_antigo == "Mensal Plus":
            slots_base_antigo = 3
        elif plano_antigo == "Anual Pro":
            slots_base_antigo = 4
        elif plano_antigo == "PARCEIRO":
            slots_base_antigo = 1
        elif plano_antigo == "SUPER":
            slots_base_antigo = 999
        slots_extras_comprados = max(0, slots_atuais - slots_base_antigo)
        novos_slots_totais = slots_base_novo + slots_extras_comprados
        cursor.execute("UPDATE configuracoes_canal SET slots_ativos = ? WHERE telegram_id = ?", (novos_slots_totais, telegram_id))

    conn.commit()
    conn.close()
    logger.info(f"Plano '{plano}' concedido ao usuário {telegram_id} por {dias} dias via admin.")

def obter_estatisticas_gerais():
    """Busca estatísticas gerais do bot."""
    conn = conectar()
    cursor = conn.cursor()

    # Total de usuários
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    total_usuarios = cursor.fetchone()[0]

    # Assinantes ativos (nível 2)
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE nivel = 2")
    assinantes_ativos = cursor.fetchone()[0]

    # Canais monitorados (que têm um id_canal_telegram)
    cursor.execute("SELECT COUNT(*) FROM configuracoes_canal WHERE id_canal_telegram IS NOT NULL")
    canais_monitorados = cursor.fetchone()[0]

    conn.close()

    return {
        "total_usuarios": total_usuarios,
        "assinantes_ativos": assinantes_ativos,
        "canais_monitorados": canais_monitorados
    }