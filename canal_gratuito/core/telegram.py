import requests
from core.ambiente import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

ultima_descricao = None

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


def atualizar_descricao_telegram(minimo_clipes, intervalo_segundos, quantidade_streamers, chat_id=TELEGRAM_CHAT_ID):
    global ultima_descricao

    descricao_nova = (
        f"😎 CLIPADOR ONLINE\n"
        f"🇧🇷 Top {quantidade_streamers} streamers do Brasil\n"
        f"🔥 {minimo_clipes}+ clipes em {intervalo_segundos}s = ENVIO"
    )

    if descricao_nova == ultima_descricao:
        return  # 🔁 Já é igual, não envia

    print("🔍 Tentando atualizar descrição com o seguinte conteúdo:")
    print(repr(descricao_nova))
    print(f"📏 Tamanho: {len(descricao_nova)} caracteres")

    if len(descricao_nova) > 255:
        descricao_nova = descricao_nova[:252] + "..."

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatDescription"
    payload = {
        "chat_id": chat_id,
        "description": descricao_nova
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 400 and "Bad Request" in response.text:
            print("⚠️ Descrição já é igual ou erro de permissão. Ignorando.")
            return
        response.raise_for_status()
        ultima_descricao = descricao_nova
        print("✅ Descrição atualizada com sucesso.")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Erro ao atualizar descrição do canal: {e}")


def enviar_mensagem_promocional(chat_id=TELEGRAM_CHAT_ID):
    mensagem = (
        "💸 <b>Quer um canal monitorando seus Streamers</b>"
        " e fazer R$700 toda semana clipando?\n\n"
        "Garanta agora 👉 @ClipadorBot"
    )
    enviar_mensagem(mensagem, chat_id=chat_id)

def enviar_header_streamers(lista_streamers, chat_id=TELEGRAM_CHAT_ID):
    if not lista_streamers:
        return

    # 1. Desfixar mensagem anterior (se houver)
    try:
        url_unpin = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/unpinChatMessage"
        requests.post(url_unpin, json={"chat_id": chat_id})
    except Exception as e:
        print(f"⚠️ Erro ao desfixar mensagem anterior: {e}")

    # 2. Criar nova mensagem
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

    # 3. Fixar a nova
    if message_id:
        url_pin = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/pinChatMessage"
        requests.post(url_pin, json={"chat_id": chat_id, "message_id": message_id, "disable_notification": True})

def enviar_mensagem_atualizacao_streamers(qtd=5, chat_id=TELEGRAM_CHAT_ID):
    mensagem = (
        f"Estamos acompanhando em tempo real os <b>{qtd} streamers mais assistidos do Brasil</b> no momento.\n\n"
        "📺 Fique ligado e aproveite os melhores clipes! 🎯"
    )
    enviar_mensagem(mensagem, chat_id=chat_id)

def atualizar_descricao_telegram_offline(chat_id=TELEGRAM_CHAT_ID):
    descricao = "O CLIPADOR ESTÁ OFFLINE 😭"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatDescription"
    data = {
        "chat_id": chat_id,
        "description": descricao
    }

    try:
        r = requests.post(url, json=data)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Erro ao atualizar descrição do canal para OFFLINE: {e}")
