from configuracoes import TIPO_LOG
from core.bootstrap import validar_variaveis_ambiente
import os
os.environ["PYTHONWARNINGS"] = "ignore"

import warnings
warnings.filterwarnings("ignore")

from threading import Thread
from core.launcher import iniciar_clipador
from canal_gratuito.core.telegram import atualizar_descricao_telegram_offline
from core.gateway.webhook_kirvano import app as webhook_app
from flask import logging as flask_logging

def iniciar_webhook():
    import logging
    log = logging.getLogger('werkzeug')
    if TIPO_LOG != "DESENVOLVEDOR":
        log.setLevel(logging.ERROR)  # Esconde os logs do Flask
    print("🌐 Webhook Kirvano iniciado em http://0.0.0.0:5100")
    webhook_app.run(
        host="0.0.0.0",
        port=5100,
        debug=(TIPO_LOG == "DESENVOLVEDOR"),
        use_reloader=False
    )

try:
    validar_variaveis_ambiente()
    print("✅ Ambiente validado com sucesso.")
    Thread(target=iniciar_webhook, daemon=True).start()
    print("🚀 Iniciando Clipador...")
    iniciar_clipador(validar_variaveis=False)
except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.")
    atualizar_descricao_telegram_offline()