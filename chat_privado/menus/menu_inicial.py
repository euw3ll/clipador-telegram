from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.ext import CommandHandler
from chat_privado.usuarios import get_nivel_usuario
from core.database import buscar_configuracao_canal, is_configuracao_completa # Nova importação

async def responder_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    nome = update.effective_user.first_name or "Clipado"
    nivel = get_nivel_usuario(telegram_id, nome)

    texto = ""
    botoes = []

    # Configurações padrão para novos usuários e expirados
    texto_padrao_novo_usuario = (
        f"👋 Aoba Clipadô! Seja bem-vindo {nome}, que nome lindo 😍\n\n"
        "Aqui você recebe os *melhores momentos das lives* direto no seu Telegram, sem esforço 🎯\n\n"
        "Notei que você *ainda não tem uma assinatura ativa* 😱\n"
        "Mas relaxa... ainda dá tempo de mudar isso 💸"
    )
    texto_expirado = (
        f"😕 Sua assinatura expirou, {nome}.\n\n"
        "Que tal renovar agora e voltar a receber os melhores momentos automaticamente?"
    )
    botoes_padrao = [
        [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
        [InlineKeyboardButton("💸 Ver planos", callback_data="menu_2")],
    ]

    # Mapeamento de nível para manipulador
    handlers = {
        1: (texto_padrao_novo_usuario, botoes_padrao),
        4: (texto_expirado, botoes_padrao),
        999: (
            f"🛠️ Eita porr@, a administração do grupo chegou...\n\n"
            f"E aí {nome}, quer fazer o que hoje? Use o /help para ver as opções.",
            [
                [InlineKeyboardButton("👤 Gerenciar usuários", callback_data="menu_admin_usuarios")],
                [InlineKeyboardButton("📊 Ver estatísticas", callback_data="menu_admin_stats")],
            ]
        ),
    }

    # Define texto e botões com base no nível
    if nivel in handlers:
        texto, botoes = handlers[nivel]
    elif nivel == 2:
        config_completa = is_configuracao_completa(telegram_id)
        config = buscar_configuracao_canal(telegram_id)
        link_do_canal = config.get("link_canal_telegram") if config else "#"

        texto = f"😎 E aí {nome}, o que vamos fazer hoje meu assinante favorito?\n\nSeu Clipador tá no pique pra caçar os melhores momentos das lives 🎯🔥"
        if config_completa:
            # Usuário com configuração completa
            botoes = [
                [InlineKeyboardButton("⚙️ Configurar canal", callback_data="abrir_configurar_canal")],
                [InlineKeyboardButton("📋 Ver plano atual", callback_data="menu_8")],
                [InlineKeyboardButton("📣 Abrir meu canal", url=link_do_canal)],
            ]
        else:
            # Usuário com configuração pendente
            botoes = [
                [InlineKeyboardButton("🚨 Finalizar Configuração do Canal", callback_data="abrir_configurar_canal")],
                [InlineKeyboardButton("📋 Ver plano atual", callback_data="menu_8")],
            ]
    else:
        # Fallback para qualquer outro nível ou caso não previsto
        texto, botoes = handlers[1]

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
