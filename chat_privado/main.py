import sys
import os
# Garante que os módulos do projeto possam ser importados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram.ext import Application
from telegram.request import HTTPXRequest
from core.ambiente import TELEGRAM_BOT_TOKEN
import asyncio
import logging # 1. Dependência adicionada para logging
from core.monitor_clientes import iniciar_monitoramento_clientes
from canal_gratuito.main import main as iniciar_monitor_gratuito
from chat_privado.handlers import registrar_handlers

logger = logging.getLogger(__name__)

async def post_initialization(application: Application):
    """
    Função executada após a inicialização do bot.
    Inicia os monitores como tarefas em segundo plano e armazena suas referências.
    """
    logger.info("🚀 Pós-inicialização: Iniciando tarefas de monitoramento...")
    
    # 2. Cria as tarefas e as armazena em 'bot_data' para serem acessíveis no shutdown
    task_gratuito = asyncio.create_task(iniciar_monitor_gratuito(application))
    task_clientes = asyncio.create_task(iniciar_monitoramento_clientes(application))
    
    application.bot_data["monitor_tasks"] = [task_gratuito, task_clientes]
    logger.info("✅ Tarefas de monitoramento iniciadas e rastreadas.")

# 3. NOVA FUNÇÃO: Lida com o encerramento seguro das tarefas
async def post_shutdown(application: Application):
    """
    Função executada antes do desligamento completo do bot.
    Cancela as tarefas de monitoramento de forma segura.
    """
    logger.info("🔌 Pré-desligamento: Cancelando tarefas de monitoramento em segundo plano...")
    tasks = application.bot_data.get("monitor_tasks", [])
    
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                # Aguardamos a tarefa ser efetivamente cancelada.
                # A exceção CancelledError é esperada e indica sucesso no cancelamento.
                await task
            except asyncio.CancelledError:
                logger.info(f"Tarefa {task.get_name()} cancelada com sucesso.")
            except Exception as e:
                # Captura outros erros inesperados durante o cancelamento
                logger.error(f"Erro inesperado ao cancelar a tarefa {task.get_name()}: {e}", exc_info=True)
    
    logger.info("✅ Tarefas em segundo plano encerradas de forma segura.")

def iniciar_chat_privado():
    # Configuração de request para get_updates (long polling)
    get_updates_request = HTTPXRequest(connect_timeout=10.0, read_timeout=60.0)

    # Configuração de request para todas as outras chamadas de API
    api_request = HTTPXRequest(connect_timeout=10.0, read_timeout=10.0, connection_pool_size=50)

    builder = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(api_request)
        .get_updates_request(get_updates_request)
    )

    # Registra as funções de inicialização e desligamento
    builder.post_init(post_initialization)
    builder.post_shutdown(post_shutdown) # 4. Registra a nova função de desligamento

    app = builder.build()

    registrar_handlers(app)
    
    logger.info("💬 Iniciando bot principal (chat privado e monitores)...")
    
    # --- INÍCIO DA ETAPA 1: Desativar os "Ouvintes" de Sinais ---
    # Adicionamos stop_signals=None para evitar o erro de runtime em threads
    app.run_polling(stop_signals=None)
    # --- FIM DA ETAPA 1 ---