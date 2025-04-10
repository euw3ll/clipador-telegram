from telegram import Update
from telegram.ext import ContextTypes


async def responder_primeira_interacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name or "usuário"
    mensagem = (
        f"Aoba Clipadô! {nome}, que nome lindo 😍\n\n"
        "Notei que você NÃO TEM UMA ASSINATURA ATIVA 😱\n"
        "Está deixando dinheiro parado na mesa heinn... 💸"
    )
    await update.message.reply_text(mensagem)
