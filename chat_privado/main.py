import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from .handlers import responder_primeira_interacao
from canal_gratuito.config import TELEGRAM_BOT_TOKEN

def iniciar_chat_privado():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, responder_primeira_interacao)
    )

    asyncio.run(application.run_polling())
