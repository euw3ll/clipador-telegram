import os
os.environ["PYTHONWARNINGS"] = "ignore"

import warnings
warnings.filterwarnings("ignore")

from core.launcher import iniciar_clipador
from canal_gratuito.core.telegram import atualizar_descricao_telegram_offline

try:
    iniciar_clipador()
except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.\n\n")
    atualizar_descricao_telegram_offline()
