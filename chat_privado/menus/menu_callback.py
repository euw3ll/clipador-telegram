from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# menu_0 → Menu principal
async def responder_menu_0(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    texto = (
        "🎯 *Bem-vindo ao Clipador!*\n\n"
        "Receba automaticamente os melhores momentos das lives direto no seu Telegram.\n\n"
        "Selecione abaixo como deseja começar:"
    )

    botoes = [
        [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
        [InlineKeyboardButton("💸 Planos", callback_data="menu_2")],
        [InlineKeyboardButton("📝 Assinar agora", callback_data="menu_3")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_1 → Como funciona
async def responder_menu_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "📚 *COMO FUNCIONA O CLIPADOR*\n\n"
        "🎥 O Clipador monitora automaticamente os streamers que você escolher e envia *os melhores momentos das lives* direto no seu canal no Telegram.\n\n"
        "🔄 *Monitoramento 24h/dia*, sem precisar fazer nada.\n"
        "🧠 O bot identifica grupos de clipes virais e filtra o que realmente importa.\n"
        "📥 Você pode ver o preview do clipe e fazer o download para subir na sua plataforma de preferência.\n\n"
        "💡 *O que são slots?*\n"
        "Cada slot representa 1 streamer monitorado.\n"
        "Você pode contratar mais slots extras para monitorar múltiplos streamers no mesmo canal.\n\n"
        "📊 *Modos de monitoramento:*\n"
        "- Modo Louco 🔥 (envia tudo que viraliza)\n"
        "- Modo Padrão 🎯 (equilíbrio entre qualidade e frequência)\n"
        "- Modo Cirúrgico 🧬 (só clipes realmente bombásticos)"
    )

    botoes = [
        [InlineKeyboardButton("💸 Ver planos", callback_data="menu_2")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_2 → Planos disponíveis
async def responder_menu_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "💸 *PLANOS DO CLIPADOR*\n\n"
        "✅ *Mensal Solo* — R$29,90/mês\n"
        "• 1 canal monitorado\n"
        "• Troca de streamer 1x/mês\n"
        "• Máximo 1 slot adicional (R$14,90 fixo)\n\n"
        "🏆 *Mensal Plus* — R$49,90/mês\n"
        "• Até 3 canais monitorados\n"
        "• Ideal pra clippers/agências\n"
        "• Até 3 slots extras (R$9,90 cada)\n\n"
        "👑 *Anual Pro* — R$299,00/ano\n"
        "• 3 canais + 1 slot bônus\n"
        "• Economia de 2 meses\n"
        "• Até 5 slots extras (R$7,90 cada)"
    )

    botoes = [
        [InlineKeyboardButton("📝 Quero assinar", callback_data="menu_3")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_3 → Assinar (escolher plano)
async def responder_menu_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "🧾 *PLANOS DO CLIPADOR*\n\n"
        "✅ *Mensal Solo* — R$29,90/mês\n"
        "• 1 canal monitorado\n"
        "• Troca de streamer 1x/mês\n"
        "• Máximo 1 slot adicional (R$14,90 fixo)\n\n"
        "🏆 *Mensal Plus* — R$49,90/mês\n"
        "• Até 3 canais monitorados\n"
        "• Ideal pra clippers/agências\n"
        "• Até 3 slots extras (R$9,90 cada)\n\n"
        "👑 *Anual Pro* — R$299,00/ano\n"
        "• 3 canais + 1 slot bônus\n"
        "• Economia de 2 meses\n"
        "• Até 5 slots extras (R$7,90 cada)"
    )

    botoes = [
        [InlineKeyboardButton("💳 Mensal Solo", callback_data="menu_4_mensal")],
        [InlineKeyboardButton("🏆 Mensal Plus", callback_data="menu_4_plus")],
        [InlineKeyboardButton("👑 Anual Pro", callback_data="menu_4_anual")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]

    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_4 → Planos (resumo + confirmar)
async def responder_menu_4_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "📦 *RESUMO DO PLANO MENSAL SOLO*\n\n"
        "💰 R$ 29,90/mês\n"
        "🔹 1 streamer monitorado\n"
        "🔁 Troca de streamer 1x por mês\n"
        "➕ Máximo 1 slot adicional (R$14,90 fixo)\n"
        "📅 Renovação mensal\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Confirmar assinatura", callback_data="menu_5_mensal")],
        [InlineKeyboardButton("🔙 Voltar para planos", callback_data="menu_3")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


async def responder_menu_4_plus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "📦 *RESUMO DO PLANO MENSAL PLUS*\n\n"
        "💰 R$ 49,90/mês\n"
        "🔹 Até 3 streamers monitorados\n"
        "🎯 Ideal para clippers e agências\n"
        "➕ Até 3 slots adicionais (R$9,90 cada)\n"
        "📅 Renovação mensal\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Confirmar assinatura", callback_data="menu_5_plus")],
        [InlineKeyboardButton("🔙 Voltar para planos", callback_data="menu_3")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


async def responder_menu_4_anual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "📦 *RESUMO DO PLANO ANUAL PRO*\n\n"
        "💰 R$ 299,00/ano\n"
        "🔹 Até 3 streamers monitorados\n"
        "🎁 1 slot extra incluso\n"
        "➕ Até 5 slots adicionais (R$7,90 cada)\n"
        "📅 Economia de 2 meses\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Confirmar assinatura", callback_data="menu_5_anual")],
        [InlineKeyboardButton("🔙 Voltar para planos", callback_data="menu_3")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_5 → Pagamento (temporário)
async def responder_menu_5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "💰 *PAGAMENTO EM CONSTRUÇÃO*\n\n"
        "Em breve você poderá concluir o pagamento aqui mesmo pelo bot.\n"
        "Enquanto isso, estamos finalizando os últimos ajustes 😉"
    )

    botoes = [
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
