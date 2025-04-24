from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.checkout import consultar_pagamento
from chat_privado.menus.menu_configurar_canal import menu_configurar_canal

from telegram.error import BadRequest


# menu_0 → Menu inicial
async def responder_menu_0(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "👋 *Seja bem-vindo ao Clipador!*\n\n"
        "O Clipador é um bot que monitora streamers e envia os melhores momentos automaticamente.\n\n"
        "Escolha uma opção para continuar:"
    )

    botoes = [
        [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
        [InlineKeyboardButton("💰 Planos", callback_data="menu_3")],
        [InlineKeyboardButton("🚀 Assinar", callback_data="menu_3")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


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

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

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


# menu_3 → Lista de Planos
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

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_4 → Resumo plano Mensal Solo
async def responder_menu_4_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "*📝 RESUMO DO PLANO MENSAL SOLO*\n\n"
        "💰 R$ 29,90/mês\n"
        "🔹 1 streamer monitorado\n"
        "🔄 Troca de streamer 1x por mês\n"
        "➕ Máximo 1 slot adicional (R$14,90 fixo)\n"
        "📅 Renovação mensal\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Escolher este plano", callback_data="menu_5_mensal")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_4 → Resumo plano Mensal Plus
async def responder_menu_4_plus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "*📝 RESUMO DO PLANO MENSAL PLUS*\n\n"
        "💰 R$ 49,90/mês\n"
        "🔹 Até 3 streamers monitorados\n"
        "📦 Ideal para agências/clippers\n"
        "➕ Até 3 slots adicionais (R$9,90 cada)\n"
        "📅 Renovação mensal\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Escolher este plano", callback_data="menu_5_plus")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_4 → Resumo plano Anual Pro
async def responder_menu_4_anual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "*📝 RESUMO DO PLANO ANUAL PRO*\n\n"
        "💰 R$ 299,00/ano\n"
        "🔹 3 streamers monitorados + 1 slot bônus\n"
        "🎁 Economia de 2 meses\n"
        "➕ Até 5 slots adicionais (R$7,90 cada)\n"
        "📅 Renovação anual\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Escolher este plano", callback_data="menu_5_anual")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")


# menu_6 → Confirmação de pagamento
from core.checkout import consultar_pagamento
from chat_privado.menus.menu_configurar_canal import menu_configurar_canal


async def responder_menu_6_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pagamento_id = context.user_data.get("id_pagamento")

    if not pagamento_id:
        await query.edit_message_text(
            "❌ Nenhum pagamento encontrado.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Voltar ao início", callback_data="menu_0")]
            ]),
            parse_mode="Markdown"
        )
        return

    status = consultar_pagamento(pagamento_id)

    if status == "approved":
        await query.edit_message_text("✅ Pagamento confirmado! Vamos configurar seu canal...")
        await menu_configurar_canal(update, context)

    elif status == "pending":
        await query.edit_message_text(
            "⏳ O pagamento ainda não foi identificado.\n"
            "Isso pode levar alguns minutos, tente novamente em instantes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Verificar novamente", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao início", callback_data="menu_0")]
            ]),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"❌ Ocorreu um erro ao consultar o pagamento (status: {status})",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_0")]
            ]),
            parse_mode="Markdown"
        )