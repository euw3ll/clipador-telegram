import requests
from canal_gratuito.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def enviar_mensagem(texto, botao_url=None, botao_texto=None, chat_id=TELEGRAM_CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    if botao_url and botao_texto:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": botao_texto, "url": botao_url}]]
        }

    r = requests.post(url, json=payload)
    r.raise_for_status()


def atualizar_descricao_telegram(streamer_nome, status, viewers, minimo_clipes, intervalo, chat_id=TELEGRAM_CHAT_ID):
    status_emoji = "🔴 AO VIVO" if status == "ONLINE" else "🟡 OFFLINE"
    
    descricao = (
        f"O CLIPADOR ESTÁ ONLINE 😎\n"
        f"👀 @{streamer_nome} - {status_emoji}\n"
        f"👥 {viewers} espectadores agora\n"
        f"🔥 Grupo de {minimo_clipes} clipes em {intervalo}s"
    )

    # Remove emojis problemáticos e limita com segurança
    descricao = remover_caracteres_invalidos(descricao)[:255]

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatDescription"
    data = {
        "chat_id": chat_id,
        "description": descricao
    }

    try:
        r = requests.post(url, json=data)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erro ao atualizar descrição do canal: {e}\nConteúdo: {descricao}")

def remover_caracteres_invalidos(texto):
    # Remove emojis e símbolos que não são aceitos na descrição
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Símbolos e pictogramas
        "\U0001F680-\U0001F6FF"  # Transporte e mapas
        "\U0001F1E0-\U0001F1FF"  # Bandeiras
        "\U00002700-\U000027BF"  # Dingbats
        "\U0001F900-\U0001F9FF"  # Suplemento de emojis
        "\U0001FA70-\U0001FAFF"  # Suplemento de símbolos adicionais
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub("", texto).strip()


# 🔹 Mensagem promocional para quem quiser contratar o Clipador
def enviar_mensagem_promocional(chat_id=TELEGRAM_CHAT_ID):
    mensagem = (
        "💸 <b>Quer um canal monitorando seus Streamers</b>"
        " e fazer R$700 toda semana clipando?\n\n"
        "Garanta agora 👉 @ClipadorBot"
    )
    enviar_mensagem(mensagem, chat_id=chat_id)


# 🔹 Header do canal com streamers monitorados
def enviar_header_streamers(lista_streamers, chat_id=TELEGRAM_CHAT_ID):
    if not lista_streamers:
        return

    nomes = "\n".join([f"• @{s}" for s in lista_streamers])
    mensagem = (
        "📢 <b>STREAMERS MONITORADOS AGORA:</b>\n"
        f"{nomes}\n\n"
        "🚀 <b>Quer monitorar outros?</b> Assine o Clipador 👉 @ClipadorBot"
    )

    url_send = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML"
    }

    r = requests.post(url_send, json=payload)
    r.raise_for_status()
    message_id = r.json().get("result", {}).get("message_id")

    if message_id:
        url_pin = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/pinChatMessage"
        requests.post(url_pin, json={"chat_id": chat_id, "message_id": message_id, "disable_notification": True})


# 🔹 Mensagem automática ao atualizar os streamers monitorados
def enviar_mensagem_atualizacao_streamers(chat_id=TELEGRAM_CHAT_ID):
    mensagem = (
        "Estamos acompanhando em tempo real os <b>5 streamers mais assistidos do Brasil</b> no momento.\n\n"
        "📺 Fique ligado e aproveite os melhores clipes! 🎯"
    )
    enviar_mensagem(mensagem, chat_id=chat_id)
