import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def enviar_mensagem(texto, botao_url=None, botao_texto="📥 BAIXAR CLIPE"):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
    }

    if botao_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": botao_texto, "url": botao_url}]]
        }

    response = requests.post(url, json=payload)

    if response.status_code != 200:
        print("❌ Erro ao enviar mensagem:", response.text)


def atualizar_descricao_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatDescription"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "description": texto[:255]  # Limite do Telegram
    }

    requests.post(url, data=payload) 
