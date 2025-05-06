import os
import sqlite3
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from core.ambiente import MERCADO_PAGO_ACCESS_TOKEN
from core.database import buscar_configuracao_canal, conectar
from chat_privado.usuarios import get_nivel_usuario

logger = logging.getLogger(__name__)

ESPERANDO_CREDENCIAIS, ESPERANDO_STREAMERS, ESCOLHENDO_MODO = range(3)

def verificar_status_pagamento(pagamento_id: int) -> str:
    url = f"https://api.mercadopago.com/v1/payments/{pagamento_id}"
    headers = {"Authorization": f"Bearer {MERCADO_PAGO_ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        return response.json().get("status", "erro")
    except Exception as e:
        logger.error(f"Erro ao verificar pagamento: {e}")
        return "erro"

async def verificar_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.delete_message()
    except:
        pass
    query = update.callback_query
    await query.answer()
    pagamento_id = context.user_data.get("id_pagamento")

    if not pagamento_id:
        await query.edit_message_text("❌ Não foi possível validar o pagamento. Tente novamente.")
        return

    status = verificar_status_pagamento(pagamento_id)
    if status == "approved":
        await iniciar_configuracao_pos_pagamento(update, context)
    elif status == "pending":
        await query.edit_message_text(
            "⏳ Pagamento ainda *pendente*. Clique novamente no botão abaixo após aprovação.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Já paguei", callback_data="verificar_pagamento")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]
            ]),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ Pagamento *não aprovado* ou expirado. Tente novamente.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_3")]
            ]),
            parse_mode="Markdown"
        )

