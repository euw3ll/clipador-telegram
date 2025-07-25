from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from chat_privado.usuarios import get_nivel_usuario, registrar_usuario, atualizar_usuario, remover_usuario, listar_usuarios

# Estados da criação de canal
ESPERANDO_CLIENT_ID, ESPERANDO_CLIENT_SECRET, ESPERANDO_BOT_TOKEN, ESPERANDO_CHAT_ID, ESPERANDO_STREAMER = range(5)

dados_temp = {}

# 🔧 Início do funil de criação
async def criar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_nivel_usuario(user_id) != 9:
        await update.message.reply_text("🚫 Comando reservado para administradores.")
        return ConversationHandler.END

    await update.message.reply_text("🔧 Vamos criar um novo canal!\n\nInforme o TWITCH_CLIENT_ID:")
    dados_temp[user_id] = {}
    return ESPERANDO_CLIENT_ID

async def receber_client_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    dados_temp[user_id]["TWITCH_CLIENT_ID"] = update.message.text
    await update.message.reply_text("✅ Agora informe o TWITCH_CLIENT_SECRET:")
    return ESPERANDO_CLIENT_SECRET

async def receber_client_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    dados_temp[user_id]["TWITCH_CLIENT_SECRET"] = update.message.text
    await update.message.reply_text("🤖 Agora informe o TELEGRAM_BOT_TOKEN:")
    return ESPERANDO_BOT_TOKEN

async def receber_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    dados_temp[user_id]["TELEGRAM_BOT_TOKEN"] = update.message.text
    await update.message.reply_text("📢 Agora informe o TELEGRAM_CHAT_ID:")
    return ESPERANDO_CHAT_ID

async def receber_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    dados_temp[user_id]["TELEGRAM_CHAT_ID"] = update.message.text
    await update.message.reply_text("🎮 Por fim, qual streamer deseja monitorar?")
    return ESPERANDO_STREAMER

async def receber_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    dados_temp[user_id]["STREAMER"] = update.message.text

    info = dados_temp[user_id]
    resumo = (
        f"✅ Canal configurado com sucesso!\n\n"
        f"TWITCH_CLIENT_ID: {info['TWITCH_CLIENT_ID']}\n"
        f"TWITCH_CLIENT_SECRET: {info['TWITCH_CLIENT_SECRET'][:4]}***\n"
        f"BOT_TOKEN: {info['TELEGRAM_BOT_TOKEN'][:4]}***\n"
        f"CHAT_ID: {info['TELEGRAM_CHAT_ID']}\n"
        f"STREAMER: {info['STREAMER']}"
    )

    await update.message.reply_text(resumo)
    del dados_temp[user_id]
    return ConversationHandler.END

async def cancelar_criacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Criação de canal cancelada.")
    return ConversationHandler.END
