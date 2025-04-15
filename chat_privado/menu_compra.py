from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# 💬 Menu principal quando o usuário acessa o bot no privado
async def mostrar_menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Ver planos disponíveis", callback_data="ver_planos")],
        [InlineKeyboardButton("💳 Comprar assinatura", callback_data="comprar_assinatura")],
        [InlineKeyboardButton("🛟 Falar com o suporte", url="https://t.me/seuContatoSuporteAqui")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bem-vindo ao Clipador!\n\n"
        "Escolha uma opção abaixo para continuar:",
        reply_markup=reply_markup
    )

# 📋 Mostra os planos disponíveis
async def ver_planos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    mensagem = (
        "💳 <b>Planos disponíveis:</b>\n\n"
        "🔹 <b>Mensal</b> - R$49,90\n"
        "• 1 streamer fixo\n"
        "• Canal exclusivo no Telegram\n\n"
        "🔸 <b>Anual</b> - R$499,90\n"
        "• Até 3 streamers fixos\n"
        "• Canal exclusivo\n"
        "• Suporte prioritário\n\n"
        "Para contratar, clique em <b>Comprar assinatura</b>!"
    )

    await query.edit_message_text(
        mensagem,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_menu")]
        ])
    )

# 💳 Início do processo de compra
async def comprar_assinatura_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Aqui você poderia gerar QR Code, registrar status de pagamento etc.
    mensagem = (
        "💸 Para comprar sua assinatura, envie um Pix para:\n\n"
        "<b>chavepix@email.com</b>\n"
        "Valor: <b>R$49,90</b> (Plano Mensal)\n\n"
        "Depois do pagamento, envie o comprovante para @SeuContato\n\n"
        "Assim que confirmado, criaremos seu canal automático!"
    )

    await query.edit_message_text(
        mensagem,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_menu")]
        ])
    )

# 🔙 Volta ao menu principal
async def voltar_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await mostrar_menu_principal(query, context)
