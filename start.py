import subprocess
import sys
import os
import json
from chat_privado.main import iniciar_chat_privado

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

if __name__ == "__main__":
    if "--limpar-estado" in sys.argv:
        limpar_estado()

    criar_estado_se_nao_existir()

    print("🚀 Iniciando o canal gratuito...")

    try:
        # Inicia o canal gratuito como subprocesso
        subprocess.Popen([sys.executable, "-m", "canal_gratuito.main"])

        # Inicia o bot do privado direto (sem asyncio.run)
        iniciar_chat_privado()

    except KeyboardInterrupt:
        print("\n🛑 Clipador encerrado.")
