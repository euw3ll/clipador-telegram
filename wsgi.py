import os
import sys
from threading import Thread

# Garante que os módulos do projeto possam ser importados
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.bootstrap import validar_variaveis_ambiente
from core.database import inicializar_banco
from core.launcher import iniciar_clipador
from core.gateway.webhook_kirvano import app # Importa a instância 'app' do Flask
from canal_gratuito.core.telegram import atualizar_descricao_telegram_offline

# --- LÓGICA DE INICIALIZAÇÃO CENTRALIZADA ---

# Valida as variáveis de ambiente
validar_variaveis_ambiente()
print("✅ Ambiente validado com sucesso.\n")

# Prepara o banco de dados
print("🔧 Preparando o banco de dados PostgreSQL...")
inicializar_banco()
print("✅ Banco de dados pronto.\n")

# Inicia o bot do Clipador em uma thread separada (processo de fundo)
print("🚀 Iniciando o bot Clipador em segundo plano...")
bot_thread = Thread(target=iniciar_clipador, args=(False,))
bot_thread.daemon = True
bot_thread.start()

print("✅ Aplicação pronta. Servidor Gunicorn assumindo o controle...")

# O Gunicorn procurará automaticamente a variável 'app' neste arquivo.
# Não é necessário chamar app.run() aqui.