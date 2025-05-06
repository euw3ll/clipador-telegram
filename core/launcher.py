import subprocess
import sys
import os
import json

from chat_privado.main import iniciar_chat_privado
from core.bootstrap import iniciar_ambiente

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Forçar timezone UTC corretamente
def scheduler_utc_patch(self, config=None, **kwargs):
    self._configure({'timezone': pytz.utc})

AsyncIOScheduler.configure = scheduler_utc_patch

ESTADO_PATH = "memoria/estado_bot.json"

def criar_estado_se_nao_existir():
    if not os.path.exists(ESTADO_PATH):
        os.makedirs(os.path.dirname(ESTADO_PATH), exist_ok=True)
        with open(ESTADO_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "ultima_execucao": None,
                "ultimo_envio_promocional": 0,
                "ultimo_envio_header": 0,
                "ultimo_envio_atualizacao_streamers": 0,
                "grupos_enviados": []
            }, f, ensure_ascii=False, indent=2)

def limpar_estado():
    if os.path.exists(ESTADO_PATH):
        os.remove(ESTADO_PATH)
        print("🧼 Memória anterior apagada.")

def iniciar_clipador(validar_variaveis=True):
    if validar_variaveis:
        iniciar_ambiente()

    if "--limpar-estado" in sys.argv:
        limpar_estado()

    criar_estado_se_nao_existir()

    print("📺 Iniciando o canal gratuito...")

    try:
        subprocess.Popen([sys.executable, "-m", "canal_gratuito.main"])
        iniciar_chat_privado()

    except KeyboardInterrupt:
        print("\n🛑 Clipador encerrado.")
