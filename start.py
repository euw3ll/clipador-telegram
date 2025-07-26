from configuracoes import TIPO_LOG, ENABLE_NGROK
from core.bootstrap import validar_variaveis_ambiente
from core.database import inicializar_banco
import os
import time
from threading import Thread

# Imports movidos para o topo para melhor organização
from core.launcher import iniciar_clipador
from core.gateway.webhook_kirvano import iniciar_webhook
from canal_gratuito.core.telegram import atualizar_descricao_telegram_offline

os.environ["PYTHONWARNINGS"] = "ignore"

import warnings
warnings.filterwarnings("ignore")

try:
    # Valida as variáveis de ambiente primeiro
    validar_variaveis_ambiente()
    print("✅ Ambiente validado com sucesso.\n")

    # Prepara o banco de dados ANTES de iniciar qualquer outra funcionalidade
    print("🔧 Preparando o banco de dados PostgreSQL...")
    inicializar_banco()
    print("✅ Banco de dados pronto.\n")

    # --- INÍCIO DA ETAPA 2: Inversão da Lógica de Inicialização ---
    
    # 1. Inicia o bot do Clipador em uma thread separada (processo de fundo)
    print("🚀 Iniciando o bot Clipador em segundo plano...")
    bot_thread = Thread(target=iniciar_clipador, args=(False,))
    bot_thread.daemon = True  # Permite que o programa principal finalize mesmo com a thread rodando
    bot_thread.start()
    
    # 2. Inicia o servidor web no processo principal.
    #    Isso mantém a aplicação "viva" para o Render e responde aos health checks.
    print("🌐 Iniciando servidor web principal para o webhook...")
    iniciar_webhook()

    # --- FIM DA ETAPA 2 ---

except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.")
    atualizar_descricao_telegram_offline()