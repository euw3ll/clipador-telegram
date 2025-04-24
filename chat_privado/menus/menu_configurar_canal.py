from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import requests
from core.ambiente import MERCADO_PAGO_ACCESS_TOKEN
from io import BytesIO

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
        await menu_configurar_canal(update, context)
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
