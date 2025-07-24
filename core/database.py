import psycopg2
from psycopg2.extras import DictCursor
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# Importa as variáveis de ambiente do PostgreSQL
from core.ambiente import (
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_HOST,
    POSTGRES_PORT,
)

logger = logging.getLogger(__name__)


def conectar():
    """Estabelece conexão com o banco de dados PostgreSQL."""
    try:
        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"❌ Erro fatal ao conectar com o PostgreSQL: {e}")
        raise


def criar_tabelas():
    """Cria todas as tabelas no banco de dados PostgreSQL se elas não existirem."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # Tabela de usuários
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    nome TEXT,
                    email TEXT UNIQUE,
                    nivel INTEGER DEFAULT 1,
                    status_pagamento TEXT DEFAULT 'pendente',
                    plano_assinado TEXT DEFAULT NULL,
                    configuracao_finalizada BOOLEAN DEFAULT FALSE,
                    data_expiracao TIMESTAMPTZ,
                    status_canal TEXT DEFAULT 'ativo',
                    aviso_canal_gratuito_enviado BOOLEAN DEFAULT FALSE,
                    ultimo_aviso_expiracao INTEGER DEFAULT NULL,
                    usou_teste_gratuito BOOLEAN DEFAULT FALSE
                )
            """)

            # Tabela de configurações de canal
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes_canal (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    id_canal_telegram TEXT,
                    twitch_client_id TEXT,
                    twitch_client_secret TEXT,
                    link_canal_telegram TEXT,
                    streamers_monitorados TEXT,
                    modo_monitoramento TEXT,
                    slots_ativos INTEGER DEFAULT 1,
                    data_criacao TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    streamers_ultima_modificacao TIMESTAMPTZ,
                    manual_min_clips INTEGER,
                    manual_interval_sec INTEGER,
                    manual_min_clips_vod INTEGER,
                    clipador_chefe_username TEXT,
                    modo_parceiro TEXT
                )
            """)

            # Tabela de histórico de envios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS historico_envios (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    clipe_id TEXT,
                    streamer_id TEXT NOT NULL,
                    grupo_inicio TIMESTAMPTZ NOT NULL,
                    grupo_fim TIMESTAMPTZ NOT NULL,
                    enviado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tabela de status dos streamers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS status_streamers (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    streamer_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    ultima_verificacao TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(telegram_id, streamer_id)
                )
            """)

            # Tabela de compras
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS compras (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT,
                    email TEXT NOT NULL,
                    plano TEXT NOT NULL,
                    metodo_pagamento TEXT,
                    status TEXT DEFAULT 'aprovado',
                    sale_id TEXT,
                    data_criacao TEXT,
                    offer_id TEXT,
                    nome_completo TEXT,
                    telefone TEXT,
                    criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tabela de notificações com FOREIGN KEY
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notificacoes_config (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    notificar_online BOOLEAN DEFAULT TRUE,
                    CONSTRAINT fk_usuarios
                        FOREIGN KEY(telegram_id) 
                        REFERENCES usuarios(telegram_id)
                        ON DELETE CASCADE
                )
            """)
            conn.commit()
            logger.info("Verificação de tabelas concluída.")
    except psycopg2.Error as e:
        logger.error(f"Erro ao criar tabelas: {e}")
        conn.rollback()
    finally:
        conn.close()


def migrar_tabelas():
    """Adiciona colunas faltantes a tabelas existentes para evitar erros após atualizações."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            def coluna_existe(tabela, coluna):
                cursor.execute("""
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
                """, (tabela, coluna))
                return cursor.fetchone() is not None

            colunas_config = {
                "manual_min_clips": "INTEGER", "manual_interval_sec": "INTEGER",
                "manual_min_clips_vod": "INTEGER", "clipador_chefe_username": "TEXT", "modo_parceiro": "TEXT"
            }
            for nome, tipo in colunas_config.items():
                if not coluna_existe('configuracoes_canal', nome):
                    cursor.execute(f"ALTER TABLE configuracoes_canal ADD COLUMN {nome} {tipo}")
                    logger.info(f"Migração: Coluna '{nome}' adicionada a 'configuracoes_canal'.")

            colunas_usuarios = {
                "aviso_canal_gratuito_enviado": "BOOLEAN DEFAULT FALSE",
                "ultimo_aviso_expiracao": "INTEGER",
                "usou_teste_gratuito": "BOOLEAN DEFAULT FALSE"
            }
            for nome, definicao in colunas_usuarios.items():
                if not coluna_existe('usuarios', nome):
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {nome} {definicao}")
                    logger.info(f"Migração: Coluna '{nome}' adicionada a 'usuarios'.")
            
            conn.commit()
            logger.info("Verificação de migração de colunas concluída.")
    except psycopg2.Error as e:
        logger.error(f"Erro durante a migração do banco de dados: {e}")
        conn.rollback()
    finally:
        conn.close()

# --- FUNÇÕES DE GERENCIAMENTO DE USUÁRIOS E PLANOS ---

def adicionar_usuario(user_id: int, nome: str, nivel: int = 1):
    """Insere um novo usuário no banco de dados se ele não existir."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # ON CONFLICT é uma forma mais robusta e eficiente de lidar com inserções duplicadas no PostgreSQL
            cursor.execute("""
                INSERT INTO usuarios (telegram_id, nome, nivel) VALUES (%s, %s, %s)
                ON CONFLICT (telegram_id) DO NOTHING
            """, (user_id, nome, nivel))
            conn.commit()
    finally:
        conn.close()


def obter_nivel_usuario(user_id: int) -> int:
    """Obtém o nível de um usuário. Retorna 1 (padrão) se não encontrado."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT nivel FROM usuarios WHERE telegram_id = %s", (user_id,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else 1
    finally:
        conn.close()


def buscar_telegram_por_email(email: str) -> Optional[int]:
    """Busca o telegram_id de um usuário pelo seu e-mail, ignorando maiúsculas/minúsculas."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT telegram_id FROM usuarios WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else None
    finally:
        conn.close()


def email_ja_utilizado_por_outro_usuario(email: str, telegram_id: int) -> bool:
    """Verifica se um e-mail já está em uso por outro usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM usuarios WHERE email = %s AND telegram_id != %s", (email, telegram_id))
            return cursor.fetchone() is not None
    finally:
        conn.close()


def revogar_usuario_por_email(email: str):
    """
    (Função a ser revisada) Remove o plano de um usuário por e-mail.
    A coluna original 'tipo_plano' foi removida; esta função agora limpa 'plano_assinado'.
    """
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # A coluna 'tipo_plano' não existe mais. Adaptado para 'plano_assinado'.
            cursor.execute("UPDATE usuarios SET plano_assinado = NULL WHERE email = %s", (email,))
            conn.commit()
    finally:
        conn.close()


def salvar_plano_usuario(user_id: int, plano: str):
    """Salva ou atualiza o plano assinado por um usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET plano_assinado = %s WHERE telegram_id = %s", (plano, user_id))
            conn.commit()
    finally:
        conn.close()


def obter_plano_usuario(user_id: int) -> Optional[str]:
    """Obtém o plano assinado por um usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT plano_assinado FROM usuarios WHERE telegram_id = %s", (user_id,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else None
    finally:
        conn.close()


def is_usuario_admin(telegram_id: int) -> bool:
    """Verifica se o telegram_id está na lista de administradores (não acessa o DB)."""
    from configuracoes import ADMIN_TELEGRAM_IDS
    return telegram_id in ADMIN_TELEGRAM_IDS

# --- FUNÇÕES DE COMPRAS E ASSINATURAS ---

def registrar_compra(telegram_id: Optional[int], email: str, plano: str, metodo_pagamento: str, status: str, sale_id: str, data_criacao: str, offer_id: str, nome_completo: Optional[str] = None, telefone: Optional[str] = None):
    """Registra uma nova compra no banco de dados."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO compras (telegram_id, email, plano, metodo_pagamento, status, sale_id, data_criacao, offer_id, nome_completo, telefone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (telegram_id, email, plano, metodo_pagamento, status, sale_id, data_criacao, offer_id, nome_completo, telefone))
            conn.commit()
    except psycopg2.Error as e:
        logger.error(f"Erro ao registrar compra para o e-mail {email}: {e}")
        conn.rollback()
    finally:
        conn.close()


def vincular_compra_e_ativar_usuario(telegram_id: int, email: str, plano: str, status: str):
    """Vincula uma compra aprovada e ativa o status do usuário em uma única transação."""
    from datetime import datetime, timedelta
    from configuracoes import TESTE_GRATUITO_DURACAO_DIAS

    if plano == "Teste Gratuito" and usuario_ja_usou_teste(telegram_id):
        raise ValueError("Você já utilizou o período de teste gratuito.")

    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # 1. Vincula o telegram_id à compra na tabela 'compras'
            cursor.execute(
                "UPDATE compras SET telegram_id = %s WHERE email = %s AND status = 'APPROVED' AND telegram_id IS NULL",
                (telegram_id, email)
            )

            # 2. Atualiza o e-mail do usuário na tabela 'usuarios'
            cursor.execute("UPDATE usuarios SET email = %s WHERE telegram_id = %s", (email, telegram_id))

            # 3. Calcula a data de expiração
            if "Anual" in plano:
                data_expiracao = datetime.now() + timedelta(days=365)
            elif plano == "Teste Gratuito":
                data_expiracao = datetime.now() + timedelta(days=TESTE_GRATUITO_DURACAO_DIAS)
            else:
                data_expiracao = datetime.now() + timedelta(days=31)

            # 4. Atualiza o status completo do usuário
            cursor.execute("""
                UPDATE usuarios SET
                    status_pagamento = %s,
                    plano_assinado = %s,
                    nivel = 2,
                    data_expiracao = %s,
                    status_canal = 'ativo',
                    ultimo_aviso_expiracao = NULL
                WHERE telegram_id = %s
            """, (status, plano, data_expiracao, telegram_id))

            # 5. Marca o teste gratuito como usado, se for o caso
            if plano == "Teste Gratuito":
                cursor.execute("UPDATE usuarios SET usou_teste_gratuito = TRUE WHERE telegram_id = %s", (telegram_id,))

            conn.commit()
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro ao vincular compra e ativar usuário {telegram_id}: {e}")
        conn.rollback()
        raise e  # Re-lança a exceção para ser tratada pela camada superior
    finally:
        conn.close()


def compra_aprovada(email: str) -> bool:
    """Verifica se existe alguma compra aprovada para o e-mail."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM compras WHERE email = %s AND status = 'aprovado' LIMIT 1", (email,))
            return cursor.fetchone() is not None
    finally:
        conn.close()


def plano_comprado(email: str) -> Optional[str]:
    """Busca o último plano comprado pelo e-mail."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT plano FROM compras WHERE email = %s ORDER BY criado_em DESC LIMIT 1", (email,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else None
    finally:
        conn.close()


def atualizar_status_compra(email: str, novo_status: str):
    """Atualiza o status de uma compra pelo e-mail."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE compras SET status = %s WHERE email = %s", (novo_status, email))
            conn.commit()
    finally:
        conn.close()


