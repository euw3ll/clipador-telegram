from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from core.database import (
    salvar_email_usuario,
    email_ja_utilizado_por_outro_usuario,
    ativar_usuario_por_telegram_id,
    salvar_plano_usuario,
    is_usuario_admin,
    buscar_pagamento_por_email,
    registrar_log_pagamento
)
from io import BytesIO
from core.pagamento import criar_pagamento_pix, criar_pagamento_cartao
from configuracoes import GATEWAY_PAGAMENTO
import base64

PEDIR_EMAIL = 1

def obter_valor_plano(plano: str) -> float:
    return {
        "Mensal Solo": 29.90,
        "Mensal Plus": 49.90,
        "Anual Pro": 299.00
    }.get(plano, 0.0)

LINKS_KIRVANO = {
    "Mensal Solo": "https://pay.kirvano.com/3f315c85-0164-4b55-81f2-6ffa661b670c",
    "Mensal Plus": "https://pay.kirvano.com/6283e70f-f385-4355-8cff-e02275935cde",
    "Anual Pro": "https://pay.kirvano.com/09287018-c006-4c0e-87c7-08a6e4464e79"
}

# MENU 5: Mostrar opções de pagamento por plano
async def responder_menu_5_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plano_esperado"] = "Mensal Solo"
    await exibir_opcoes_pagamento(update, context, "Mensal Solo")

async def responder_menu_5_plus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plano_esperado"] = "Mensal Plus"
    await exibir_opcoes_pagamento(update, context, "Mensal Plus")

async def responder_menu_5_anual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plano_esperado"] = "Anual Pro"
    await exibir_opcoes_pagamento(update, context, "Anual Pro")

# Exibe botões com base no gateway
async def exibir_opcoes_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    valor = obter_valor_plano(plano_nome)

    texto = (
        f"📦 *Plano selecionado: {plano_nome}*\n"
        f"💰 Valor: R${valor:.2f}\n\n"
    )

    if GATEWAY_PAGAMENTO == "KIRVANO":
        texto += "Clique abaixo para acessar o link de pagamento:"
        botoes = [
            [InlineKeyboardButton("📎 Acessar link de pagamento", url=LINKS_KIRVANO[plano_nome])],
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
        ]
    elif GATEWAY_PAGAMENTO == "MERCADOPAGO":
        texto += "Escolha a forma de pagamento:"
        botoes = [
            [InlineKeyboardButton("💸 Pagar com Pix", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
            [InlineKeyboardButton("💳 Pagar com Cartão", callback_data=f"pagar_cartao_{plano_nome.replace(' ', '_')}")],
            [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
        ]
    else:
        texto += "❌ Gateway de pagamento inválido."
        botoes = [[InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]]

    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )

# GERAÇÃO DE PIX (somente Mercado Pago)
async def gerar_pagamento_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    try:
        dados = criar_pagamento_pix(
            valor=obter_valor_plano(plano_nome),
            descricao=f"Assinatura Clipador - {plano_nome}"
        )

        imagem_bytes = base64.b64decode(dados["imagem"])
        imagem_io = BytesIO(imagem_bytes)
        imagem_io.name = "qrcode.png"

        texto = (
            f"💸 *Pagamento via Pix gerado com sucesso!*\n\n"
            f"📦 Plano: *{plano_nome}*\n"
            f"💰 Valor: *R${dados['valor']:.2f}*\n\n"
            "Copie o código abaixo ou escaneie o QR Code:"
        )

        botoes = [
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
        ]

        await query.message.reply_photo(
            photo=imagem_io,
            caption=texto + f"\n\n`{dados['qrcode']}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botoes)
        )

    except Exception as e:
        await query.message.reply_text(
            text=f"❌ Erro ao gerar o pagamento via Pix.\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
            ]),
            parse_mode="Markdown"
        )

# GERAÇÃO DE CARTÃO (somente Mercado Pago)
async def gerar_pagamento_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    try:
        link_checkout = criar_pagamento_cartao(
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
            [InlineKeyboardButton("💳 Pagar com Cartão", url=link_checkout)],
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
        ]

        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

    except Exception as e:
        await query.edit_message_text(
            text="❌ Erro ao gerar pagamento com cartão. Deseja tentar novamente?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_cartao_{plano_nome.replace(' ', '_')}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
            ])
        )

