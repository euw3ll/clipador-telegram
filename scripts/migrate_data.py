import os
import sys
import sqlite3
import psycopg2
from dotenv import load_dotenv
import logging

# Adiciona o diretório raiz do projeto ao caminho do Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import criar_tabelas, migrar_tabelas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def connect_to_sqlite():
    db_path = os.path.join("banco", "clipador.db")
    if not os.path.exists(db_path):
        logging.error(f"Arquivo SQLite não encontrado: {db_path}")
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        logging.info("✅ Conectado ao SQLite.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"❌ Erro ao conectar ao SQLite: {e}")
        return None

def connect_to_postgres():
    load_dotenv()
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT")
        )
        logging.info("✅ Conectado ao PostgreSQL.")
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"❌ Erro ao conectar ao PostgreSQL: {e}")
        return None

def drop_all_tables(conn):
    logging.warning("🔥 Apagando todas as tabelas existentes no banco de dados de destino...")
    tabelas = [
        "historico_envios", "compras", "status_streamers",
        "notificacoes_config", "configuracoes_canal", "usuarios"
    ]
    with conn.cursor() as cursor:
        for tabela in tabelas:
            cursor.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE;")
            logging.info(f"Tabela '{tabela}' apagada.")
        conn.commit()
    logging.info("✅ Todas as tabelas antigas foram removidas.")

def migrar_dados(sqlite_conn, postgres_conn):
    logging.info("🚚 Iniciando a migração dos dados...")
    
    mapeamento_tabelas_ideal = {
        "usuarios": ["telegram_id", "nome", "email", "nivel", "status_pagamento", "plano_assinado", "configuracao_finalizada", "data_expiracao", "status_canal", "aviso_canal_gratuito_enviado", "ultimo_aviso_expiracao", "usou_teste_gratuito"],
        "configuracoes_canal": ["telegram_id", "id_canal_telegram", "twitch_client_id", "twitch_client_secret", "link_canal_telegram", "streamers_monitorados", "modo_monitoramento", "slots_ativos", "data_criacao", "streamers_ultima_modificacao", "manual_min_clips", "manual_interval_sec", "manual_min_clips_vod", "clipador_chefe_username", "modo_parceiro"],
        "historico_envios": ["telegram_id", "clipe_id", "streamer_id", "grupo_inicio", "grupo_fim", "enviado_em"],
        "status_streamers": ["telegram_id", "streamer_id", "status", "ultima_verificacao"],
        "notificacoes_config": ["telegram_id", "notificar_online"],
        "compras": ["telegram_id", "email", "plano", "metodo_pagamento", "status", "sale_id", "data_criacao", "offer_id", "nome_completo", "telefone", "criado_em"],
    }
    
    ordem_migracao = ["usuarios", "configuracoes_canal", "historico_envios", "status_streamers", "notificacoes_config", "compras"]
    CHUNK_SIZE = 500  # Processa 500 registros por vez

    try:
        with postgres_conn.cursor() as pg_cursor:
            for tabela in ordem_migracao:
                logging.info(f"Processando tabela '{tabela}'...")
                
                sqlite_cursor = sqlite_conn.cursor()
                sqlite_cursor.execute(f"PRAGMA table_info({tabela});")
                colunas_reais_sqlite = [row['name'] for row in sqlite_cursor.fetchall()]
                colunas_ideais = mapeamento_tabelas_ideal[tabela]
                colunas_para_migrar = [col for col in colunas_ideais if col in colunas_reais_sqlite]
                
                if not colunas_para_migrar:
                    logging.warning(f"Nenhuma coluna correspondente para '{tabela}'. Pulando.")
                    continue

                logging.info(f"Colunas a serem migradas para '{tabela}': {', '.join(colunas_para_migrar)}")
                
                sqlite_cursor.execute(f"SELECT {', '.join(colunas_para_migrar)} FROM {tabela}")
                
                registros_migrados = 0
                while True:
                    registros = sqlite_cursor.fetchmany(CHUNK_SIZE)
                    if not registros:
                        break

                    dados_para_inserir = []
                    for reg in registros:
                        reg_dict = dict(reg)
                        for bool_col in ["configuracao_finalizada", "aviso_canal_gratuito_enviado", "usou_teste_gratuito", "notificar_online"]:
                            if bool_col in reg_dict and reg_dict[bool_col] is not None:
                                reg_dict[bool_col] = bool(reg_dict[bool_col])
                        
                        dados_ordenados = tuple(reg_dict.get(col) for col in colunas_para_migrar)
                        dados_para_inserir.append(dados_ordenados)

                    placeholders = ", ".join(["%s"] * len(colunas_para_migrar))
                    query = f"INSERT INTO {tabela} ({', '.join(colunas_para_migrar)}) VALUES ({placeholders})"
                    
                    pg_cursor.executemany(query, dados_para_inserir)
                    registros_migrados += len(dados_para_inserir)
                    logging.info(f"... {registros_migrados} registros migrados para '{tabela}'...")

                if registros_migrados > 0:
                    logging.info(f"✅ Total de {registros_migrados} registros migrados para a tabela '{tabela}'.")
                else:
                    logging.info(f"✅ Tabela '{tabela}' estava vazia no SQLite. Nenhum dado a migrar.")
            
            postgres_conn.commit()
            logging.info("🚚 Migração de dados concluída com sucesso!")
    except (Exception, psycopg2.Error, sqlite3.Error) as e:
        logging.error(f"❌ Erro durante a migração da tabela '{tabela}': {e}")
        postgres_conn.rollback()
        raise e

def main():
    logging.info("🚀 Iniciando script de migração de dados...")
    
    postgres_conn = connect_to_postgres()
    sqlite_conn = connect_to_sqlite()
    
    if not sqlite_conn or not postgres_conn:
        logging.critical("🚨 Abortando a migração.")
        return

    try:
        drop_all_tables(postgres_conn)
        
        logging.info("🔧 Criando o esquema de tabelas no PostgreSQL...")
        criar_tabelas()
        migrar_tabelas()
        logging.info("✅ Esquema de tabelas criado com sucesso.")

        migrar_dados(sqlite_conn, postgres_conn)
        
        logging.info("🎉🎉🎉 Processo de migração finalizado com sucesso! 🎉🎉🎉")
    except Exception as e:
        logging.critical(f"🚨 A migração falhou. Erro: {e}")
    finally:
        if sqlite_conn: sqlite_conn.close()
        if postgres_conn: postgres_conn.close()
        logging.info("🏁 Conexões fechadas.")

if __name__ == "__main__":
    main()