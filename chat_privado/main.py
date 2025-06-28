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
    # Aumenta os timeouts para dar mais tempo para a conexão com a API do Telegram
    request = HTTPXRequest(connect_timeout=20.0, read_timeout=20.0)

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request)
    builder.post_init(post_initialization)
    app = builder.build()

    from chat_privado.handlers import registrar_handlers  # agora centralizado
    registrar_handlers(app)
    print("💬 Iniciando bot principal (chat privado e monitores)...")
    app.run_polling()
