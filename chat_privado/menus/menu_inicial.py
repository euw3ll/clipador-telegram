from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from chat_privado.usuarios import get_nivel_usuario

async def responder_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nome = update.effective_user.first_name or "Clipado"
    nivel = get_nivel_usuario(user_id, nome)  # já registra se não existir

    # Mensagem personalizada conforme o tipo de usuário
    if nivel == 1:
        texto = (
            f"👋 Aoba Clipadô! Seja bem-vindo {nome}, que nome lindo 😍\n\n"
            "Aqui você recebe os *melhores momentos das lives* direto no seu Telegram, sem esforço 🎯\n\n"
            "Notei que você *ainda não tem uma assinatura ativa* 😱\n"
            "Mas relaxa... ainda dá tempo de mudar isso 💸"
        )
    elif nivel == 2:
        texto = (
            f"✅ Assinante ativo, tamo junto {nome}!\n\n"
            "Seu Clipador está sempre pronto pra te entregar os melhores clipes 😎"
        )
    elif nivel == 4:
        texto = (
            f"😕 Sua assinatura expirou, {nome}.\n\n"
            "Que tal renovar agora e voltar a receber os melhores momentos automaticamente?"
        )
    elif nivel == 999:
        texto = (
            f"🛠️ Eita porr@, a administração do grupo chegou...\n\n"
            f"E aí {nome}, quer fazer o que hoje? Use o /help para ver as opções."
        )
    else:
        texto = f"👋 Opa {nome}, não consegui identificar seu status 😅\nVamos te colocar no caminho certo!"

    botoes = [
        [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
        [InlineKeyboardButton("💸 Ver planos", callback_data="menu_2")],
    ]

    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )
