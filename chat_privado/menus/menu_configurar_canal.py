from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import requests
from io import BytesIO
import os
import sqlite3

from core.ambiente import MERCADO_PAGO_ACCESS_TOKEN
from chat_privado.usuarios import get_nivel_usuario

# Placeholder para evitar erro de importação em handlers.py
async def receber_client_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔧 Ainda estamos implementando essa etapa. Em breve você poderá ajustar as configurações do seu canal por aqui.")

# Função para verificar o status de pagamento
def verificar_status_pagamento(pagamento_id: int) -> str:
    url = f"https://api.mercadopago.com/v1/payments/{pagamento_id}"
    headers = {"Authorization": f"Bearer {MERCADO_PAGO_ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    data = response.json()
    return data.get("status", "erro")

# Callback após clicar em "✅ Já paguei"
async def verificar_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Recuperar ID do pagamento salvo no context.user_data
    pagamento_id = context.user_data.get("id_pagamento")

    if not pagamento_id:
        await query.edit_message_text("❌ Não foi possível validar o pagamento. Tente novamente.")
        return

    status = verificar_status_pagamento(pagamento_id)

    if status == "approved":
        await iniciar_configuracao_pos_pagamento(update, context)
    elif status == "pending":
        await query.edit_message_text(
            "⏳ Pagamento ainda *pendente*. Assim que for aprovado, clique novamente no botão abaixo.",
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

# Menu de configuração do canal
async def menu_configurar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "🎉 *Pagamento confirmado!*\n\n"
        "Agora vamos configurar seu canal personalizado do Clipador.\n\n"
        "👣 *Passo 1* — Crie um aplicativo na Twitch:\n"
        "Acesse: https://dev.twitch.tv/console/apps\n"
        "Clique em *Register Your Application* e preencha:\n"
        "- Name: Clipador\n"
        "- OAuth Redirect URL: `https://clipador.com.br/redirect`\n"
        "- Category: Chat Bot\n\n"
        "Depois de criar, envie aqui no bot:\n"
        "`Client ID` e `Client Secret`\n\n"
        "*Exemplo:* \n"
        "`ID: abc123`\n"
        "`SECRET: def456`\n\n"
        "Quando estiver pronto, clique abaixo 👇"
    )

    botoes = [
        [InlineKeyboardButton("📨 Enviar dados da Twitch", callback_data="enviar_twitch")],
        [InlineKeyboardButton("🔙 Voltar ao início", callback_data="menu_0")]
    ]

    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

# Callback após validar pagamento (usuários da Kirvano)
async def iniciar_configuracao_pos_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await menu_configurar_canal(update, context)


# Estados do ConversationHandler
ESPERANDO_CREDENCIAIS, ESPERANDO_STREAMERS, ESCOLHENDO_MODO = range(3)

# Início da coleta das credenciais da Twitch
async def iniciar_envio_twitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📨 Envie suas credenciais no seguinte formato:\n\n"
        "`ID: sua_client_id`\n"
        "`SECRET: seu_client_secret`",
        parse_mode="Markdown"
    )
    return ESPERANDO_CREDENCIAIS

