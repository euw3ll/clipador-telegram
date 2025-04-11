import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from .handlers import (
    responder_primeira_interacao,
    criar_canal,
    receber_client_id,
    receber_client_secret,
    receber_bot_token,
    receber_chat_id,
    receber_streamer,
    cancelar_criacao
)
from .usuarios import carregar_db_usuarios
from canal_gratuito.config import TELEGRAM_BOT_TOKEN  # ⬅️ corrigido aqui

def iniciar_chat_privado():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("criarcanal", criar_canal)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_client_id)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_client_secret)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_bot_token)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_chat_id)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_streamer)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar_criacao)]
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_primeira_interacao))

    print("💬 Bot privado iniciado. Aguardando mensagens...")
    app.run_polling()
