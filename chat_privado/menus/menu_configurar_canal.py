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
from core.database import (
    buscar_configuracao_canal,
    salvar_progresso_configuracao,
    limpar_progresso_configuracao,
    conectar
)
from chat_privado.usuarios import get_nivel_usuario
from core.telethon_criar_canal import criar_canal_telegram

logger = logging.getLogger(__name__)

async def limpar_e_enviar_nova_etapa(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str, botoes: list, parse_mode="Markdown"):
    # Apagar mensagens antigas armazenadas
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    # Tentar editar a mensagem se for callback, senão enviar nova
    try:
        if update.callback_query:
            await update.callback_query.answer()
            nova_msg = await update.callback_query.edit_message_text(
                text=texto,
                reply_markup=InlineKeyboardMarkup(botoes),
                parse_mode=parse_mode
            )
        else:
            nova_msg = await update.message.reply_text(
                text=texto,
                reply_markup=InlineKeyboardMarkup(botoes),
                parse_mode=parse_mode
            )
        context.user_data["mensagens_para_apagar"] = [nova_msg.message_id]
    except:
        nova_msg = await update.effective_message.reply_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(botoes),
            parse_mode=parse_mode
        )
        context.user_data["mensagens_para_apagar"] = [nova_msg.message_id]

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
        # Apagar todas as mensagens anteriores, inclusive o menu de planos
        for msg_id in context.user_data.get("mensagens_para_apagar", []):
            try:
                await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
            except:
                pass
        context.user_data["mensagens_para_apagar"] = []
        # Armazene a mensagem anterior de plano selecionado para posterior exclusão
        context.user_data["mensagem_plano_selecionado"] = query.message.message_id
        # Apagar a mensagem de plano selecionado com botões, se existir
        if "mensagem_plano_selecionado" in context.user_data:
            try:
                await context.bot.delete_message(chat_id=query.from_user.id, message_id=context.user_data["mensagem_plano_selecionado"])
            except:
                pass
            context.user_data.pop("mensagem_plano_selecionado", None)
        # Recuperar o email de pagamento
        email_pagamento = context.user_data.get("email_pagamento", "desconhecido")
        await iniciar_configuracao_pos_pagamento(update, context, email_pagamento)
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
    # Remover mensagens extras após ativação gratuita para admin
    if context.user_data.get("produto_gratis_ativado_admin"):
        for msg_id in context.user_data.get("mensagens_para_apagar", []):
            try:
                await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
            except:
                pass
        context.user_data["mensagens_para_apagar"] = []

    configuracao = buscar_configuracao_canal(query.from_user.id)
    # Checagem de etapas da configuração
    if configuracao:
        if not configuracao.get("twitch_client_id") or not configuracao.get("twitch_client_secret"):
            return await iniciar_envio_twitch(update, context)
        if not configuracao.get("streamers"):
            return await receber_credenciais(update, context)
        if not configuracao.get("modo"):
            return await escolher_modo_monitoramento(update, context)
    if configuracao and configuracao.get("twitch_client_id") and configuracao.get("streamers"):
        if context.user_data.get("produto_gratis_ativado_admin"):
            for msg_id in context.user_data.get("mensagens_para_apagar", []):
                try:
                    await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
                except:
                    pass
            context.user_data["mensagens_para_apagar"] = []
        texto = "⚙️ Seu canal já está configurado.\n\nO que deseja fazer?"
        botoes = [
            [InlineKeyboardButton("👁 Ver canal", callback_data="ver_canal")],
            [InlineKeyboardButton("🔧 Alterar configuração", callback_data="enviar_twitch")],
            [InlineKeyboardButton("ℹ️ Ver plano", callback_data="ver_plano")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]
        ]
        await limpar_e_enviar_nova_etapa(update, context, texto, botoes, parse_mode=None)
        return

    texto = (
        "👣 *Passo 1* — Crie um aplicativo na Twitch:\n"
        "https://dev.twitch.tv/console/apps\n\n"
        "Use:\n- Name: Clipador\n- Redirect URL: `https://clipador.com.br/redirect`\n- Category: Chat Bot\n\n"
        "Depois envie aqui:\n`ID: abc123`\n`SECRET: def456`\n\n"
    )
    botoes = [
        [InlineKeyboardButton("📨 Enviar dados da Twitch", callback_data="enviar_twitch")]
    ]

    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)

