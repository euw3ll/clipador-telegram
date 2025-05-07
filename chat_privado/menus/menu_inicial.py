from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.ext import CommandHandler
from chat_privado.usuarios import get_nivel_usuario
from core.database import buscar_configuracao_canal

async def responder_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    nome = update.effective_user.first_name or "Clipado"
    nivel = get_nivel_usuario(telegram_id, nome)  # já registra se não existir

    # Mensagem personalizada conforme o tipo de usuário
    if nivel == 1:
        texto = (
            f"👋 Aoba Clipadô! Seja bem-vindo {nome}, que nome lindo 😍\n\n"
            "Aqui você recebe os *melhores momentos das lives* direto no seu Telegram, sem esforço 🎯\n\n"
            "Notei que você *ainda não tem uma assinatura ativa* 😱\n"
            "Mas relaxa... ainda dá tempo de mudar isso 💸"
        )
        botoes = [
            [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
            [InlineKeyboardButton("💸 Ver planos", callback_data="menu_2")],
        ]

    elif nivel == 2:
        config = buscar_configuracao_canal(telegram_id)
        if config and (not config.get("twitch_client_id") or not config.get("streamers") or not config.get("modo")):
            if not config.get("twitch_client_id"):
                texto = (
                    f"✅ Pagamento confirmado, {nome}!\n\n"
                    "Vamos começar sua configuração.\n\n"
                    "Clique abaixo para informar suas credenciais da Twitch:"
                )
                botoes = [[InlineKeyboardButton("🔐 Enviar credenciais", callback_data="enviar_twitch")]]
            elif not config.get("streamers"):
                texto = (
                    f"✅ Credenciais recebidas, {nome}!\n\n"
                    "Agora envie os nomes dos streamers que deseja monitorar:"
                )
                botoes = [[InlineKeyboardButton("📺 Continuar configuração", callback_data="menu_configurar_canal")]]
            elif not config.get("modo"):
                texto = (
                    f"📺 Streamers recebidos com sucesso, {nome}!\n\n"
                    "Agora falta apenas selecionar o modo de monitoramento:"
                )
                botoes = [[InlineKeyboardButton("🧠 Escolher modo", callback_data="menu_configurar_canal")]]
        else:
            texto = (
                f"😎 E aí {nome}, o que vamos fazer hoje meu assinante favorito?\n\n"
                "Seu Clipador tá no pique pra caçar os melhores momentos das lives 🎯🔥"
            )
            botoes = [
                [InlineKeyboardButton("⚙️ Configurar canal", callback_data="menu_7")],
                [InlineKeyboardButton("📋 Ver plano atual", callback_data="menu_8")],
                [InlineKeyboardButton("📣 Abrir meu canal", url="https://t.me/seu_canal")],
            ]

    elif nivel == 4:
        texto = (
            f"😕 Sua assinatura expirou, {nome}.\n\n"
            "Que tal renovar agora e voltar a receber os melhores momentos automaticamente?"
        )
        botoes = [
            [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
            [InlineKeyboardButton("💸 Ver planos", callback_data="menu_2")],
        ]

    elif nivel == 999:
        texto = (
            f"🛠️ Eita porr@, a administração do grupo chegou...\n\n"
            f"E aí {nome}, quer fazer o que hoje? Use o /help para ver as opções."
        )
        botoes = [
            [InlineKeyboardButton("👤 Gerenciar usuários", callback_data="menu_admin_usuarios")],
            [InlineKeyboardButton("📊 Ver estatísticas", callback_data="menu_admin_stats")],
        ]

    else:
        texto = (
            f"👋 Aoba Clipadô! Seja bem-vindo {nome}, que nome lindo 😍\n\n"
            "Aqui você recebe os *melhores momentos das lives* direto no seu Telegram, sem esforço 🎯\n\n"
            "Notei que você *ainda não tem uma assinatura ativa* 😱\n"
            "Mas relaxa... ainda dá tempo de mudar isso 💸"
        )
        botoes = [
            [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
            [InlineKeyboardButton("💸 Ver planos", callback_data="menu_2")],
        ]

    if update.message:
        await update.message.reply_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(botoes),
            parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(botoes),
            parse_mode="Markdown"
        )

async def voltar_ao_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usado quando o usuário clica em '🔙 Voltar ao menu'"""
    return await responder_inicio(update, context)

def registrar_menu_inicial(application):
    application.add_handler(CommandHandler("start", responder_inicio))
