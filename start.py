from configuracoes import TIPO_LOG, ENABLE_NGROK
from core.bootstrap import validar_variaveis_ambiente
from core.database import inicializar_banco # <-- 1. Importar a nova função
import os
import subprocess
import time
import requests

os.environ["PYTHONWARNINGS"] = "ignore"

import warnings
warnings.filterwarnings("ignore")

from threading import Thread
from core.launcher import iniciar_clipador
from canal_gratuito.core.telegram import atualizar_descricao_telegram_offline

def iniciar_webhook():
    if ENABLE_NGROK:
        print("🌐 Iniciando servidor do Webhook Kirvano com ngrok...")
    else:
        print("🌐 Iniciando servidor do Webhook Kirvano (ngrok desativado)...")
    subprocess.Popen(["python3", "start_webhook.py"])

try:
    # Valida as variáveis de ambiente primeiro
    validar_variaveis_ambiente()
    print("✅ Ambiente validado com sucesso.\n")

    # Prepara o banco de dados ANTES de iniciar qualquer outra funcionalidade
    print("🔧 Preparando o banco de dados PostgreSQL...")
    inicializar_banco() # <-- 2. Chamar a função de inicialização
    print("✅ Banco de dados pronto.\n")


    Thread(target=iniciar_webhook).start()

    print("🚀 Iniciando Clipador!")
    iniciar_clipador(validar_variaveis=False)
except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.")
    atualizar_descricao_telegram_offline()