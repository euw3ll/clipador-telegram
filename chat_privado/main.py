from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from chat_privado.handlers import responder_primeira_interacao
from canal_gratuito.config import TELEGRAM_BOT_TOKEN


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_primeira_interacao(update, context)


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
