import os
from flask import Flask, request, jsonify
from threading import Thread
from core.database import (
    atualizar_status_compra,
    registrar_compra,
    compra_ja_registrada,
    registrar_evento_webhook
)
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Flask(__name__)
WEBHOOK_TOKEN = "clipador2024secure"

@app.route("/webhook", methods=["POST"])
def webhook_kirvano():
    try:
        logging.info("⚙️ Início do processamento do webhook Kirvano")
        import os
        logging.info(f"📁 Banco em uso: {os.path.abspath('banco/clipador.db')}")
        logging.info(f"📂 Diretório atual: {os.getcwd()}")
        headers_recebidos = dict(request.headers)
        logging.info(f"📩 Headers recebidos: {headers_recebidos}")
        data = request.json
        if not data or not isinstance(data, dict):
            logging.warning("⚠️ Webhook vazio ou inválido.")
            return jsonify({"error": "payload inválido"}), 400
        registrar_evento_webhook(data)
        logging.info(f"📬 Webhook recebido: {data}")

        nome_completo = data.get("customer", {}).get("name")
        telefone = data.get("customer", {}).get("phone_number")

        token = headers_recebidos.get("Security-Token")
        if token != WEBHOOK_TOKEN:
            logging.warning("🔒 Token inválido recebido no webhook.")
            return jsonify({"error": "unauthorized"}), 403

        sale_id = data.get("sale_id")
        data_criacao = data.get("created_at")
        metodo_pagamento = data.get("payment_method") or data.get("payment", {}).get("method")
        status = data.get("status")
        email = data.get("customer", {}).get("email") or data.get("contactEmail")

        # Ignora se já foi registrado e não for email de teste
        email_teste = email.strip().lower() in ["wendrell.antoneli@gmail.com", "w3lldrop@gmail.com"]
        if compra_ja_registrada(sale_id) and not email_teste:
            logging.info("🛑 Compra já registrada anteriormente. Ignorando.")
            return jsonify({"ok": True, "duplicada": True}), 200

        produtos = data.get("products", [])
        # Pega a primeira oferta com nome válido
        nome_plano = next((p.get("offer_name") for p in produtos if p.get("offer_name")), "Plano desconhecido")
        offer_id = produtos[0].get("offer_id") if produtos else None

        if not email:
            logging.warning("⚠️ Nenhum e-mail recebido.")
            return jsonify({"error": "email ausente"}), 400
        
        # A única responsabilidade do webhook é registrar a compra no banco.
        # A lógica de ativação/desativação será feita pelo bot quando o usuário interagir
        # ou por um processo em segundo plano que verifica o banco.
        if status in ["APPROVED", "REFUNDED", "EXPIRED", "CHARGEBACK", "PENDING"]:
            try:
                # O telegram_id é nulo aqui porque o webhook não sabe o telegram_id do usuário.
                # Ele será vinculado depois pelo bot quando o usuário informar o e-mail.
                registrar_compra(
                    telegram_id=None, # Não temos o telegram_id neste ponto
                    email=email,
                    plano=nome_plano,
                    metodo_pagamento=metodo_pagamento,
                    status=status,
                    sale_id=sale_id,
                    data_criacao=data_criacao,
                    offer_id=offer_id,
                    nome_completo=nome_completo,
                    telefone=telefone
                )
                logging.info(f"📦 Compra com status '{status}' registrada para o e-mail {email}.")
            except Exception as e:
                logging.error(f"❌ Erro ao registrar compra no banco de dados: {e}")
                # Se o registro no DB falhar, retornamos 500 para a Kirvano saber que algo deu errado.
                return jsonify({"error": "database error", "message": str(e)}), 500

        logging.info("✅ Webhook finalizado com sucesso.")
        return jsonify({"ok": True}), 200

    except Exception as e:
        logging.error(f"❌ Erro ao processar webhook: {e}")
        return jsonify({"error": "erro interno", "mensagem": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return "✅ Webhook Kirvano ativo!", 200

def iniciar_webhook():
    port = int(os.environ.get("PORT", 5100))
    logging.getLogger('werkzeug').setLevel(logging.ERROR)  # Oculta log padrão do Flask
    logging.info("✅ Webhook Kirvano está rodando com sucesso!")
    logging.info("📡 Aguardando eventos de pagamento da Kirvano...")
    logging.info("🌍 Acesse via ngrok ou Render para testes locais")
    app.run(host="0.0.0.0", port=port)
    logging.info("🛑 Webhook finalizado.")

if __name__ == "__main__":
    iniciar_webhook()