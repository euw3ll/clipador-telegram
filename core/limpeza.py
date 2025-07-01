import os
import logging
import sqlite3
from datetime import datetime, timedelta

from core.database import conectar

logger = logging.getLogger(__name__)

# --- Constantes de Limpeza ---
DIRETORIO_LOGS = "memoria"
TAMANHO_MAX_LOG_MB = 10
TAMANHO_MAX_LOG_BYTES = TAMANHO_MAX_LOG_MB * 1024 * 1024
LINHAS_A_MANTER_LOG = 10000  # Mantém as últimas 10.000 linhas (~1-2MB)

RETENCAO_HISTORICO_DB_HORAS = 24 # Retenção de 24 horas no DB


def limpar_logs_antigos():
    """
    Verifica a pasta de logs e trunca arquivos .txt que excedem o tamanho máximo,
    mantendo apenas as linhas mais recentes.
    """
    if not os.path.isdir(DIRETORIO_LOGS):
        logger.info(f"Diretório de logs '{DIRETORIO_LOGS}' não encontrado. Pulando limpeza de logs.")
        return

    logger.info("Iniciando verificação de arquivos de log...")
    for filename in os.listdir(DIRETORIO_LOGS):
        if filename.endswith(".txt"):
            filepath = os.path.join(DIRETORIO_LOGS, filename)
            try:
                if os.path.getsize(filepath) > TAMANHO_MAX_LOG_BYTES:
                    logger.warning(f"Arquivo de log '{filepath}' excedeu {TAMANHO_MAX_LOG_MB} MB. Truncando...")

                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        linhas = f.readlines()

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.writelines(linhas[-LINHAS_A_MANTER_LOG:])

                    logger.info(f"✅ Arquivo '{filepath}' truncado. {LINHAS_A_MANTER_LOG} linhas recentes foram mantidas.")
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.error(f"Erro ao processar o arquivo de log '{filepath}': {e}", exc_info=True)


def limpar_historico_banco_dados():
    """
    Remove registros da tabela 'historico_envios' com mais de 24 horas.
    """
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()
        limite_tempo = datetime.now() - timedelta(hours=RETENCAO_HISTORICO_DB_HORAS)

        logger.info(f"Iniciando limpeza do 'historico_envios' (registros com mais de {RETENCAO_HISTORICO_DB_HORAS} horas)...")

        cursor.execute("DELETE FROM historico_envios WHERE enviado_em < ?", (limite_tempo,))
        removidos = cursor.rowcount
        conn.commit()

        if removidos > 0:
            logger.info(f"✅ Limpeza do banco de dados concluída. {removidos} registros antigos removidos.")
        else:
            logger.debug("Nenhum registro antigo encontrado em 'historico_envios' para remover.")

    except sqlite3.Error as e:
        logger.error(f"Erro de banco de dados ao limpar histórico: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()


def executar_limpeza_completa():
    """Executa todas as rotinas de limpeza (logs e banco de dados)."""
    logger.info("--- Iniciando rotina de limpeza periódica ---")
    limpar_logs_antigos()
    limpar_historico_banco_dados()
    logger.info("--- Rotina de limpeza periódica finalizada ---")