def desativar_assinatura_por_email(email: str, novo_status: str = 'expirado') -> Optional[int]:
    """Desativa a assinatura de um usuário e retorna seu telegram_id."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT telegram_id FROM usuarios WHERE LOWER(email) = LOWER(%s) AND nivel = 2", (email,))
            resultado = cursor.fetchone()
            
            if not resultado:
                return None

            telegram_id = resultado[0]
            
            cursor.execute(
                "UPDATE usuarios SET nivel = 4, status_pagamento = %s, status_canal = 'removido' WHERE telegram_id = %s",
                (novo_status, telegram_id)
            )
            
            conn.commit()
            return telegram_id
    finally:
        conn.close()


def atualizar_data_expiracao(email: str, nova_data: datetime):
    """Atualiza a data de expiração e reativa o usuário (nível 2)."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE usuarios
                SET data_expiracao = %s, nivel = 2, status_canal = 'ativo', ultimo_aviso_expiracao = NULL
                WHERE LOWER(email) = LOWER(%s)
            """, (nova_data, email))
            conn.commit()
    finally:
        conn.close()

# --- FUNÇÕES DE LÓGICA DE ATIVAÇÃO E ASSINATURA ---

def vincular_compra_e_ativar_usuario(telegram_id: int, email: str, plano: str, status: str):
    """Vincula uma compra aprovada e ativa o status do usuário em uma única transação."""
    from datetime import datetime, timedelta
    from configuracoes import TESTE_GRATUITO_DURACAO_DIAS

    if plano == "Teste Gratuito" and usuario_ja_usou_teste(telegram_id):
        raise ValueError("Você já utilizou o período de teste gratuito.")

    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # 1. Vincula o telegram_id à compra (se ainda não estiver vinculado)
            cursor.execute(
                "UPDATE compras SET telegram_id = %s WHERE LOWER(email) = LOWER(%s) AND status = 'APPROVED' AND telegram_id IS NULL",
                (telegram_id, email)
            )

            # 2. Atualiza o e-mail do usuário
            cursor.execute("UPDATE usuarios SET email = %s WHERE telegram_id = %s", (email, telegram_id))

            # 3. Calcula a data de expiração
            if "Anual" in plano:
                data_expiracao = datetime.now() + timedelta(days=365)
            elif plano == "Teste Gratuito":
                data_expiracao = datetime.now() + timedelta(days=TESTE_GRATUITO_DURACAO_DIAS)
            else:  # Planos mensais
                data_expiracao = datetime.now() + timedelta(days=31)

            # 4. Atualiza o status completo do usuário
            cursor.execute("""
                UPDATE usuarios SET
                    status_pagamento = %s,
                    plano_assinado = %s,
                    nivel = 2,
                    data_expiracao = %s,
                    status_canal = 'ativo',
                    ultimo_aviso_expiracao = NULL
                WHERE telegram_id = %s
            """, (status, plano, data_expiracao, telegram_id))

            # 5. Marca o teste gratuito como usado
            if plano == "Teste Gratuito":
                cursor.execute("UPDATE usuarios SET usou_teste_gratuito = TRUE WHERE telegram_id = %s", (telegram_id,))

            conn.commit()
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro na transação de ativação do usuário {telegram_id}: {e}")
        if conn:
            conn.rollback()
        raise e  # Re-lança a exceção para ser tratada pela camada que a chamou
    finally:
        if conn:
            conn.close()


def desativar_assinatura_por_email(email: str, novo_status: str = 'expirado') -> Optional[int]:
    """Desativa a assinatura de um usuário (nível 4) e retorna seu telegram_id."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # Busca o telegram_id do usuário ativo
            cursor.execute("SELECT telegram_id FROM usuarios WHERE LOWER(email) = LOWER(%s) AND nivel = 2", (email,))
            resultado = cursor.fetchone()
            
            if not resultado:
                return None

            telegram_id = resultado[0]
            
            # Atualiza o status do usuário para desativado
            cursor.execute(
                "UPDATE usuarios SET nivel = 4, status_pagamento = %s, status_canal = 'removido' WHERE telegram_id = %s",
                (novo_status, telegram_id)
            )
            
            conn.commit()
            return telegram_id
    finally:
        conn.close()


