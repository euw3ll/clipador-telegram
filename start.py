from configuracoes import TIPO_LOG
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
    print("🌐 Iniciando servidor do Webhook Kirvano...")
    subprocess.Popen(["python3", "start_webhook.py"])

    print("🌐 Gerando link público com ngrok...")
   # ngrok = subprocess.Popen(["ngrok", "http", "5100"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(4)  # Aguarda o ngrok subir

    try:
        r = requests.get("http://localhost:4040/api/tunnels")
        url_publica = r.json()["tunnels"][0]["public_url"]
        print(f"🔗 URL pública do webhook: {url_publica}")
    except Exception as e:
        print("❌ Não foi possível obter a URL do ngrok:", e)

try:
    validar_variaveis_ambiente()
    print("✅ Ambiente validado com sucesso.\n")

    # Inicia webhook em thread paralela
    Thread(target=iniciar_webhook).start()

    print("🚀 Iniciando Clipador!")
    iniciar_clipador(validar_variaveis=False)
except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.")
    atualizar_descricao_telegram_offline()