# MENU 6: Já paguei (pede e-mail)
async def responder_menu_6(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text(
            "😎 Beleza! Agora me diga qual e-mail você usou para fazer o pagamento:",
            reply_markup=ForceReply(selective=True)
        )
    else:
        await update.message.reply_text(
            "😎 Beleza! Agora me diga qual e-mail você usou para fazer o pagamento:",
            reply_markup=ForceReply(selective=True)
        )
    return MENU_6

async def receber_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.gateway.kirvano import verificar_pagamento_email_e_registrar

    email = update.message.text.strip()

    if not email or "@" not in email or "." not in email:
        await update.message.reply_text(
            "❌ E-mail inválido ou não informado. Por favor, digite um e-mail válido para continuar.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return MENU_6

    await update.message.chat.send_action(action="typing")

    telegram_id = update.effective_user.id
    plano_esperado = context.user_data.get("plano_esperado", "Mensal Solo")

    if email_ja_utilizado_por_outro_usuario(email, telegram_id):
        await update.message.reply_text(
            "❌ Este e-mail já está vinculado a outro usuário.\nVerifique se digitou corretamente ou use outro e-mail.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return MENU_6

    status, plano_real = verificar_pagamento_email_e_registrar(email, telegram_id)

    registrar_log_pagamento(telegram_id, email, plano_real, status)

    # Verifica se o plano adquirido é diferente do selecionado
    if status == "approved" and plano_real != plano_esperado:
        await update.message.reply_text(
            "❌ O plano selecionado não corresponde ao plano que você comprou.\n"
            f"Você comprou o plano *{plano_real}*, mas selecionou o *{plano_esperado}*.\n"
            "Volte e selecione o plano correto.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
            ])
        )
        return MENU_6

    if status == "approved":
        print("[DEBUG] Pagamento aprovado, ativando usuário...")
        salvar_email_usuario(telegram_id, email)
        salvar_plano_usuario(telegram_id, plano_real)
        ativar_usuario_por_telegram_id(telegram_id)
        await update.message.reply_text(
            f"✅ Pagamento confirmado com sucesso!\n\n"
            f"Plano assinado: *{plano_real}*.\n"
            f"Seu acesso foi liberado. Agora vamos configurar seu canal privado.",
            parse_mode="Markdown"
        )
        botoes = [
            [InlineKeyboardButton("⚙️ Continuar configuração", callback_data="menu_configurar_canal")]
        ]
        await update.message.reply_text(
            "Clique no botão abaixo para configurar seu canal personalizado:",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
        return ConversationHandler.END
    elif status == "free":
        print("[DEBUG] Produto gratuito detectado.")

        if "@" not in email or "." not in email:
            await update.message.reply_text(
                "❌ E-mail inválido. Por favor, digite um e-mail real para continuar.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                    [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
                ])
            )
            return MENU_6

        pagamento = buscar_pagamento_por_email(email)
        if not pagamento:
            print("[DEBUG] E-mail não está associado a nenhuma compra real.")
            await update.message.reply_text(
                "❌ Este e-mail não está vinculado a nenhuma compra.\nVerifique se digitou corretamente.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                    [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
                ])
            )
            return MENU_6

        if is_usuario_admin(telegram_id):
            print("[DEBUG] Usuário é admin e e-mail é válido, ativando acesso gratuito.")
            salvar_email_usuario(telegram_id, email)
            salvar_plano_usuario(telegram_id, plano_real)
            ativar_usuario_por_telegram_id(telegram_id)
            await update.message.reply_text(
                f"🔓 Produto gratuito reconhecido e ativado para admin.\nPlano: *{plano_real}*.",
                parse_mode="Markdown"
            )
            botoes = [
                [InlineKeyboardButton("⚙️ Continuar configuração", callback_data="menu_configurar_canal")]
            ]
            await update.message.reply_text(
                "Clique no botão abaixo para configurar seu canal personalizado:",
                reply_markup=InlineKeyboardMarkup(botoes)
            )
            return ConversationHandler.END
        else:
            print("[DEBUG] Usuário NÃO é admin, bloqueando produto gratuito.")
            await update.message.reply_text(
                "❌ Produtos gratuitos só podem ser usados por administradores.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
                ])
            )
    elif status == "pending":
        print("[DEBUG] Pagamento pendente.")
        await update.message.reply_text(
            "🕐 Pagamento ainda pendente.\nAguarde a confirmação e clique novamente em 'Já paguei'.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Já paguei", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
            ])
        )
    elif status == "not_found":
        print("[DEBUG] Pagamento não encontrado.")
        await update.message.reply_text(
            "❌ Pagamento não encontrado para este e-mail.\nVerifique se digitou corretamente.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return MENU_6
    else:
        print(f"[DEBUG] Erro inesperado na verificação de pagamento: {status}")
        await update.message.reply_text(
            "❌ Ocorreu um erro inesperado durante a verificação do pagamento.\nTente novamente ou verifique os dados informados.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
    print(f"[DEBUG] E-mail recebido: {email}")
    print(f"[DEBUG] Plano esperado: {plano_esperado}")
    print(f"[DEBUG] Resultado verificação: status={status}, plano_real={plano_real}")
    return MENU_6

MENU_6 = 6

from telegram.ext import CallbackQueryHandler

pagamento_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(responder_menu_6, pattern="^menu_6$")],
    states={
        MENU_6: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_email)],
    },
    fallbacks=[],
)

# ROTEADOR
async def roteador_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pagar_pix_"):
        plano = data.replace("pagar_pix_", "").replace("_", " ")
        await gerar_pagamento_pix(update, context, plano)

    elif data.startswith("pagar_cartao_"):
        plano = data.replace("pagar_cartao_", "").replace("_", " ")
        await gerar_pagamento_cartao(update, context, plano)