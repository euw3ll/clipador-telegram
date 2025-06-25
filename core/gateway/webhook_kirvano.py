from flask import Flask, request, jsonify
import os
import asyncio
from datetime import datetime, timedelta

# Adicionar o path do projeto para que os imports funcionem
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.database import desativar_assinatura_por_email, buscar_configuracao_canal, atualizar_data_expiracao
from core.telethon_gerenciar_canal import remover_usuario_do_canal
from core.ambiente import KIRVANO_TOKEN

app = Flask(__name__)

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
    if event_type in ['subscription.canceled', 'subscription.expired', 'purchase.refunded', 'purchase.chargeback']:
        handle_subscription_ended(email, status)

    elif event_type == 'subscription.renewed':
        plano = data.get('plan', {}).get('name', '')
        handle_subscription_renewed(email, plano)
    
    elif event_type == 'purchase.approved':
        print(f"INFO: Compra aprovada para {email} registrada via webhook (ação tratada no bot).")

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
    app.run(host='0.0.0.0', port=5100)