async def menu_configurar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.delete_message()
    except:
        pass
    query = update.callback_query
    await query.answer()

    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    configuracao = buscar_configuracao_canal(query.from_user.id)
    if configuracao and configuracao.get("twitch_client_id") and configuracao.get("streamers"):
        await query.edit_message_text(
            "⚙️ Seu canal já está configurado.\n\nO que deseja fazer?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁 Ver canal", callback_data="ver_canal")],
                [InlineKeyboardButton("🔧 Alterar configuração", callback_data="enviar_twitch")],
                [InlineKeyboardButton("ℹ️ Ver plano", callback_data="ver_plano")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]
            ])
        )
        return

    texto = (
        "🎉 *Pagamento confirmado!*\n\n"
        "Agora vamos configurar seu canal personalizado do Clipador.\n\n"
        "👣 *Passo 1* — Crie um aplicativo na Twitch:\n"
        "https://dev.twitch.tv/console/apps\n\n"
        "Use:\n- Name: Clipador\n- Redirect URL: `https://clipador.com.br/redirect`\n- Category: Chat Bot\n\n"
        "Depois envie aqui:\n`ID: abc123`\n`SECRET: def456`\n\nClique abaixo 👇"
    )
    botoes = [
        [InlineKeyboardButton("📨 Enviar dados da Twitch", callback_data="enviar_twitch")],
        [InlineKeyboardButton("🔙 Voltar ao início", callback_data="menu_0")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    except Exception:
        nova_msg = await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
        context.user_data.setdefault("mensagens_para_apagar", []).append(nova_msg.message_id)

async def iniciar_configuracao_pos_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await menu_configurar_canal(update, context)

async def iniciar_envio_twitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📨 Envie suas credenciais no formato:\n\n`ID: sua_client_id`\n`SECRET: seu_client_secret`",
        parse_mode="Markdown"
    )
    return ESPERANDO_CREDENCIAIS

async def receber_credenciais(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    twitch_id, twitch_secret = "", ""
    for linha in texto.splitlines():
        if linha.lower().startswith("id:"):
            twitch_id = linha.split(":", 1)[1].strip()
        elif linha.lower().startswith("secret:"):
            twitch_secret = linha.split(":", 1)[1].strip()

    if not twitch_id or not twitch_secret or len(twitch_id) < 10 or len(twitch_secret) < 10:
        msg = await update.message.reply_text(
            "❌ Formato inválido. Envie no formato:\n\n`ID: sua_client_id`\n`SECRET: seu_client_secret`",
            parse_mode="Markdown"
        )
        context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
        return ESPERANDO_CREDENCIAIS

    context.user_data["twitch_id"] = twitch_id
    context.user_data["twitch_secret"] = twitch_secret

    telegram_id = update.message.from_user.id
    nome = update.message.from_user.full_name
    nivel = get_nivel_usuario(telegram_id, nome)
    limite_streamers = 1 if nivel == 2 else 3 if nivel == 3 else 5
    context.user_data.update({
        "limite_streamers": limite_streamers,
        "streamers": []
    })

    msg = await update.message.reply_text(
        f"✅ Credenciais recebidas!\n\nAgora envie o nome do streamer que deseja monitorar.\n(Até {limite_streamers} no total)"
    )
    context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
    return ESPERANDO_STREAMERS

async def receber_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    streamers = context.user_data.get("streamers", [])
    limite = context.user_data.get("limite_streamers")

    if nome.isdigit():
        indice = int(nome) - 1
        if 0 <= indice < len(streamers):
            removido = streamers.pop(indice)
            msg = await update.message.reply_text(f"❌ Removido: {removido}")
            context.user_data["streamers"] = streamers
            context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
            return ESPERANDO_STREAMERS

    if len(streamers) >= limite:
        msg = await update.message.reply_text("❌ Você já atingiu o limite de streamers.")
        context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
        return await escolher_modo_monitoramento(update, context)

    streamers.append(nome)
    context.user_data["streamers"] = streamers

    if len(streamers) < limite:
        lista = "\n".join([f"{i+1}. {s}" for i, s in enumerate(streamers)])
        restante = limite - len(streamers)
        msg = await update.message.reply_text(
            f"✅ Adicionado: {nome}\n\nStreamers atuais:\n{lista}\n\n"
            f"Você pode enviar mais {restante}, digite /continuar ou envie o número para remover."
        )
        context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
        return ESPERANDO_STREAMERS
    else:
        return await escolher_modo_monitoramento(update, context)

async def comando_continuar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await escolher_modo_monitoramento(update, context)

async def escolher_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send = query.edit_message_text
    else:
        send = update.message.reply_text

    texto = (
        "🧠 *Modos de Monitoramento do Clipador:*\n\n"
        "🤖 *Automático:* O Clipador escolhe o melhor modo.\n"
        "🚀 *Modo Louco:* Muitos clipes rapidamente.\n"
        "🎯 *Modo Padrão:* Equilíbrio entre qualidade e quantidade.\n"
        "🔬 *Modo Cirúrgico:* Apenas clipes virais.\n"
        "🛠 *Manual:* (em breve)\n\n"
        "📌 Você poderá alterar o modo depois."
    )
    botoes = [
        [InlineKeyboardButton("✅ Selecionar modo", callback_data="escolher_modo")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_streamers")]
    ]
    await send(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return ESCOLHENDO_MODO

async def voltar_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    streamers = context.user_data.get("streamers", [])
    limite = context.user_data.get("limite_streamers", 1)
    restante = limite - len(streamers)
    lista = "\n".join([f"{i+1}. {s}" for i, s in enumerate(streamers)])
    texto = f"📺 *Streamers atuais:*\n{lista}\n\nVocê pode enviar mais {restante} ou digitar /continuar para avançar."
    await query.edit_message_text(text=texto, parse_mode="Markdown")
    return ESPERANDO_STREAMERS

async def mostrar_botoes_modos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "🧠 *Modos de Monitoramento do Clipador:*\n\n"
        "🤖 *Automático:* O Clipador escolhe o melhor modo.\n"
        "🚀 *Modo Louco:* Muitos clipes rapidamente.\n"
        "🎯 *Modo Padrão:* Equilíbrio entre qualidade e quantidade.\n"
        "🔬 *Modo Cirúrgico:* Apenas clipes virais.\n"
        "🛠 *Manual:* (em breve)\n\n"
        "📌 Você poderá alterar o modo depois."
    )
    botoes = [
        [InlineKeyboardButton("🤖 Automático", callback_data="modo_AUTOMATICO")],
        [InlineKeyboardButton("🚀 Modo Louco", callback_data="modo_MODO_LOUCO")],
        [InlineKeyboardButton("🎯 Modo Padrão", callback_data="modo_MODO_PADRAO")],
        [InlineKeyboardButton("🔬 Modo Cirúrgico", callback_data="modo_MODO_CIRURGICO")],
        [InlineKeyboardButton("🛠 Manual", callback_data="modo_MANUAL")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_streamers")]
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return ESCOLHENDO_MODO

async def salvar_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data.replace("modo_", "")
    context.user_data["modo_monitoramento"] = modo

    telegram_id = query.from_user.id
    twitch_client_id = context.user_data.get("twitch_id")
    twitch_client_secret = context.user_data.get("twitch_secret")
    streamers = context.user_data.get("streamers", [])

    texto = (
        f"📋 *Revisão final dos dados:*\n\n"
        f"👤 Usuário: @{query.from_user.username or query.from_user.first_name}\n"
        f"🧪 Client ID: `{twitch_client_id}`\n"
        f"🔐 Client Secret: `{twitch_client_secret[:6]}...`\n"
        f"📺 Streamers: `{', '.join(streamers)}`\n"
        f"🧠 Modo: `{modo}`\n\n"
        f"⚠️ Após salvar, você terá até 1 hora para alterar os streamers.\nDepois disso, eles serão fixos."
    )
    botoes = [
        [InlineKeyboardButton("✅ Confirmar e salvar", callback_data="confirmar_salvar_canal")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_streamers")]
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return ESCOLHENDO_MODO

async def confirmar_salvar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    username = query.from_user.username or f"user{telegram_id}"

    twitch_client_id = context.user_data.get("twitch_id")
    twitch_client_secret = context.user_data.get("twitch_secret")
    streamers = context.user_data.get("streamers", [])
    modo = context.user_data.get("modo_monitoramento")

    # Apagar mensagens antigas
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=telegram_id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    salvar_configuracao_canal(telegram_id, twitch_client_id, twitch_client_secret, streamers, modo)
    atualizar_telegram_id_usuario(telegram_id)

    await query.edit_message_text(
        f"✅ Tudo pronto!\n\n"
        f"📢 Seu canal *Clipador 🎥 @{username}* foi criado com sucesso!\n\n"
        "Você começará a receber clipes automaticamente com base nas suas configurações 🚀",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Abrir canal", url=f"https://t.me/clipador_{username}")]
        ]),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# Banco local para salvar configurações
def salvar_configuracao_canal(telegram_id, twitch_client_id, twitch_client_secret, streamers, modo):
    caminho = os.path.join("banco", "database_canais.db")
    conn = sqlite3.connect(caminho)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canais (
            telegram_id INTEGER PRIMARY KEY,
            twitch_client_id TEXT,
            twitch_client_secret TEXT,
            streamers TEXT,
            modo TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO canais (telegram_id, twitch_client_id, twitch_client_secret, streamers, modo)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            twitch_client_id=excluded.twitch_client_id,
            twitch_client_secret=excluded.twitch_client_secret,
            streamers=CASE
                WHEN (strftime('%s','now') - strftime('%s',data_criacao)) < 3600 THEN excluded.streamers
                ELSE canais.streamers
            END,
            modo=excluded.modo
    """, (
        telegram_id,
        twitch_client_id,
        twitch_client_secret,
        ",".join(streamers),
        modo
    ))
    conn.commit()
    conn.close()

def atualizar_telegram_id_usuario(telegram_id):
    from core.database import conectar
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET telegram_id = ? WHERE id = ?", (telegram_id, telegram_id))
    conn.commit()
    conn.close()

# ConversationHandler do processo
def configurar_canal_conversa():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(iniciar_envio_twitch, pattern="^enviar_twitch$"),
            CallbackQueryHandler(menu_configurar_canal, pattern="^menu_configurar_canal$"),
            CallbackQueryHandler(responder_menu_7_configurar, pattern="^continuar_configuracao$")
        ],
        states={
            ESPERANDO_CREDENCIAIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_credenciais)],
            ESPERANDO_STREAMERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_streamer),
                CommandHandler("continuar", comando_continuar)
            ],
            ESCOLHENDO_MODO: [
                CallbackQueryHandler(mostrar_botoes_modos, pattern="^escolher_modo$"),
                CallbackQueryHandler(salvar_modo_monitoramento, pattern="^modo_"),
                CallbackQueryHandler(voltar_streamers, pattern="^voltar_streamers$"),
                CallbackQueryHandler(confirmar_salvar_canal, pattern="^confirmar_salvar_canal$")
            ]
        },
        fallbacks=[],
        allow_reentry=True
    )

# Webhook para envio automático
async def iniciar_configuracao_via_webhook(application, telegram_id):
    try:
        texto = (
            "🎉 *Pagamento confirmado!*\n\n"
            "Agora vamos configurar seu canal personalizado do Clipador.\n\n"
            "👣 *Passo 1:* Crie um app na Twitch:\n"
            "https://dev.twitch.tv/console/apps\n"
            "- Name: Clipador\n"
            "- Redirect: https://clipador.com.br/redirect\n"
            "- Category: Chat Bot\n\n"
            "Depois envie aqui:\n"
            "`ID: xxx`\n`SECRET: yyy`\n\n"
            "👇 Quando estiver pronto:"
        )
        botoes = [
            [InlineKeyboardButton("📨 Enviar dados da Twitch", callback_data="enviar_twitch")],
            [InlineKeyboardButton("🔙 Voltar ao início", callback_data="menu_0")]
        ]
        await application.bot.send_message(chat_id=telegram_id, text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"Erro webhook: {e}")
        return False

# Redirecionador manual para o menu
async def verificar_callback_configurar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await menu_configurar_canal(update, context)

# Resposta ao botão "continuar_configuracao"
async def responder_menu_7_configurar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("🚀 Continuando configuração do canal...")
    await menu_configurar_canal(update, context)