def atualizar_data_expiracao(email: str, nova_data: datetime):
    """Atualiza a data de expiração e reativa um usuário (nível 2)."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE usuarios
                SET data_expiracao = %s, nivel = 2, status_canal = 'ativo', ultimo_aviso_expiracao = NULL
                WHERE LOWER(email) = LOWER(%s)
            """, (nova_data, email))
            conn.commit()
    finally:
        conn.close()

# --- FUNÇÕES DE GERENCIAMENTO DE CONFIGURAÇÃO DO CANAL ---

def salvar_configuracao_canal_completa(telegram_id: int, twitch_client_id: str, twitch_client_secret: str, streamers: list, modo: str, clipador_chefe: Optional[str] = None, modo_parceiro: str = 'somente_bot'):
    """Salva a configuração completa de um canal, atualizando ou inserindo um novo registro."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            streamers_str = ",".join(streamers)
            plano = obter_plano_usuario(telegram_id)
            slots_iniciais = obter_slots_base_plano(plano)

            # Verifica se já existe uma configuração para este usuário
            cursor.execute("SELECT id FROM configuracoes_canal WHERE telegram_id = %s", (telegram_id,))
            existe = cursor.fetchone()

            if existe:
                # Atualiza a configuração existente
                cursor.execute("""
                    UPDATE configuracoes_canal
                    SET twitch_client_id = %s, twitch_client_secret = %s, streamers_monitorados = %s, 
                        modo_monitoramento = %s, slots_ativos = %s, streamers_ultima_modificacao = CURRENT_TIMESTAMP, 
                        clipador_chefe_username = %s, modo_parceiro = %s
                    WHERE telegram_id = %s
                """, (twitch_client_id, twitch_client_secret, streamers_str, modo, slots_iniciais, clipador_chefe, modo_parceiro, telegram_id))
            else:
                # Insere uma nova configuração
                cursor.execute("""
                    INSERT INTO configuracoes_canal (
                        telegram_id, twitch_client_id, twitch_client_secret, streamers_monitorados, 
                        modo_monitoramento, slots_ativos, streamers_ultima_modificacao, 
                        clipador_chefe_username, modo_parceiro
                    ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                """, (telegram_id, twitch_client_id, twitch_client_secret, streamers_str, modo, slots_iniciais, clipador_chefe, modo_parceiro))
            
            conn.commit()
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro ao salvar configuração completa para {telegram_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def buscar_configuracao_canal(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Busca a configuração de canal de um usuário e retorna como um dicionário."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM configuracoes_canal WHERE telegram_id = %s", (telegram_id,))
            resultado = cursor.fetchone()
            return dict(resultado) if resultado else None
    finally:
        conn.close()


def buscar_link_canal(telegram_id: int) -> Optional[str]:
    """Busca o link do canal do Telegram de um usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT link_canal_telegram FROM configuracoes_canal WHERE telegram_id = %s", (telegram_id,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else None
    finally:
        conn.close()


def salvar_link_canal(telegram_id: int, id_canal: str, link_canal: str):
    """Salva o ID e o link do canal do Telegram na configuração do usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE configuracoes_canal SET id_canal_telegram = %s, link_canal_telegram = %s WHERE telegram_id = %s",
                (id_canal, link_canal, telegram_id)
            )
            conn.commit()
    finally:
        conn.close()


def deletar_configuracao_canal(telegram_id: int):
    """Remove a linha de configuração de um usuário da tabela configuracoes_canal."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = %s", (telegram_id,))
            conn.commit()
    finally:
        conn.close()


