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

# ⚙️ PARÂMETROS DE MONITORAMENTO
QUANTIDADE_STREAMERS_TOP_BR = 5      # Quantos streamers do topo do Brasil monitorar.
STREAMERS_ADICIONAIS_GRATUITO = [""] # Lista de streamers para monitorar ADICIONALMENTE aos tops. Deixe [] se não quiser.
INTERVALO_ANALISE_MINUTOS_GRATUITO = 10 # Janela de tempo para buscar clipes (em minutos).

# 🔄 SWITCHES DE FUNCIONALIDADE
MODO_MONITORAMENTO_GRATUITO = "MANUAL" # Opções para o canal gratuito: 'AUTOMATICO' (sensibilidade baseada em viewers) ou 'MANUAL' (usa as constantes de `canal_gratuito/core/monitor.py`)
TIPO_LOG = "PADRAO"  # "PADRAO" ou "DESENVOLVEDOR"
ATUALIZAR_DESCRICAO = True
ENVIAR_CLIPES = True
USAR_VERIFICACAO_AO_VIVO = True

# ⏰ INTERVALOS DE MENSAGENS (em segundos)
INTERVALO_ATUALIZAR_DESCRICAO = 300
INTERVALO_MENSAGEM_PROMOCIONAL = 800
INTERVALO_MENSAGEM_HEADER = 5400
INTERVALO_ATUALIZACAO_STREAMERS = 5400

"""CONFIGURAÇÕES DO CHAT PRIVADO"""
MODO_MANUTENCAO = False
GATEWAY_PAGAMENTO = "KIRVANO"  # 'MERCADOPAGO' ou 'KIRVANO'
SUPPORT_USERNAME = "euw3ll" # Usuário para o botão de suporte

# --- NOVO: Configurações do Teste Gratuito ---
TESTE_GRATUITO_ATIVO = True # True para ativar, False para desativar o botão
TESTE_GRATUITO_DURACAO_DIAS = 3 # Duração do período de teste em dias

# Links de pagamento da Kirvano
KIRVANO_LINKS = {
    "Teste Gratuito": "https://pay.kirvano.com/5f583d6e-2343-4842-9419-0f944bb090c3", # Link para o produto de R$0,00
    "Mensal Solo": "https://pay.kirvano.com/3f315c85-0164-4b55-81f2-6ffa661b670c",
    "Mensal Plus": "https://pay.kirvano.com/6283e70f-f385-4355-8cff-e02275935cde",
    "Anual Pro": "https://pay.kirvano.com/09287018-c006-4c0e-87c7-08a6e4464e79",
    "Slot Extra": "https://pay.kirvano.com/6f6d41a4-f4a9-459a-892f-b881b34b602e"
}

# Preços dos planos e produtos
PLANOS_PRECOS = {
    "Teste Gratuito": 0.00,
    "Mensal Solo": 19.90,
    "Mensal Plus": 39.90,
    "Anual Pro": 199.00,
    "Slot Extra": 9.90
}