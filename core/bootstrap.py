from core.ambiente import (
    TWITCH_CLIENT_ID,
    TWITCH_CLIENT_SECRET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID
)
from core.database import criar_tabelas  # ⬅️ IMPORTANTE

def validar_variaveis_ambiente():
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        raise EnvironmentError("❌ Variáveis da Twitch não configuradas corretamente.")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise EnvironmentError("❌ Variáveis do Telegram não configuradas corretamente.")

def iniciar_ambiente():
    print("🔁 Validando variáveis de ambiente...")
    validar_variaveis_ambiente()
    criar_tabelas()  # ⬅️ CRIA AS TABELAS NO BANCO
    print("✅ Ambiente validado com sucesso.")
