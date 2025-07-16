from flask import Flask, request, jsonify
import os
import asyncio
from datetime import datetime, timedelta
import subprocess # Importa o módulo subprocess

# Adicionar o path do projeto para que os imports funcionem
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.database import desativar_assinatura_por_email, buscar_configuracao_canal, atualizar_data_expiracao, registrar_compra, sale_id_ja_registrado
from core.telethon_criar_canal import remover_usuario_do_canal
from core.ambiente import KIRVANO_TOKEN

app = Flask(__name__)

# Função para iniciar o ngrok (movida para fora do bloco main)
def iniciar_ngrok():
    try:
        # Inicia o ngrok em segundo plano.  Adapte o caminho conforme necessário.
        process = subprocess.Popen(['ngrok', 'http', '5100'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Imprime os logs do ngrok para fins de depuração (opcional)
        # for line in process.stdout:
        #     print(line.decode('utf-8').strip())
        # for line in process.stderr:
        #     print(line.decode('utf-8').strip())
        print("ngrok iniciado em background.")
        return process
    except FileNotFoundError:
        print("Erro: ngrok não encontrado. Verifique se está instalado e no PATH.")
        return None
    except Exception as e:
        print(f"Erro ao iniciar ngrok: {e}")
        return None

# Função para rodar corrotinas a partir de um contexto síncrono (Flask)
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

@app.route('/webhook/kirvano', methods=['POST'])
def kirvano_webhook():
    # 1. Validar o token de segurança
    token_recebido = request.headers.get('X-Kirvano-Token')
    if not KIRVANO_TOKEN or token_recebido != KIRVANO_TOKEN:
        print(f"⚠️ Tentativa de acesso ao webhook com token inválido. Recebido: {token_recebido}")
        return jsonify({"status": "error", "message": "Token inválido"}), 403

    data = request.json
    event_type = data.get('event_type')
    email = data.get('customer', {}).get('email')
    status = data.get('status')

    if not email:
        return jsonify({"status": "error", "message": "E-mail não encontrado no payload"}), 400

    print(f"🔔 Webhook recebido: {event_type} para o e-mail {email}")

    # 2. Roteamento de Eventos
    if event_type in ['subscription.canceled', 'subscription.expired', 'purchase.refunded', 'purchase.chargeback', 'subscription.late']:
        handle_subscription_ended(email, status)

    elif event_type == 'subscription.renewed':
        plano = data.get('plan', {}).get('name', '')
        handle_subscription_renewed(email, plano)
    
    elif event_type == 'purchase.approved':
        sale_id = data.get('sale_id')
        if not sale_id:
            print("⚠️ Webhook de compra aprovada sem 'sale_id'. Ignorando.")
            return jsonify({"status": "error", "message": "sale_id não encontrado"}), 400

        if sale_id_ja_registrado(sale_id):
            print(f"INFO: Compra com sale_id {sale_id} já registrada. Ignorando webhook duplicado.")
            return jsonify({"status": "success", "message": "duplicado"}), 200

        # Extraindo dados do payload
        produto = data.get('products', [{}])[0]
        plano = produto.get('offer_name', 'Plano Desconhecido')
        metodo_pagamento = data.get('payment', {}).get('method')
        data_criacao = data.get('created_at')
        offer_id = produto.get('offer_id')
        nome_completo = data.get('customer', {}).get('name')
        telefone = data.get('customer', {}).get('phone_number')

        # O telegram_id é None aqui, pois será vinculado pelo bot depois
        registrar_compra(None, email, plano, metodo_pagamento, status, sale_id, data_criacao, offer_id, nome_completo, telefone)
        print(f"✅ Compra aprovada para {email} (Plano: {plano}) registrada no banco de dados via webhook.")


    else:
        print(f"INFO: Evento não tratado recebido: {event_type}")

    return jsonify({"status": "success"}), 200

def handle_subscription_ended(email, status):
    """Lida com o fim de uma assinatura (cancelada, expirada, etc.)."""
    print(f"Iniciando processo de desativação para {email} (Status: {status})")
    
    telegram_id = desativar_assinatura_por_email(email, novo_status=status)

    if not telegram_id:
        print(f"Usuário com e-mail {email} não encontrado ou já inativo.")
        return

    config = buscar_configuracao_canal(telegram_id)
    if config and config.get('id_canal_telegram'):
        id_canal = int(config['id_canal_telegram'])
        run_async(remover_usuario_do_canal(id_canal, telegram_id))
    else:
        print(f"Usuário {telegram_id} não possui canal configurado para remoção.")

def handle_subscription_renewed(email, plano):
    """Lida com a renovação de uma assinatura, estendendo a data de expiração."""
    print(f"Iniciando processo de renovação para {email}")
    
    if "Anual" in plano:
        nova_data = datetime.now() + timedelta(days=365)
    else: # Assume mensal
        nova_data = datetime.now() + timedelta(days=31) # 31 para dar uma margem
    
    atualizar_data_expiracao(email, nova_data)
    print(f"Data de expiração para {email} atualizada para {nova_data.strftime('%Y-%m-%d')}")

def iniciar_webhook():
    # Verifica a variável de ambiente antes de iniciar o ngrok
    from configuracoes import ENABLE_NGROK

    if ENABLE_NGROK:
        ngrok_process = iniciar_ngrok()
    else:
        print("ngrok desativado pela variável de ambiente.")
        ngrok_process = None

    app.run(host='0.0.0.0', port=5100, debug=True, use_reloader=False) # Adicionado debug e reloader para evitar multiplas instancias
    if ngrok_process:
        ngrok_process.terminate()