def obter_slots_base_plano(plano: Optional[str]) -> int:
    """Retorna a quantidade base de slots para um determinado plano (não interage com o DB)."""
    if plano == "Mensal Solo": return 1
    if plano == "Mensal Plus": return 3
    if plano == "Anual Pro": return 4  # 3 do plano + 1 de bônus
    if plano == "PARCEIRO": return 1
    if plano == "Teste Gratuito": return 1
    if plano == "SUPER": return 999
    return 1  # Padrão para planos não reconhecidos ou nulos


def adicionar_slot_extra(telegram_id: int, quantidade: int = 1):
    """Adiciona um ou mais slots extras para o usuário, incrementando o contador."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE configuracoes_canal SET slots_ativos = slots_ativos + %s WHERE telegram_id = %s",
                (quantidade, telegram_id)
            )
            conn.commit()
        logger.info(f"{quantidade} slot(s) extra(s) adicionado(s) para o usuário {telegram_id}.")
    finally:
        conn.close()


def remover_slots_extras(telegram_id: int):
    """Reseta os slots de um usuário para o valor base do seu plano."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            plano = obter_plano_usuario(telegram_id)
            slots_base = obter_slots_base_plano(plano)

            cursor.execute("UPDATE configuracoes_canal SET slots_ativos = %s WHERE telegram_id = %s", (slots_base, telegram_id))
            
            if cursor.rowcount == 0:
                raise ValueError(f"Usuário {telegram_id} não possui um canal configurado para remover slots.")

            conn.commit()
            logger.info(f"Slots extras removidos para o usuário {telegram_id}. Slots resetados para {slots_base}.")
    finally:
        conn.close()


def atualizar_configuracao_manual(telegram_id: int, min_clips: int = None, interval_sec: int = None, min_clips_vod: int = None):
    """Atualiza os parâmetros de configuração manual de um usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            updates = []
            params = []

            if min_clips is not None:
                updates.append("manual_min_clips = %s")
                params.append(min_clips)
            if interval_sec is not None:
                updates.append("manual_interval_sec = %s")
                params.append(interval_sec)
            if min_clips_vod is not None:
                updates.append("manual_min_clips_vod = %s")
                params.append(min_clips_vod)

            if not updates:
                return

            params.append(telegram_id)
            query = f"UPDATE configuracoes_canal SET {', '.join(updates)} WHERE telegram_id = %s"
            
            cursor.execute(query, tuple(params))
            conn.commit()
            logger.info(f"Configuração manual atualizada para o usuário {telegram_id}.")
    finally:
        conn.close()


def atualizar_modo_monitoramento(telegram_id: int, novo_modo: str):
    """Atualiza apenas o modo de monitoramento de um canal."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE configuracoes_canal SET modo_monitoramento = %s WHERE telegram_id = %s", (novo_modo, telegram_id))
            conn.commit()
    finally:
        conn.close()


def atualizar_streamers_monitorados(telegram_id: int, nova_lista_streamers: list[str]):
    """Atualiza a lista de streamers monitorados."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            streamers_str = ",".join(nova_lista_streamers)
            cursor.execute(
                "UPDATE configuracoes_canal SET streamers_monitorados = %s WHERE telegram_id = %s",
                (streamers_str, telegram_id)
            )
            conn.commit()
    finally:
        conn.close()


def resetar_cooldown_streamers(telegram_id: int):
    """Reseta o cooldown para alteração de streamers, permitindo modificações."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE configuracoes_canal SET streamers_ultima_modificacao = NULL WHERE telegram_id = %s", (telegram_id,))
            
            if cursor.rowcount == 0:
                raise ValueError(f"Usuário {telegram_id} não possui um canal configurado.")

            conn.commit()
            logger.info(f"Cooldown de alteração de streamers resetado para o usuário {telegram_id}.")
    finally:
        conn.close()

# --- FUNÇÕES DE PROGRESSO DE CONFIGURAÇÃO E ESTADO ---

