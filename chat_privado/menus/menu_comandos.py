from telegram import Update
from telegram.ext import ContextTypes
from chat_privado.usuarios import get_nivel_usuario

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
    elif nivel == 9:
        texto = (
            f"🛠️ *Ajuda Administrativa – Olá {nome}!*\n\n"
            "Comandos administrativos:\n"
            "/menu – Acessar o menu principal\n"
            "/usuarios – Listar usuários cadastrados\n"
            "/criarcanal – Criar novo canal monitorado\n"
            "/broadcast – Enviar mensagem para todos\n"
        )
    else:
        texto = (
            f"👀 *Ajuda padrão – Olá {nome}*\n\n"
            "Se você está vendo isso, algo pode estar errado com seu tipo de usuário.\n"
            "Tente usar /menu ou fale com o suporte após assinar."
        )

    await update.message.reply_text(texto, parse_mode="Markdown")
