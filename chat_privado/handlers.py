from telegram import Update
from telegram.ext import ContextTypes
from .usuarios import get_nivel_usuario, registrar_usuario

# 🛠️ Alternativa temporária de manutenção
MODO_MANUTENCAO = True

NIVEIS = {
    1: "USUÁRIO NOVO",
    2: "ASSINANTE",
    4: "EX-ASSINANTE",
    9: "ADMINISTRADOR"
}

async def responder_primeira_interacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nome = update.effective_user.first_name or "usuário"

    registrar_usuario(user_id)
    nivel = get_nivel_usuario(user_id)

    if MODO_MANUTENCAO:
        await update.message.reply_text("🛠️ O Clipador está em manutenção temporária.\nTente novamente mais tarde.")
        return

    if nivel == 1:
        mensagem = (
            f"Aoba Clipadô! {nome}, que nome lindo 😍\n\n"
            "Notei que você NÃO TEM UMA ASSINATURA ATIVA 😱\n"
            "Está deixando dinheiro parado na mesa heinn... 💸"
        )
    else:
        mensagem = f"🔐 {NIVEIS.get(nivel, 'Nível desconhecido')}"

    await update.message.reply_text(mensagem)