def marcar_configuracao_completa(telegram_id: int, status: bool):
    """Marca o status de configuração finalizada para um usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET configuracao_finalizada = %s WHERE telegram_id = %s", (status, telegram_id))
            conn.commit()
    finally:
        conn.close()


def is_configuracao_completa(telegram_id: int) -> bool:
    """Verifica se a configuração do usuário está marcada como completa."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT configuracao_finalizada FROM usuarios WHERE telegram_id = %s", (telegram_id,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else False
    finally:
        conn.close()


def assinatura_em_configuracao(telegram_id: int) -> bool:
    """Verifica se um assinante ativo ainda tem campos de configuração pendentes."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT u.nivel, c.twitch_client_id, c.streamers_monitorados, c.modo_monitoramento
                FROM usuarios u
                LEFT JOIN configuracoes_canal c ON u.telegram_id = c.telegram_id
                WHERE u.telegram_id = %s AND u.nivel = 2
            """, (telegram_id,))
            resultado = cursor.fetchone()

            if not resultado:
                return False

            campos_pendentes = not resultado['twitch_client_id'] or not resultado['streamers_monitorados'] or not resultado['modo_monitoramento']
            return campos_pendentes
    finally:
        conn.close()


def salvar_progresso_configuracao(telegram_id: int, etapa: str, dados_parciais: dict = None):
    """Salva dados parciais da configuração do canal, atualizando ou inserindo conforme necessário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            existing_config = buscar_configuracao_canal(telegram_id)
            dados_parciais = dados_parciais or {}

            if existing_config:
                # Monta a query de UPDATE
                update_fields = []
                update_values = []
                if "twitch_client_id" in dados_parciais:
                    update_fields.append("twitch_client_id = %s")
                    update_values.append(dados_parciais["twitch_client_id"])
                if "twitch_client_secret" in dados_parciais:
                    update_fields.append("twitch_client_secret = %s")
                    update_values.append(dados_parciais["twitch_client_secret"])
                if "streamers" in dados_parciais:
                    streamers_str = ",".join(dados_parciais["streamers"])
                    update_fields.append("streamers_monitorados = %s")
                    update_values.append(streamers_str)
                    if etapa == "streamers":
                        update_fields.append("streamers_ultima_modificacao = CURRENT_TIMESTAMP")
                if "modo" in dados_parciais:
                    update_fields.append("modo_monitoramento = %s")
                    update_values.append(dados_parciais["modo"])

                if update_fields:
                    query = f"UPDATE configuracoes_canal SET {', '.join(update_fields)} WHERE telegram_id = %s"
                    update_values.append(telegram_id)
                    cursor.execute(query, tuple(update_values))
            else:
                # Monta a query de INSERT
                fields = ["telegram_id"]
                values_placeholders = ["%s"]
                values = [telegram_id]

                if "twitch_client_id" in dados_parciais:
                    fields.append("twitch_client_id")
                    values_placeholders.append("%s")
                    values.append(dados_parciais["twitch_client_id"])
                if "twitch_client_secret" in dados_parciais:
                    fields.append("twitch_client_secret")
                    values_placeholders.append("%s")
                    values.append(dados_parciais["twitch_client_secret"])
                if "streamers" in dados_parciais:
                    fields.append("streamers_monitorados")
                    values_placeholders.append("%s")
                    values.append(",".join(dados_parciais["streamers"]))
                    fields.append("streamers_ultima_modificacao")
                    values_placeholders.append("CURRENT_TIMESTAMP") # Adicionado diretamente na query
                if "modo" in dados_parciais:
                    fields.append("modo_monitoramento")
                    values_placeholders.append("%s")
                    values.append(dados_parciais["modo"])
                
                query = f"INSERT INTO configuracoes_canal ({', '.join(fields)}) VALUES ({', '.join(values_placeholders)})"
                cursor.execute(query, tuple(values))

            conn.commit()
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro ao salvar progresso de configuração para {telegram_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def buscar_progresso_configuracao(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Busca o progresso da configuração de um canal."""
    config = buscar_configuracao_canal(telegram_id)
    if not config:
        return None

    progresso = {}
    if config.get("modo_monitoramento"):
        progresso["modo_monitoramento"] = config["modo_monitoramento"]
    if config.get("streamers_monitorados"):
        progresso["streamers_monitorados"] = config["streamers_monitorados"]
    return progresso if progresso else None


def limpar_progresso_configuracao(telegram_id: int):
    """Limpa os dados de configuração de um canal, mantendo o registro."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE configuracoes_canal
                SET twitch_client_id = NULL, twitch_client_secret = NULL, 
                    streamers_monitorados = NULL, modo_monitoramento = NULL
                WHERE telegram_id = %s
            """, (telegram_id,))
            conn.commit()
    finally:
        conn.close()

# --- FUNÇÕES DE TESTE E ADMIN (CRUD DE USUÁRIO) ---

