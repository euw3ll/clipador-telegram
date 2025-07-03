import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram.ext import Application
from telegram.request import HTTPXRequest
from core.ambiente import TELEGRAM_BOT_TOKEN
import asyncio
from core.monitor_clientes import iniciar_monitoramento_clientes
from canal_gratuito.main import main as iniciar_monitor_gratuito

async def post_initialization(application: Application):
    """Função a ser executada após a inicialização do bot."""
    print("📺 Iniciando monitor do canal gratuito...")
    # Inicia o monitoramento do canal gratuito em background
    asyncio.create_task(iniciar_monitor_gratuito(application))

    # Inicia o monitoramento de clientes em background
    asyncio.create_task(iniciar_monitoramento_clientes(application))

def iniciar_chat_privado():
    # Configuração de request para get_updates (long polling)
    # Não precisa de um pool grande, mas de um read_timeout alto
    get_updates_request = HTTPXRequest(connect_timeout=10.0, read_timeout=60.0)

    # Configuração de request para todas as outras chamadas de API
    # Pool maior para lidar com monitores concorrentes e outras tarefas
    api_request = HTTPXRequest(connect_timeout=10.0, read_timeout=10.0, connection_pool_size=50)

    builder = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(api_request)
        .get_updates_request(get_updates_request)
    )

    builder.post_init(post_initialization)
    app = builder.build()

    from chat_privado.handlers import registrar_handlers  # agora centralizado
    registrar_handlers(app)
    print("💬 Iniciando bot principal (chat privado e monitores)...")
    app.run_polling()
