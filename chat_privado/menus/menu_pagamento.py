from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from core.pagamento import criar_pagamento_pix, criar_pagamento_cartao

def obter_valor_plano(plano: str) -> float:
    return {
        "Mensal Solo": 29.90,
        "Mensal Plus": 49.90,
        "Anual Pro": 299.00
    }.get(plano, 0.0)

async def gerar_pagamento_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    try:
        dados = await criar_pagamento_pix(
            valor=obter_valor_plano(plano_nome),
            descricao=f"Assinatura Clipador - {plano_nome}"
        )

        texto = (
            f"💸 *Pagamento via Pix gerado com sucesso!*\n\n"
            f"📦 Plano: *{plano_nome}*\n"
            f"💰 Valor: *R${dados['valor']:.2f}*\n\n"
            "Copie o código abaixo ou escaneie o QR Code:"
        )

        botoes = [
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_0")],
            [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
        ]

        await query.message.reply_photo(
            photo=f"data:image/png;base64,{dados['imagem']}",
            caption=texto + f"\n\n`{dados['qrcode']}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botoes)
        )

    except Exception as e:
        await query.edit_message_text(
            text=f"❌ Erro ao gerar o pagamento via Pix.\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
            ])
        )

async def gerar_pagamento_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    try:
        link = await criar_pagamento_cartao(
            valor=obter_valor_plano(plano_nome),
            descricao=f"Assinatura Clipador - {plano_nome}"
        )

        texto = (
            f"💳 *Pagamento via Cartão de Crédito*\n\n"
            f"📦 Plano: *{plano_nome}*\n"
            f"💰 Valor: *R${obter_valor_plano(plano_nome):.2f}*\n\n"
            "Clique abaixo para finalizar a compra:"
        )

        botoes = [
            [InlineKeyboardButton("💳 Pagar com Cartão", url=link)],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
        ]

        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

    except Exception as e:
        await query.edit_message_text(
            text=f"❌ Erro ao gerar pagamento com cartão.\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_cartao_{plano_nome.replace(' ', '_')}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
            ])
        )

async def exibir_opcoes_pagamento(update: Update, plano_nome: str):
    query = update.callback_query
    await query.answer()

    texto = (
        f"📝 *Plano selecionado: {plano_nome}*\n"
        f"💰 Valor: R${obter_valor_plano(plano_nome):.2f}\n\n"
        f"Escolha a forma de pagamento:"
    )

    botoes = [
        [InlineKeyboardButton("💸 Pagar com Pix", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
        [InlineKeyboardButton("💳 Pagar com Cartão", callback_data=f"pagar_cartao_{plano_nome.replace(' ', '_')}")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
    ]

    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

# Roteadores
async def responder_menu_5_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await exibir_opcoes_pagamento(update, "Mensal Solo")

async def responder_menu_5_plus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await exibir_opcoes_pagamento(update, "Mensal Plus")

async def responder_menu_5_anual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await exibir_opcoes_pagamento(update, "Anual Pro")

async def roteador_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("pagar_pix_"):
        plano = data.replace("pagar_pix_", "").replace("_", " ")
        await gerar_pagamento_pix(update, context, plano)

    elif data.startswith("pagar_cartao_"):
        plano = data.replace("pagar_cartao_", "").replace("_", " ")
        await gerar_pagamento_cartao(update, context, plano)