async def revogar_acesso_teste_expirado(telegram_id: int):
    """
    Revoga o acesso de um usuário de teste expirado, deletando o canal do Telegram,
    a configuração do canal no DB e atualizando o status do usuário.
    """
    from core.telethon_criar_canal import deletar_canal_telegram
    logger.info(f"Iniciando revogação de acesso de teste para o usuário {telegram_id}.")
    
    config = buscar_configuracao_canal(telegram_id)
    if config and config.get('id_canal_telegram'):
        try:
            id_canal = int(config['id_canal_telegram'])
            await deletar_canal_telegram(id_canal)
            logger.info(f"Canal do Telegram {id_canal} (teste expirado) para o usuário {telegram_id} deletado.")
        except Exception as e:
            logger.error(f"Erro ao deletar canal de teste expirado {config.get('id_canal_telegram')} para {telegram_id}: {e}", exc_info=True)

    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("""
                UPDATE usuarios SET 
                    plano_assinado = NULL, 
                    nivel = 4, 
                    status_pagamento = 'trial_expired',
                    configuracao_finalizada = FALSE, 
                    data_expiracao = NULL, 
                    status_canal = 'removido' 
                WHERE telegram_id = %s
            """, (telegram_id,))
            conn.commit()
            logger.info(f"Configuração e status do usuário de teste {telegram_id} resetados no banco de dados.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro de DB ao revogar acesso de teste para {telegram_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


async def resetar_estado_usuario_para_teste(telegram_id: int):
    """
    APAGA COMPLETAMENTE um usuário e todos os seus dados associados,
    incluindo o canal do Telegram, para fins de teste.
    """
    from core.telethon_criar_canal import deletar_canal_telegram
    config = buscar_configuracao_canal(telegram_id)
    if config and config.get('id_canal_telegram'):
        try:
            await deletar_canal_telegram(int(config['id_canal_telegram']))
            logger.info(f"Canal do Telegram para o usuário {telegram_id} deletado.")
        except Exception as e:
            logger.error(f"Erro ao deletar canal do Telegram para {telegram_id}: {e}", exc_info=True)

    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # A ordem de exclusão é importante para respeitar as chaves estrangeiras
            cursor.execute("DELETE FROM historico_envios WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM compras WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM status_streamers WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM notificacoes_config WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM usuarios WHERE telegram_id = %s", (telegram_id,))
            conn.commit()
            logger.info(f"Todos os dados do usuário {telegram_id} foram removidos do banco de dados.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro ao deletar dados do usuário {telegram_id} do banco de dados: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def conceder_plano_usuario(telegram_id: int, plano: str, dias: int):
    """Concede um plano a um usuário, ativando-o e definindo a data de expiração."""
    from datetime import datetime, timedelta
    
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            plano_antigo = obter_plano_usuario(telegram_id)
            data_expiracao = datetime.now() + timedelta(days=dias)

            cursor.execute("""
                UPDATE usuarios SET
                    plano_assinado = %s, nivel = 2, data_expiracao = %s, ultimo_aviso_expiracao = NULL,
                    status_pagamento = 'approved_admin', status_canal = 'ativo'
                WHERE telegram_id = %s
            """, (plano, data_expiracao, telegram_id))

            slots_base_novo = obter_slots_base_plano(plano)
            config = buscar_configuracao_canal(telegram_id)
            
            if config:
                slots_atuais = config.get('slots_ativos', 1)
                slots_base_antigo = obter_slots_base_plano(plano_antigo)
                slots_extras_comprados = max(0, slots_atuais - slots_base_antigo)
                novos_slots_totais = slots_base_novo + slots_extras_comprados
                cursor.execute(
                    "UPDATE configuracoes_canal SET slots_ativos = %s WHERE telegram_id = %s",
                    (novos_slots_totais, telegram_id)
                )

            conn.commit()
            logger.info(f"Plano '{plano}' concedido ao usuário {telegram_id} por {dias} dias via admin.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro ao conceder plano para {telegram_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# --- FUNÇÕES DE GERENCIAMENTO DE STATUS (AVISOS, TESTES, STREAMERS) ---

def marcar_aviso_enviado(telegram_id: int):
    """Marca que o aviso do canal gratuito foi enviado para o usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET aviso_canal_gratuito_enviado = TRUE WHERE telegram_id = %s", (telegram_id,))
            conn.commit()
    finally:
        conn.close()


def verificar_aviso_enviado(telegram_id: int) -> bool:
    """Verifica se o aviso do canal gratuito já foi enviado para o usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT aviso_canal_gratuito_enviado FROM usuarios WHERE telegram_id = %s", (telegram_id,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else False
    finally:
        conn.close()


def usuario_ja_usou_teste(telegram_id: int) -> bool:
    """Verifica se um usuário já ativou o teste gratuito."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT usou_teste_gratuito FROM usuarios WHERE telegram_id = %s", (telegram_id,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else False
    finally:
        conn.close()


def resetar_flag_teste_gratuito(telegram_id: int):
    """Reseta a flag 'usou_teste_gratuito' para FALSE."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET usou_teste_gratuito = FALSE WHERE telegram_id = %s", (telegram_id,))
            conn.commit()
            
            if cursor.rowcount == 0:
                raise ValueError(f"Usuário com ID {telegram_id} não encontrado.")
    finally:
        conn.close()
    logger.info(f"Flag de teste gratuito resetada para o usuário {telegram_id}.")


def obter_status_streamer(telegram_id: int, streamer_id: str) -> Optional[str]:
    """Obtém o último status conhecido de um streamer ('online' ou 'offline')."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM status_streamers WHERE telegram_id = %s AND streamer_id = %s", (telegram_id, streamer_id))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else None
    finally:
        conn.close()


def atualizar_status_streamer(telegram_id: int, streamer_id: str, novo_status: str):
    """Atualiza ou insere o status de um streamer usando ON CONFLICT para eficiência."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO status_streamers (telegram_id, streamer_id, status, ultima_verificacao)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (telegram_id, streamer_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    ultima_verificacao = CURRENT_TIMESTAMP
            """, (telegram_id, streamer_id, novo_status))
            conn.commit()
    finally:
        conn.close()

# --- FUNÇÕES DE HISTÓRICO DE ENVIOS ---

def registrar_grupo_enviado(telegram_id: int, streamer_id: str, grupo_inicio: datetime, grupo_fim: datetime):
    """Registra que um grupo de clipes foi enviado para um usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO historico_envios (telegram_id, streamer_id, grupo_inicio, grupo_fim)
                VALUES (%s, %s, %s, %s)
            """, (telegram_id, streamer_id, grupo_inicio, grupo_fim))
            conn.commit()
    finally:
        conn.close()


def verificar_grupo_ja_enviado(telegram_id: int, streamer_id: str, grupo_inicio: datetime, grupo_fim: datetime) -> bool:
    """Verifica se um grupo de clipes com sobreposição de tempo já foi enviado."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # A lógica de sobreposição (StartA <= EndB) and (EndA >= StartB) é mantida.
            cursor.execute("""
                SELECT 1 FROM historico_envios
                WHERE telegram_id = %s AND streamer_id = %s AND grupo_inicio <= %s AND grupo_fim >= %s
                LIMIT 1
            """, (telegram_id, streamer_id, grupo_fim, grupo_inicio))
            return cursor.fetchone() is not None
    finally:
        conn.close()


def registrar_clipe_chefe_enviado(telegram_id: int, clipe_id: str):
    """Registra que um clipe individual do chefe foi enviado."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO historico_envios (telegram_id, clipe_id, streamer_id, grupo_inicio, grupo_fim)
                VALUES (%s, %s, 'clipador_chefe', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (telegram_id, clipe_id))
            conn.commit()
    finally:
        conn.close()


def verificar_clipe_chefe_ja_enviado(telegram_id: int, clipe_id: str) -> bool:
    """Verifica se um clipe específico do chefe já foi enviado."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM historico_envios WHERE telegram_id = %s AND clipe_id = %s LIMIT 1", (telegram_id, clipe_id))
            return cursor.fetchone() is not None
    finally:
        conn.close()

# --- FUNÇÕES DE NOTIFICAÇÕES E ESTATÍSTICAS ---

def obter_ou_criar_config_notificacao(telegram_id: int) -> Dict[str, Any]:
    """
    Busca a configuração de notificação de um usuário.
    Se não existir, cria uma com valores padrão e a retorna.
    """
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Tenta inserir com os valores padrão, se o telegram_id já existir, não faz nada.
            cursor.execute("""
                INSERT INTO notificacoes_config (telegram_id, notificar_online)
                VALUES (%s, TRUE)
                ON CONFLICT (telegram_id) DO NOTHING
            """, (telegram_id,))
            
            # Busca a configuração (que agora garantidamente existe)
            cursor.execute("SELECT * FROM notificacoes_config WHERE telegram_id = %s", (telegram_id,))
            config = cursor.fetchone()
            conn.commit()
            return dict(config)
    finally:
        conn.close()


def atualizar_config_notificacao(telegram_id: int, notificar_online: bool = None):
    """Atualiza as configurações de notificação de um usuário."""
    if notificar_online is None:
        return

    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # Garante que a configuração exista antes de atualizar
            obter_ou_criar_config_notificacao(telegram_id)
            
            cursor.execute(
                "UPDATE notificacoes_config SET notificar_online = %s WHERE telegram_id = %s",
                (notificar_online, telegram_id)
            )
            conn.commit()
            logger.info(f"Configuração de notificação atualizada para o usuário {telegram_id}.")
    finally:
        conn.close()


def obter_estatisticas_gerais() -> Dict[str, int]:
    """Busca estatísticas gerais do bot."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            total_usuarios = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE nivel = 2")
            assinantes_ativos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM configuracoes_canal WHERE id_canal_telegram IS NOT NULL")
            canais_monitorados = cursor.fetchone()[0]

            return {
                "total_usuarios": total_usuarios,
                "assinantes_ativos": assinantes_ativos,
                "canais_monitorados": canais_monitorados
            }
    finally:
        conn.close()


def buscar_usuarios_para_notificar_expiracao() -> List[Dict[str, Any]]:
    """
    Busca usuários cujas assinaturas estão próximas de expirar e que precisam ser notificados.
    """
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # A lógica é convertida para usar as funções de data e hora do PostgreSQL.
            # (data_expiracao - NOW()) resulta em um intervalo, que pode ser convertido para dias.
            cursor.execute("""
                SELECT 
                    telegram_id, 
                    EXTRACT(DAY FROM (data_expiracao - NOW())) AS dias_restantes
                FROM usuarios
                WHERE 
                    nivel = 2 AND data_expiracao IS NOT NULL
                    AND (
                        (EXTRACT(DAY FROM (data_expiracao - NOW())) <= 7 AND (ultimo_aviso_expiracao IS NULL OR ultimo_aviso_expiracao > 7)) OR
                        (EXTRACT(DAY FROM (data_expiracao - NOW())) <= 3 AND (ultimo_aviso_expiracao IS NULL OR ultimo_aviso_expiracao > 3)) OR
                        (EXTRACT(DAY FROM (data_expiracao - NOW())) <= 1 AND (ultimo_aviso_expiracao IS NULL OR ultimo_aviso_expiracao > 1)) OR
                        (EXTRACT(DAY FROM (data_expiracao - NOW())) <= 0 AND (ultimo_aviso_expiracao IS NULL OR ultimo_aviso_expiracao > 0))
                    )
            """)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def atualizar_ultimo_aviso_expiracao(telegram_id: int, dias_aviso: int):
    """Atualiza o campo ultimo_aviso_expiracao para um usuário."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET ultimo_aviso_expiracao = %s WHERE telegram_id = %s", (dias_aviso, telegram_id))
            conn.commit()
            logger.info(f"Aviso de expiração de {dias_aviso} dias atualizado para o usuário {telegram_id}.")
    finally:
        conn.close()