async def iniciar_configuracao_pos_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE, email_pagamento: str = ""):
    await update.callback_query.answer()
    # Apagar a mensagem de plano selecionado com botões, se existir
    if "mensagem_plano_selecionado" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=context.user_data["mensagem_plano_selecionado"])
        except:
            pass
        context.user_data.pop("mensagem_plano_selecionado", None)
    # Limpar mensagens salvas e remover qualquer mensagem do tipo "Plano selecionado"
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=f"🔓 Produto gratuito ativado para admin.\nPlano: *{context.user_data.get('nome_plano', 'Indefinido')}*.\n📧 Ativado com: `{email_pagamento}`\n\nClique no botão abaixo para configurar seu canal personalizado:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Continuar configuração", callback_data="continuar_configuracao")]
        ]),
        parse_mode="Markdown"
    )
    await menu_configurar_canal(update, context)

async def iniciar_envio_twitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    # Apagar mensagens antigas
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    texto = (
        "🧩 Agora me diga as credenciais do aplicativo que você criou na Twitch:\n\n"
        "Envie nesse formato exato:\n\n"
        "`ID: abc123`\n`SECRET: def456`"
    )
    from telegram import ForceReply
    msg = await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=texto,
        reply_markup=ForceReply(selective=True),
        parse_mode="Markdown"
    )
    context.user_data["mensagens_para_apagar"] = [msg.message_id]
    return ESPERANDO_CREDENCIAIS

