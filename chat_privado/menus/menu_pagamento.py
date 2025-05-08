async def avancar_para_nova_etapa(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str, botoes: list):
    mensagens = context.user_data.get("mensagens_para_apagar", [])
    for msg_id in mensagens:
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except Exception:
            pass
    context.user_data["mensagens_para_apagar"] = []

    nova_msg = await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    context.user_data.setdefault("mensagens_para_apagar", []).append(nova_msg.message_id)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from core.database import (
    salvar_email_usuario,
    email_ja_utilizado_por_outro_usuario,
    ativar_usuario_por_telegram_id,
    salvar_plano_usuario,
    is_usuario_admin,
    buscar_pagamento_por_email,
    registrar_log_pagamento,
    vincular_email_usuario,
    atualizar_status_compra_telegram
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
        # Salva o ID da mensagem de botões para poder editar depois
        context.user_data["mensagem_pagamento_id"] = query.message.message_id
        await query.message.reply_text(
            text="😎 Beleza! Agora me diga qual e-mail você usou para fazer o pagamento:",
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
    vincular_email_usuario(update.effective_user.id, email)

    # Apaga a mensagem anterior com os botões, se possível
    plano_esperado = context.user_data.get("plano_esperado", "Mensal Solo")
    try:
        await update.message.delete()
    except Exception as e:
        print(f"[DEBUG] Não foi possível apagar a mensagem anterior: {e}")

    if not email or "@" not in email or "." not in email:
        await update.message.reply_text(
            f"📧 E-mail informado: {email}\n\n"
            "❌ E-mail inválido ou não informado. Por favor, digite um e-mail válido para continuar.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return MENU_6

    await update.message.chat.send_action(action="typing")

    telegram_id = update.effective_user.id
    print(f"[DEBUG] Iniciando verificação de pagamento do e-mail: {email}")

    if email_ja_utilizado_por_outro_usuario(email, telegram_id):
        await update.message.reply_text(
            "❌ Este e-mail já está vinculado a outro usuário.\nVerifique se digitou corretamente ou use outro e-mail.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return MENU_6

    try:
        status, plano_real = verificar_pagamento_email_e_registrar(email, telegram_id)
        from core.database import atualizar_status_compra_telegram
        atualizar_status_compra_telegram(email, telegram_id, status)
        registrar_log_pagamento(telegram_id, email, plano_real, status)
    except Exception as e:
        status = "erro_interno"
        plano_real = None
        print(f"[ERRO] Exceção ao verificar pagamento: {str(e)}")
        registrar_log_pagamento(telegram_id, email, None, status)
        await update.message.reply_text(
            "❌ Ocorreu um erro inesperado durante a verificação do pagamento.\nTente novamente mais tarde.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return MENU_6

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
        if not vincular_email_usuario(telegram_id, email):
            await update.message.reply_text(
                "❌ Este e-mail já está vinculado a outro usuário.\nVerifique se digitou corretamente ou use outro e-mail.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                    [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
                ])
            )
            return MENU_6
        salvar_plano_usuario(telegram_id, plano_real)
        ativar_usuario_por_telegram_id(telegram_id)
        await avancar_para_nova_etapa(
            update,
            context,
            f"✅ Pagamento confirmado com sucesso!\n\n"
            f"Plano assinado: *{plano_real}*.\n"
            f"Seu acesso foi liberado. Agora vamos configurar seu canal privado.",
            [[InlineKeyboardButton("⚙️ Continuar configuração", callback_data="abrir_configurar_canal")]]
        )
        return ConversationHandler.END
    elif status == "free":
        pagamento = buscar_pagamento_por_email(email)
        if not pagamento:
            print("[DEBUG] Nenhuma compra detectada com este e-mail.")
            await update.message.reply_text(
                f"❌ Nenhuma compra detectada com o e-mail: {email}\n"
                "Verifique se digitou corretamente ou realize o pagamento antes de continuar.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                    [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
                ])
            )
            return MENU_6

        print("[DEBUG] Produto gratuito detectado.")
        if not is_usuario_admin(telegram_id):
            print("[DEBUG] Usuário NÃO é admin, bloqueando produto gratuito.")
            await update.message.reply_text(
                "❌ Produtos gratuitos só podem ser usados por administradores.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
                ])
            )
            return MENU_6

        print("[DEBUG] Usuário é admin e e-mail é válido, ativando acesso gratuito.")
        if not vincular_email_usuario(telegram_id, email):
            await update.message.reply_text(
                "❌ Este e-mail já está vinculado a outro usuário.\nVerifique se digitou corretamente ou use outro e-mail.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                    [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
                ])
            )
            return MENU_6
        salvar_plano_usuario(telegram_id, plano_real)
        ativar_usuario_por_telegram_id(telegram_id)
        # Apagar mensagens anteriores
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except:
            pass
        # Apagar mensagens antigas de confirmação, se houver
        mensagens = context.user_data.get("mensagens_para_apagar", [])
        for msg_id in mensagens:
            try:
                await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
            except Exception:
                pass
        context.user_data["mensagens_para_apagar"] = []

        nova_msg = await update.message.reply_text(
            f"🔓 Produto gratuito ativado para admin.\nPlano: *{plano_esperado}*.",
            parse_mode="Markdown"
        )
        context.user_data.setdefault("mensagens_para_apagar", []).append(nova_msg.message_id)
        botoes = [
            [InlineKeyboardButton("⚙️ Continuar configuração", callback_data="abrir_configurar_canal")]
        ]
        await update.message.reply_text(
            "Clique no botão abaixo para configurar seu canal personalizado:",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
        return ConversationHandler.END
    elif status == "pending":
        print("[DEBUG] Pagamento pendente.")
        # Determina a mensagem a ser editada
        mensagem_id = None
        chat_id = update.effective_chat.id
        # Tenta pegar a mensagem de botões anterior via reply_to_message, senão pega do user_data
        if update.message.reply_to_message:
            mensagem_id = update.message.reply_to_message.message_id
        else:
            mensagem_id = context.user_data.get("mensagem_pagamento_id")
        plano_esperado = context.user_data.get("plano_esperado", "Mensal Solo")
        # Monta os botões
        botoes = [
            [InlineKeyboardButton("📎 Acessar link de pagamento", url=LINKS_KIRVANO.get(plano_esperado, ""))],
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
        ]
        texto_pendente = (
            f"📧 E-mail informado: {email}\n\n"
            "🕐 Pagamento ainda pendente.\n"
            "Aguarde a confirmação e clique novamente em 'Já paguei'."
        )
        if mensagem_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=mensagem_id,
                    text=texto_pendente,
                    reply_markup=InlineKeyboardMarkup(botoes)
                )
            except Exception as e:
                print(f"[DEBUG] Falha ao editar mensagem pendente: {e}")
                await update.message.reply_text(
                    texto_pendente,
                    reply_markup=InlineKeyboardMarkup(botoes)
                )
        else:
            await update.message.reply_text(
                texto_pendente,
                reply_markup=InlineKeyboardMarkup(botoes)
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
    elif status == "pendente":
        pagamento = buscar_pagamento_por_email(email)
        if not pagamento:
            print("[DEBUG] Nenhuma compra detectada com este e-mail (pendente).")
            await update.message.reply_text(
                "❌ Nenhuma compra detectada com este e-mail.\n"
                "Verifique se digitou corretamente ou realize o pagamento antes de continuar.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                    [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
                ])
            )
            return MENU_6

        print("[DEBUG] Produto gratuito detectado, mas status pendente. Checando se é admin...")
        if is_usuario_admin(telegram_id):
            print("[DEBUG] Admin liberado mesmo com status pendente.")
            salvar_plano_usuario(telegram_id, plano_real or plano_esperado)
            ativar_usuario_por_telegram_id(telegram_id)
            # Apagar mensagens anteriores
            try:
                await update.message.reply_to_message.delete()
                await update.message.delete()
            except:
                pass
            # Apagar mensagens antigas de confirmação, se houver
            mensagens = context.user_data.get("mensagens_para_apagar", [])
            for msg_id in mensagens:
                try:
                    await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
                except Exception:
                    pass
            context.user_data["mensagens_para_apagar"] = []

            nova_msg = await update.message.reply_text(
                f"🔓 Produto gratuito ativado para admin.\nPlano: *{plano_esperado}*.",
                parse_mode="Markdown"
            )
            context.user_data.setdefault("mensagens_para_apagar", []).append(nova_msg.message_id)
            botoes = [
                [InlineKeyboardButton("⚙️ Continuar configuração", callback_data="abrir_configurar_canal")]
            ]
            await update.message.reply_text(
                "Clique no botão abaixo para configurar seu canal personalizado:",
                reply_markup=InlineKeyboardMarkup(botoes)
            )
            return ConversationHandler.END
        else:
            texto_pendente = (
                f"📧 E-mail informado: {email}\n\n"
                "🕐 Pagamento ainda pendente.\n"
                "Aguarde a confirmação e clique novamente em 'Já paguei'."
            )
            await update.message.reply_text(
                texto_pendente,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Já paguei", callback_data="menu_6")],
                    [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
                ])
            )
            return MENU_6
    # Fallback para status inesperado
    if status not in ["approved", "free", "pending", "not_found", "pendente"]:
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
# HANDLER PARA MENU DE CONFIGURAÇÃO DO CANAL
from chat_privado.menus.menu_configurar_canal import menu_configurar_canal

pagamento_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(responder_menu_6, pattern="^menu_6$")],
    states={
        MENU_6: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_email)],
    },
    fallbacks=[],
    per_message=False
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

    elif data == "abrir_configurar_canal":
        from chat_privado.menus.menu_configurar_canal import menu_configurar_canal
        print("[DEBUG] Callback abrir_configurar_canal acionado.")
        await update.callback_query.answer()
        await menu_configurar_canal(update, context)