# --- FUNÇÕES UTILITÁRIAS E DE BUSCA ---

def buscar_usuarios_ativos_configurados() -> List[Dict[str, Any]]:
    """
    Busca todos os usuários que são assinantes ativos (nível 2) e que
    finalizaram a configuração do canal. Retorna uma lista de dicionários.
    """
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT c.* FROM configuracoes_canal c
                JOIN usuarios u ON c.telegram_id = u.telegram_id
                WHERE u.nivel = 2 AND u.configuracao_finalizada = TRUE
            """)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def buscar_usuario_por_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Busca os dados de um usuário pelo seu telegram_id e retorna como dicionário."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE telegram_id = %s", (telegram_id,))
            resultado = cursor.fetchone()
            return dict(resultado) if resultado else None
    finally:
        conn.close()


def buscar_usuario_por_email(email: str) -> Optional[Dict[str, Any]]:
    """Busca os dados de um usuário pelo seu email e retorna como dicionário."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
            resultado = cursor.fetchone()
            return dict(resultado) if resultado else None
    finally:
        conn.close()


def buscar_ids_assinantes_ativos() -> List[int]:
    """Busca os IDs de todos os usuários que são assinantes ativos (nível 2)."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT telegram_id FROM usuarios WHERE nivel = 2")
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

def buscar_pagamento_por_email(email: str) -> Optional[Dict[str, Any]]:
    """Busca o pagamento mais recente por email na tabela compras."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM compras WHERE LOWER(email) = LOWER(%s) ORDER BY criado_em DESC LIMIT 1",
                (email.strip(),)
            )
            resultado = cursor.fetchone()
            return dict(resultado) if resultado else None
    finally:
        conn.close()


