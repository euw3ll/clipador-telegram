from telegram import Update
from telegram.ext import ContextTypes
from chat_privado.usuarios import get_nivel_usuario
from core.database import (
    is_usuario_admin,
    buscar_configuracao_canal, # Já importado
    is_configuracao_completa, # Nova importação
    assinatura_em_configuracao
)

async def skip_configuracao_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite que um admin pule a configuração do canal se estiver pendente."""
    telegram_id = update.effective_user.id

    if not is_usuario_admin(telegram_id):
        await update.message.reply_text("❌ Este comando é exclusivo para administradores.")
        return

    # Verifica se o usuário é um assinante ativo (nível 2) e a configuração não está completa
    if get_nivel_usuario(telegram_id) == 2 and not is_configuracao_completa(telegram_id):
        from core.database import marcar_configuracao_completa # Nova importação
        marcar_configuracao_completa(telegram_id, False) # Marca como não finalizada
        await update.message.reply_text(
            "✅ Ok, configuração pulada por enquanto.\n\n"
            "Você pode retomar a qualquer momento usando o menu do comando /start."
        )
    else:
        await update.message.reply_text("Você não possui nenhuma configuração de canal pendente para pular.")