# Receber credenciais
async def receber_credenciais(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    linhas = texto.splitlines()
    twitch_id, twitch_secret = "", ""
    for linha in linhas:
        if linha.lower().startswith("id:"):
            twitch_id = linha.split(":", 1)[1].strip()
        if linha.lower().startswith("secret:"):
            twitch_secret = linha.split(":", 1)[1].strip()

    if not twitch_id or not twitch_secret:
        await update.message.reply_text("❌ Formato inválido. Tente novamente conforme o exemplo.")
        return ESPERANDO_CREDENCIAIS

    context.user_data["twitch_id"] = twitch_id
    context.user_data["twitch_secret"] = twitch_secret

    telegram_id = update.message.from_user.id
    nome = update.message.from_user.full_name
    nivel = get_nivel_usuario(telegram_id, nome)
    limite_streamers = 1 if nivel == 2 else 3 if nivel == 3 else 5
    context.user_data["limite_streamers"] = limite_streamers
    context.user_data["streamers"] = []

    await update.message.reply_text(f"✅ Credenciais recebidas com sucesso!\n\nAgora envie o nome do streamer que deseja monitorar. Envie um por vez. (Você pode adicionar até {limite_streamers})")
    return ESPERANDO_STREAMERS

# Receber nome dos streamers
async def receber_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    streamers = context.user_data.get("streamers", [])
    limite = context.user_data.get("limite_streamers")

    if len(streamers) >= limite:
        await update.message.reply_text("❌ Você já atingiu o número máximo de streamers.")
        return await escolher_modo_monitoramento(update, context)

    streamers.append(nome)
    context.user_data["streamers"] = streamers

    if len(streamers) < limite:
        await update.message.reply_text(f"✅ Adicionado: {nome}\n\nVocê pode enviar mais {limite - len(streamers)} streamer(s), ou digite /continuar para avançar.")
        return ESPERANDO_STREAMERS
    else:
        return await escolher_modo_monitoramento(update, context)

# Comando para continuar mesmo sem atingir o limite
async def comando_continuar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await escolher_modo_monitoramento(update, context)

# Escolher modo de monitoramento
async def escolher_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botoes = [
        [InlineKeyboardButton("🤖 Automático", callback_data="modo_AUTOMATICO")],
        [InlineKeyboardButton("🚀 Modo Louco", callback_data="modo_MODO_LOUCO")],
        [InlineKeyboardButton("🎯 Modo Padrão", callback_data="modo_MODO_PADRAO")],
        [InlineKeyboardButton("🔬 Modo Cirúrgico", callback_data="modo_MODO_CIRURGICO")],
        [InlineKeyboardButton("🛠️ Manual", callback_data="modo_MANUAL")]
    ]
    await update.message.reply_text("🧠 Escolha o modo de monitoramento:", reply_markup=InlineKeyboardMarkup(botoes))
    return ESCOLHENDO_MODO

# Callback do modo
async def salvar_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data.replace("modo_", "")
    context.user_data["modo_monitoramento"] = modo

    # Salvar no banco
    salvar_configuracao_canal(
        telegram_id=query.from_user.id,
        twitch_client_id=context.user_data["twitch_id"],
        twitch_client_secret=context.user_data["twitch_secret"],
        streamers=context.user_data["streamers"],
        modo=modo
    )

    await query.edit_message_text(
        f"🎉 Tudo certo!\n\nSeu canal está configurado com sucesso com o modo *{modo}*.\nVocê começará a receber os clipes em breve!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# --- Implementação local de salvar_configuracao_canal ---
import sqlite3
import os

CAMINHO_BANCO_CANAIS = os.path.join("banco", "database_canais.db")

def salvar_configuracao_canal(telegram_id, twitch_client_id, twitch_client_secret, streamers, modo):
    conexao = sqlite3.connect(CAMINHO_BANCO_CANAIS)
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canais (
            telegram_id INTEGER PRIMARY KEY,
            twitch_client_id TEXT NOT NULL,
            twitch_client_secret TEXT NOT NULL,
            streamers TEXT NOT NULL,
            modo TEXT NOT NULL
        )
    """)

    cursor.execute("""
        INSERT OR REPLACE INTO canais (telegram_id, twitch_client_id, twitch_client_secret, streamers, modo)
        VALUES (?, ?, ?, ?, ?)
    """, (
        telegram_id,
        twitch_client_id,
        twitch_client_secret,
        ",".join(streamers),
        modo
    ))

    conexao.commit()
    conexao.close()


# ConversationHandler para configurar canal

def configurar_canal_conversa():
    from telegram.ext import CallbackQueryHandler, ConversationHandler
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_envio_twitch, pattern="^enviar_twitch$")],
        states={
            ESPERANDO_CREDENCIAIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_credenciais)],
            ESPERANDO_STREAMERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_streamer),
                CommandHandler("continuar", comando_continuar)
            ],
            ESCOLHENDO_MODO: [CallbackQueryHandler(salvar_modo_monitoramento, pattern="^modo_")]
        },
        fallbacks=[],
        allow_reentry=True
    )


# Callback direto do botão "Continuar configuração" (menu_7)
async def responder_menu_7_configurar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await menu_configurar_canal(update, context)


# Função para ser chamada pelo webhook após pagamento aprovado
async def iniciar_configuracao_via_webhook(application, telegram_id):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        user_chat = await application.bot.get_chat(telegram_id)
        texto = (
            "🎉 *Pagamento confirmado!*\n\n"
            "Agora vamos configurar seu canal personalizado do Clipador.\n\n"
            "👣 *Passo 1* — Crie um aplicativo na Twitch:\n"
            "Acesse: https://dev.twitch.tv/console/apps\n"
            "Clique em *Register Your Application* e preencha:\n"
            "- Name: Clipador\n"
            "- OAuth Redirect URL: `https://clipador.com.br/redirect`\n"
            "- Category: Chat Bot\n\n"
            "Depois de criar, envie aqui no bot:\n"
            "`Client ID` e `Client Secret`\n\n"
            "*Exemplo:* \n"
            "`ID: abc123`\n"
            "`SECRET: def456`\n\n"
            "Quando estiver pronto, clique abaixo 👇"
        )
        botoes = [
            [InlineKeyboardButton("📨 Enviar dados da Twitch", callback_data="enviar_twitch")],
            [InlineKeyboardButton("🔙 Voltar ao início", callback_data="menu_0")]
        ]
        await application.bot.send_message(chat_id=telegram_id, text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"Erro ao enviar mensagem inicial para {telegram_id}: {e}")
        return False
