from configuracoes import TIPO_LOG, ENABLE_NGROK
from core.bootstrap import validar_variaveis_ambiente
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
    validar_variaveis_ambiente()
    print("✅ Ambiente validado com sucesso.\n")

    Thread(target=iniciar_webhook).start() # Mantém a inicialização em thread

    print("🚀 Iniciando Clipador!")
    iniciar_clipador(validar_variaveis=False)
except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.")
    atualizar_descricao_telegram_offline()