def buscar_compra_aprovada_por_email(email: str) -> Optional[Dict[str, Any]]:
    """Busca a compra aprovada mais recente por email na tabela compras."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM compras
                WHERE LOWER(email) = LOWER(%s) AND status = 'aprovado'
                ORDER BY criado_em DESC
                LIMIT 1
            """, (email.strip(),))
            resultado = cursor.fetchone()
            return dict(resultado) if resultado else None
    finally:
        conn.close()

def buscar_compras_aprovadas_nao_vinculadas(email: str) -> List[Dict[str, Any]]:
    """Busca todas as compras aprovadas de um e-mail que ainda não foram vinculadas a um telegram_id."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM compras
                WHERE LOWER(email) = LOWER(%s) AND status = 'aprovado' AND telegram_id IS NULL
                ORDER BY criado_em DESC
            """, (email.strip(),))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

# --- FUNÇÕES QUE NÃO INTERAGEM COM O BANCO DE DADOS ---

def registrar_log_pagamento(telegram_id, email, plano, status):
    """Registra um log de pagamento em um arquivo de texto."""
    dados = f"[{datetime.now()}] ID: {telegram_id}, Email: {email}, Plano: {plano}, Status: {status}\n"
    try:
        os.makedirs("memoria", exist_ok=True)
        with open("memoria/log_pagamentos.txt", "a", encoding="utf-8") as f:
            f.write(dados)
    except IOError as e:
        logger.error(f"Erro ao escrever no log de pagamentos: {e}")

def registrar_evento_webhook(dados: dict):
    """Registra o corpo de um evento de webhook em um arquivo de texto."""
    log_data = f"[{datetime.now()}] {dados}\n"
    try:
        os.makedirs("memoria", exist_ok=True)
        with open("memoria/log_eventos_webhook.txt", "a", encoding="utf-8") as f:
            f.write(log_data)
    except IOError as e:
        logger.error(f"Erro ao escrever no log de webhooks: {e}")

# --- FUNÇÕES ADICIONAIS DE GERENCIAMENTO DE USUÁRIOS ---

def atualizar_dados_usuario(telegram_id: int, nome: Optional[str] = None, nivel: Optional[int] = None):
    """Atualiza o nome e/ou o nível de um usuário específico."""
    if nome is None and nivel is None:
        return # Nada a fazer

    conn = conectar()
    try:
        with conn.cursor() as cursor:
            updates = []
            params = []

            if nome is not None:
                updates.append("nome = %s")
                params.append(nome)
            
            if nivel is not None:
                updates.append("nivel = %s")
                params.append(nivel)
            
            params.append(telegram_id)
            query = f"UPDATE usuarios SET {', '.join(updates)} WHERE telegram_id = %s"
            
            cursor.execute(query, tuple(params))
            conn.commit()
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro ao atualizar dados para o usuário {telegram_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def remover_usuario_por_id(telegram_id: int):
    """
    Remove um usuário e todos os seus dados associados (compras, configurações, etc.)
    em uma única transação.
    """
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            # A ordem de exclusão é importante para respeitar as chaves estrangeiras
            logger.warning(f"Iniciando remoção completa do usuário {telegram_id}.")
            cursor.execute("DELETE FROM historico_envios WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM compras WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM status_streamers WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM configuracoes_canal WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM notificacoes_config WHERE telegram_id = %s", (telegram_id,))
            cursor.execute("DELETE FROM usuarios WHERE telegram_id = %s", (telegram_id,)) # Por último
            conn.commit()
            logger.info(f"Usuário {telegram_id} removido com sucesso de todas as tabelas.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"Erro na transação de remoção do usuário {telegram_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def listar_todos_usuarios() -> List[Dict[str, Any]]:
    """Lista todos os usuários e seus principais dados para fins de administração."""
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT id, telegram_id, nome, email, nivel, plano_assinado FROM usuarios ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

# --- FUNÇÕES DE COMPATIBILIDADE RESTAURADAS ---

def atualizar_telegram_id_simples(telegram_id_antigo: int, telegram_id_novo: int):
    """Atualiza o telegram_id usando o valor antigo como referência."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET telegram_id = %s WHERE telegram_id = %s", (telegram_id_novo, telegram_id_antigo))
            conn.commit()
    finally:
        conn.close()

def sale_id_ja_registrado(sale_id: str) -> bool:
    """Função para verificar se sale_id já foi registrado."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM compras WHERE sale_id = %s LIMIT 1", (sale_id,))
            return cursor.fetchone() is not None
    finally:
        conn.close()

# Alias para manter a compatibilidade com o código antigo que usa este nome
compra_ja_registrada = sale_id_ja_registrado        

# --- FUNÇÃO DE INICIALIZAÇÃO ---

def inicializar_banco():
    """
    Função central para ser chamada na inicialização do sistema.
    Cria as tabelas se não existirem e aplica migrações de colunas.
    """
    logger.info("🔧 Inicializando e verificando a estrutura do banco de dados PostgreSQL...")
    criar_tabelas()
    migrar_tabelas()
    logger.info("✅ Banco de dados pronto para uso.")

# IMPORTANTE: Remova as chamadas diretas como criar_tabelas() e migrar_tabelas()
# do final do arquivo. A única função que deve ser chamada externamente é 'inicializar_banco()',
# preferencialmente no arquivo principal de inicialização do seu bot.