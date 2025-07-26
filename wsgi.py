import os
import sys
import logging  # <-- ETAPA 1: Dependência adicionada
from threading import Thread

# --- INÍCIO DA ETAPA 1: Configuração do Logging ---
# Configura o logger principal para garantir que todas as mensagens (incluindo as do Gunicorn e Flask)
# sejam exibidas de forma confiável no terminal do Render.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Força a saída para o stream que o Render captura
)
# --- FIM DA ETAPA 1 ---

# Garante que os módulos do projeto possam ser importados
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.bootstrap import validar_variaveis_ambiente
from core.database import inicializar_banco
from core.launcher import iniciar_clipador
from core.gateway.webhook_kirvano import app # Importa a instância 'app' do Flask
from canal_gratuito.core.telegram import atualizar_descricao_telegram_offline

# --- LÓGICA DE INICIALIZAÇÃO CENTRALIZADA ---

# Valida as variáveis de ambiente
logging.info("Validando variáveis de ambiente...")
validar_variaveis_ambiente()
logging.info("✅ Ambiente validado com sucesso.")

# Prepara o banco de dados
logging.info("🔧 Preparando o banco de dados PostgreSQL...")
inicializar_banco()
logging.info("✅ Banco de dados pronto.")

# Inicia o bot do Clipador em uma thread separada (processo de fundo)
logging.info("🚀 Iniciando o bot Clipador em segundo plano...")
bot_thread = Thread(target=iniciar_clipador, args=(False,))
bot_thread.daemon = True
bot_thread.start()

logging.info("✅ Aplicação pronta. Servidor Gunicorn assumindo o controle...")

# O Gunicorn procurará automaticamente a variável 'app' neste arquivo.
# Não é necessário chamar app.run() aqui.