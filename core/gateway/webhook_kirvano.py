import os
from flask import Flask, request, jsonify
from threading import Thread
from core.database import (
    atualizar_status_compra,
    buscar_telegram_por_email,
    ativar_usuario_por_telegram_id,
    salvar_plano_usuario,
    eh_admin,
    registrar_compra
)
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Flask(__name__)
WEBHOOK_TOKEN = "clipador2024secure"

@app.route("/webhook-kirvano", methods=["POST"])
def webhook_kirvano():
    try:
        logging.info("⚙️ Início do processamento do webhook Kirvano")
        headers_recebidos = dict(request.headers)
        logging.info(f"📩 Headers recebidos: {headers_recebidos}")
        data = request.json
        logging.info(f"📬 Webhook recebido: {data}")

        token = headers_recebidos.get("Security-Token")
        if token != WEBHOOK_TOKEN:
            logging.warning("🔒 Token inválido recebido no webhook.")
            return jsonify({"error": "unauthorized"}), 403

        sale_id = data.get("sale_id")
        data_criacao = data.get("created_at")
        metodo_pagamento = data.get("payment_method") or data.get("payment", {}).get("method")
        status = data.get("status")
        email = data.get("customer", {}).get("email") or data.get("contactEmail")

        produtos = data.get("products", [])
        nome_plano = produtos[0].get("offer_name") if produtos else "Plano desconhecido"
        offer_id = produtos[0].get("offer_id") if produtos else None

        if not email:
            logging.warning("⚠️ Nenhum e-mail recebido.")
            return jsonify({"error": "email ausente"}), 400

        logging.info(f"🔍 Procurando usuário com e-mail: {email}")
        telegram_id = buscar_telegram_por_email(email.strip().lower())
        logging.info(f"📢 Resultado da busca: {telegram_id}")
        if not telegram_id:
            logging.warning(f"⚠️ Nenhum usuário encontrado para o e-mail: {email}")
            return jsonify({"error": "usuario nao encontrado"}), 404

        if status == "APPROVED":
            logging.info(f"🔎 Verificando se {telegram_id} é admin...")
            resultado_admin = eh_admin(telegram_id)
            logging.info(f"Resultado de eh_admin: {resultado_admin}")
            if metodo_pagamento == "FREE" and not resultado_admin:
                logging.warning("❌ Acesso negado: produto gratuito disponível apenas para administradores.")
                return jsonify({"error": "produto gratuito é exclusivo para administradores"}), 403

            registrar_compra(
                telegram_id=telegram_id,
                email=email,
                plano=nome_plano,
                metodo_pagamento=metodo_pagamento,
                status=status,
                sale_id=sale_id,
                data_criacao=data_criacao,
                offer_id=offer_id
            )
            logging.info("📦 Compra registrada com sucesso.")

            ativar_usuario_por_telegram_id(telegram_id)
            logging.info("🟢 Usuário ativado com sucesso.")

            salvar_plano_usuario(telegram_id, nome_plano)
            logging.info("💾 Plano salvo com sucesso.")
            logging.info(f"✅ Usuário {telegram_id} ativado com plano: {nome_plano}")

        elif status in ["REFUNDED", "EXPIRED", "CHARGEBACK"]:
            atualizar_status_compra(sale_id, status)
            logging.warning(f"⚠️ Pagamento não válido. Status: {status}")

        logging.info("✅ Webhook finalizado com sucesso.")
        return jsonify({"ok": True}), 200

    except Exception as e:
        logging.error(f"❌ Erro ao processar webhook: {e}")
        return jsonify({"error": "erro interno", "mensagem": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return "✅ Webhook Kirvano ativo!", 200

def iniciar_webhook():
    logging.info("🚀 Iniciando servidor do Webhook Kirvano...")
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    iniciar_webhook()