from flask import Flask, request, jsonify
import os
import asyncio
from datetime import datetime, timedelta
import subprocess
import logging # <-- Adicionado

# Garante que o logger capture eventos do Gunicorn e Flask
gunicorn_logger = logging.getLogger('gunicorn.error')
app_logger = logging.getLogger(__name__)
app_logger.handlers = gunicorn_logger.handlers
app_logger.setLevel(gunicorn_logger.level)

# Adicionar o path do projeto para que os imports funcionem
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.database import desativar_assinatura_por_email, buscar_configuracao_canal, atualizar_data_expiracao, registrar_compra, sale_id_ja_registrado
from core.telethon_criar_canal import remover_usuario_do_canal
from core.ambiente import KIRVANO_TOKEN

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    """Esta rota responde com 'OK' para que o Render saiba que o serviço está online."""
    return "Clipador Webhook Service is running.", 200

def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

@app.route('/webhook/kirvano', methods=['POST'])
def kirvano_webhook():
    app_logger.info("--- NOVO EVENTO WEBHOOK RECEBIDO ---")
    app_logger.info("1. Cabeçalhos da Requisição (Headers): %s", request.headers)
    
    token_recebido = request.headers.get('X-Kirvano-Token')
    app_logger.info("2. Token Extraído do Header 'X-Kirvano-Token': %s", token_recebido)

    # 1. Validar o token de segurança
    if not KIRVANO_TOKEN or token_recebido != KIRVANO_TOKEN:
        token_esperado_seguro = f"'{KIRVANO_TOKEN[:4]}...{KIRVANO_TOKEN[-4:]}'" if KIRVANO_TOKEN and len(KIRVANO_TOKEN) > 8 else "'Configurado, mas muito curto'"
        if not KIRVANO_TOKEN:
            token_esperado_seguro = "'NÃO CONFIGURADO NO AMBIENTE'"

        app_logger.warning("--- FALHA NA VALIDAÇÃO DO TOKEN ---")
        app_logger.warning("-> Token Recebido: '%s'", token_recebido)
        app_logger.warning("-> Token Esperado: %s", token_esperado_seguro)
        app_logger.warning("------------------------------------")
        
        return jsonify({"status": "error", "message": "Token inválido"}), 403

    data = request.json
    event_type = data.get('event_type')
    email = data.get('customer', {}).get('email')
    status = data.get('status')

    if not email:
        app_logger.warning("Webhook recebido sem e-mail no payload.")
        return jsonify({"status": "error", "message": "E-mail não encontrado no payload"}), 400

    app_logger.info("Webhook VALIDADO com sucesso: Evento '%s' para o e-mail '%s'", event_type, email)

    # 2. Roteamento de Eventos
    if event_type in ['subscription.canceled', 'subscription.expired', 'purchase.refunded', 'purchase.chargeback', 'subscription.late']:
        handle_subscription_ended(email, status)

    elif event_type == 'subscription.renewed':
        plano = data.get('plan', {}).get('name', '')
        handle_subscription_renewed(email, plano)
    
    elif event_type == 'purchase.approved':
        sale_id = data.get('sale_id')
        if not sale_id:
            app_logger.warning("Webhook de compra aprovada sem 'sale_id'. Ignorando.")
            return jsonify({"status": "error", "message": "sale_id não encontrado"}), 400

        if sale_id_ja_registrado(sale_id):
            app_logger.info("Compra com sale_id %s já registrada. Ignorando webhook duplicado.", sale_id)
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
        app_logger.info("✅ Compra aprovada para %s (Plano: %s) registrada no banco de dados via webhook.", email, plano)

    else:
        app_logger.info("Evento não tratado recebido: %s", event_type)

    return jsonify({"status": "success"}), 200

def handle_subscription_ended(email, status):
    """Lida com o fim de uma assinatura (cancelada, expirada, etc.)."""
    app_logger.info("Iniciando processo de desativação para %s (Status: %s)", email, status)
    
    telegram_id = desativar_assinatura_por_email(email, novo_status=status)

    if not telegram_id:
        app_logger.warning("Usuário com e-mail %s não encontrado ou já inativo.", email)
        return

    config = buscar_configuracao_canal(telegram_id)
    if config and config.get('id_canal_telegram'):
        id_canal = int(config['id_canal_telegram'])
        run_async(remover_usuario_do_canal(id_canal, telegram_id))
    else:
        app_logger.warning("Usuário %s não possui canal configurado para remoção.", telegram_id)

def handle_subscription_renewed(email, plano):
    """Lida com a renovação de uma assinatura, estendendo a data de expiração."""
    app_logger.info("Iniciando processo de renovação para %s", email)
    
    if "Anual" in plano:
        nova_data = datetime.now() + timedelta(days=365)
    else: # Assume mensal
        nova_data = datetime.now() + timedelta(days=31)
    
    atualizar_data_expiracao(email, nova_data)
    app_logger.info("Data de expiração para %s atualizada para %s", email, nova_data.strftime('%Y-%m-%d'))

# A função iniciar_webhook não é mais necessária, pois o Gunicorn gerencia o servidor.
# Se precisar rodar localmente para testes, use o comando: flask --app core/gateway/webhook_kirvano:app run