async def receber_credenciais(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Apagar mensagens anteriores da etapa de credenciais
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    texto = update.message.text
    twitch_id, twitch_secret = "", ""
    for linha in texto.splitlines():
        if linha.lower().startswith("id:"):
            twitch_id = linha.split(":", 1)[1].strip()
        elif linha.lower().startswith("secret:"):
            twitch_secret = linha.split(":", 1)[1].strip()

    if not twitch_id or not twitch_secret or len(twitch_id) < 10 or len(twitch_secret) < 10:
        await limpar_e_enviar_nova_etapa(
            update,
            context,
            "❌ Formato inválido. Envie no formato:\n\n`ID: sua_client_id`\n`SECRET: seu_client_secret`",
            [],
        )
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
    # Persistência dos dados parciais
    context.user_data["canal_config"] = {
        "twitch_id": twitch_id,
        "twitch_secret": twitch_secret,
        "streamers": [],
        "modo": None
    }
    # Salvar progresso da configuração (etapa credenciais)
    from core.database import salvar_progresso_configuracao
    salvar_progresso_configuracao(telegram_id, etapa="credenciais", dados_parciais={
        "twitch_client_id": twitch_id,
        "twitch_client_secret": twitch_secret
    })

    texto_etapa = (
        f"✅ Credenciais recebidas!\n\nAgora envie o nome do streamer que deseja monitorar (ex: gaules). *Não use @*.\n\n"
        f"📌 Você pode cadastrar até {limite_streamers} streamers. Slots extras estarão disponíveis futuramente.\n"
        f"Você pode digitar `/continuar` a qualquer momento para avançar."
    )
    await limpar_e_enviar_nova_etapa(update, context, texto_etapa, [])
    return ESPERANDO_STREAMERS

async def receber_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    streamers = context.user_data.get("streamers", [])
    limite = context.user_data.get("limite_streamers")

    if nome.isdigit():
        indice = int(nome) - 1
        if 0 <= indice < len(streamers):
            removido = streamers.pop(indice)
            await limpar_e_enviar_nova_etapa(update, context, f"❌ Removido: {removido}", [])
            context.user_data["streamers"] = streamers
            # Atualiza persistência
            if "canal_config" in context.user_data:
                context.user_data["canal_config"]["streamers"] = streamers
            # Salvar progresso da configuração (etapa streamers)
            from core.database import salvar_progresso_configuracao
            salvar_progresso_configuracao(update.message.from_user.id, etapa="streamers", dados_parciais={
                "streamers": streamers
            })
            return ESPERANDO_STREAMERS

    if len(streamers) >= limite:
        await limpar_e_enviar_nova_etapa(update, context, "❌ Você já atingiu o limite de streamers.", [])
        # Salvar progresso da configuração (etapa streamers)
        from core.database import salvar_progresso_configuracao
        salvar_progresso_configuracao(update.message.from_user.id, etapa="streamers", dados_parciais={
            "streamers": streamers
        })
        # Limpar mensagens antes de ir para a escolha de modo
        context.user_data["mensagens_para_apagar"] = []
        return await escolher_modo_monitoramento(update, context)

    streamers.append(nome)
    context.user_data["streamers"] = streamers
    # Atualiza persistência
    if "canal_config" in context.user_data:
        context.user_data["canal_config"]["streamers"] = streamers
    # Salvar progresso da configuração (etapa streamers)
    from core.database import salvar_progresso_configuracao
    salvar_progresso_configuracao(update.message.from_user.id, etapa="streamers", dados_parciais={
        "streamers": streamers
    })

    if len(streamers) < limite:
        lista = "\n".join([f"{i+1}. {s}" for i, s in enumerate(streamers)])
        restante = limite - len(streamers)
        texto = (
            f"✅ Adicionado: {nome}\n\nStreamers atuais:\n{lista}\n\n"
            f"Você pode enviar mais {restante}, digite /continuar ou envie o número para remover."
        )
        await limpar_e_enviar_nova_etapa(update, context, texto, [])
        return ESPERANDO_STREAMERS
    else:
        # Limpar mensagens antes de ir para a escolha de modo
        context.user_data["mensagens_para_apagar"] = []
        return await escolher_modo_monitoramento(update, context)

async def comando_continuar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await escolher_modo_monitoramento(update, context)

async def escolher_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Limpeza das mensagens anteriores de configuração de streamers
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []
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
    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
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
    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
    return ESCOLHENDO_MODO

async def salvar_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data.replace("modo_", "")
    context.user_data["modo_monitoramento"] = modo
    # Atualiza persistência
    if "canal_config" in context.user_data:
        context.user_data["canal_config"]["modo"] = modo

    telegram_id = query.from_user.id
    # Salvar progresso da configuração (etapa modo)
    from core.database import salvar_progresso_configuracao
    salvar_progresso_configuracao(telegram_id, etapa="modo", dados_parciais={
        "modo": modo
    })
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
        f"⚠️ Após salvar, você terá até 1 hora para alterar os streamers preenchidos.\n"
        f"Slots vazios poderão ser preenchidos depois, sem prazo."
    )
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []
    botoes = [
        [InlineKeyboardButton("✅ Confirmar e salvar", callback_data="confirmar_salvar_canal")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_streamers")]
    ]
    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
    return ESCOLHENDO_MODO

async def confirmar_salvar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    username = query.from_user.username or f"user{telegram_id}"

    canal_config = context.user_data.get("canal_config", {})
    twitch_client_id = context.user_data.get("twitch_id") or canal_config.get("twitch_id")
    twitch_client_secret = context.user_data.get("twitch_secret") or canal_config.get("twitch_secret")
    streamers = context.user_data.get("streamers") or canal_config.get("streamers", [])
    modo = context.user_data.get("modo_monitoramento") or canal_config.get("modo")

    # Apagar mensagens antigas
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=telegram_id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    salvar_configuracao_canal(telegram_id, twitch_client_id, twitch_client_secret, streamers, modo)
    # Limpar progresso da configuração ao finalizar
    from core.database import limpar_progresso_configuracao
    limpar_progresso_configuracao(telegram_id)
    atualizar_telegram_id_usuario(telegram_id)
    await criar_canal_telegram(username=query.from_user.username, telegram_id=telegram_id)

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