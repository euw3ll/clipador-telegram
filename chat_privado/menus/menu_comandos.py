from telegram import Update
from telegram.ext import ContextTypes
from chat_privado.usuarios import get_nivel_usuario
from core.database import (
    is_usuario_admin,
    buscar_configuracao_canal, # Já importado
    is_configuracao_completa, # Nova importação
    assinatura_em_configuracao
)

async def responder_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nome = update.effective_user.first_name or "usuário"
    nivel = get_nivel_usuario(user_id)

    if nivel == 1:
        texto = (
            f"🤖 *Ajuda do Clipador – Olá {nome}!*\n\n"
            "Comandos disponíveis:\n"
            "/menu – Abrir o menu principal\n"
            "/planos – Ver os planos disponíveis\n"
            "/assinar – Iniciar sua assinatura\n"
        )
    elif nivel == 2:
        texto = (
            f"✅ *Ajuda do Clipador – Olá {nome}, assinante ativo!*\n\n"
            "Comandos úteis:\n"
            "/menu – Acessar o menu principal\n"
            "/meusdados – Ver sua assinatura atual\n"
            "/alterarstreamer – Trocar streamer monitorado (1x/mês)\n"
        )
    elif is_usuario_admin(user_id): # Agora verifica diretamente se é admin
        texto = (
            f"🛠️ *Ajuda Administrativa – Olá {nome}!*\n\n"
            "Comandos administrativos (use /admin para o painel completo):\n"
            "/menu – Acessar o menu principal\n"
            "/admin – Abrir o painel de administração\n"
            # Você pode listar outros comandos gerais de admin aqui se existirem,
            # mas o gerenciamento específico de usuários/canais está agora sob /admin
        )
    else:
        texto = (
            f"👀 *Ajuda padrão – Olá {nome}*\n\n"
            "Se você está vendo isso, algo pode estar errado com seu tipo de usuário.\n"
            "Tente usar /menu ou fale com o suporte após assinar."
        )

    await update.message.reply_text(texto, parse_mode="Markdown")

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
