from core.ambiente import (
    TWITCH_CLIENT_ID,
    TWITCH_CLIENT_SECRET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)


#IDs dos usuários administradores do bot
ADMIN_TELEGRAM_IDS = [1527996001] # Adicione o ID do novo admin aqui


"""CONFIGURAÇÕES DO CANAL GRATUITO"""
# 💬 CANAL DO TELEGRAM
CANAL_GRATUITO_ID = TELEGRAM_CHAT_ID # ID numérico do canal gratuito
LINK_CANAL_GRATUITO = "https://t.me/clipadorfree" # IMPORTANTE: Substitua pelo link de convite do seu canal gratuito

INTERVALO_ATUALIZAR_DESCRICAO = 300
INTERVALO_MENSAGEM_PROMOCIONAL = 800
INTERVALO_MENSAGEM_HEADER = 5400
INTERVALO_ATUALIZACAO_STREAMERS = 5400

# 🔄 SWITCHES DE FUNCIONALIDADE
MODO_MONITORAMENTO_GRATUITO = "MANUAL" # Opções para o canal gratuito: 'AUTOMATICO' (sensibilidade baseada em viewers) ou 'MANUAL' (usa as constantes de `canal_gratuito/core/monitor.py`)
TIPO_LOG = "PADRAO"  # "PADRAO" ou "DESENVOLVEDOR"
ATUALIZAR_DESCRICAO = True
ENVIAR_CLIPES = True
USAR_VERIFICACAO_AO_VIVO = True

"""CONFIGURAÇÕES DO CHAT PRIVADO"""
MODO_MANUTENCAO = False
GATEWAY_PAGAMENTO = "KIRVANO"  # 'MERCADOPAGO' ou 'KIRVANO'
SUPPORT_USERNAME = "euw3ll" # Usuário para o botão de suporte

# Links de pagamento da Kirvano
KIRVANO_LINKS = {
    "Mensal Solo": "https://pay.kirvano.com/3f315c85-0164-4b55-81f2-6ffa661b670c",
    "Mensal Plus": "https://pay.kirvano.com/6283e70f-f385-4355-8cff-e02275935cde",
    "Anual Pro": "https://pay.kirvano.com/09287018-c006-4c0e-87c7-08a6e4464e79",
    "Slot Extra": "https://pay.kirvano.com/6f6d41a4-f4a9-459a-892f-b881b34b602e"
}

# Preços dos planos e produtos
PLANOS_PRECOS = {
    "Mensal Solo": 19.90,
    "Mensal Plus": 39.90,
    "Anual Pro": 199.00,
    "Slot Extra": 9.90
}