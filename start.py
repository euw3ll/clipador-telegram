from configuracoes import TIPO_LOG
from core.bootstrap import validar_variaveis_ambiente
import os
os.environ["PYTHONWARNINGS"] = "ignore"

import warnings
warnings.filterwarnings("ignore")

from threading import Thread
from core.launcher import iniciar_clipador
from canal_gratuito.core.telegram import atualizar_descricao_telegram_offline

try:
    validar_variaveis_ambiente()
    print("✅ Ambiente validado com sucesso.\n")
    print("🚀 Iniciando Clipador...")
    iniciar_clipador(validar_variaveis=False)
except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.")
    atualizar_descricao_telegram_offline()