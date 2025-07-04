import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from core.database import obter_ou_criar_config_notificacao, atualizar_config_notificacao

logger = logging.getLogger(__name__)

# Função auxiliar para construir o menu
async def _construir_menu_notificacoes(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Constrói a mensagem e os botões para o menu de notificações."""
    config = obter_ou_criar_config_notificacao(telegram_id)

    status_online = "Ativado ✅" if config.get('notificar_online') else "Desativado ❌"

    texto = (
        "🔔 *Central de Notificações*\n\n"
        "Gerencie aqui os avisos que você recebe no seu canal.\n\n"
        "🔹 *Streamer Online:* Receba um aviso quando um streamer monitorado iniciar a transmissão."
    )

    botoes = [
        [InlineKeyboardButton(f"Streamer Online: {status_online}", callback_data="toggle_notificacao_online")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")] # Volta para o menu de gerenciamento
    ]

    return texto, InlineKeyboardMarkup(botoes)

# Handler principal para abrir o menu
async def abrir_menu_notificacoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o menu de gerenciamento de notificações."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    texto, keyboard = await _construir_menu_notificacoes(telegram_id)

    await query.edit_message_text(
        text=texto,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# Handler para ativar/desativar as notificações
async def toggle_notificacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ativa ou desativa um tipo de notificação."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    tipo_notificacao = query.data.replace("toggle_notificacao_", "")

    config_atual = obter_ou_criar_config_notificacao(telegram_id)

    if tipo_notificacao == "online":
        novo_status = not config_atual.get('notificar_online')
        atualizar_config_notificacao(telegram_id, notificar_online=novo_status)
        logger.info(f"Notificação 'online' alterada para {novo_status} para o usuário {telegram_id}.")
    
    # Reconstrói e edita o menu para refletir a mudança
    texto, keyboard = await _construir_menu_notificacoes(telegram_id)
    await query.edit_message_text(
        text=texto,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )