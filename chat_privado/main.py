import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram.ext import Application
from chat_privado.handlers import registrar_handlers  # agora centralizado
from core.ambiente import TELEGRAM_BOT_TOKEN
import asyncio

def iniciar_chat_privado():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    registrar_handlers(app)
    print("💬 Bot privado iniciado. Aguardando mensagens...")
    asyncio.run(app.run_polling())
