import os
from flask import Flask, request, jsonify
from threading import Thread
from core.database import (
    atualizar_status_compra,
    buscar_telegram_por_email,
    ativar_usuario_por_telegram_id,
    salvar_plano_usuario,
    eh_admin,
    registrar_compra,
    atualizar_status_pagamento,
    compra_ja_registrada,
    registrar_evento_webhook,
    atualizar_plano_usuario,
    atualizar_telegram_id_por_email  # nova importação
)
import logging
from chat_privado.menus.menu_configurar_canal import iniciar_configuracao_via_webhook

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

        if status == "APPROVED":
            logging.info(f"🔎 Verificando se {email} é admin...")
            # Move buscar_telegram_por_email and related logic after registrar_compra
            try:
                registrar_compra(
                    telegram_id=None,
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
                logging.info("📦 Compra registrada com sucesso.")
            except Exception as e:
                logging.error(f"❌ Erro ao registrar compra: {e}")

            logging.info(f"🔍 Procurando usuário com e-mail: {email}")
            telegram_id = buscar_telegram_por_email(email.strip().lower())
            logging.info(f"📢 Resultado da busca: {telegram_id}")
            if not telegram_id:
                logging.warning(f"⚠️ Nenhum usuário encontrado para o e-mail: {email}")
                return jsonify({"ok": True, "pendente_vinculo": True}), 200
            atualizar_telegram_id_por_email(email.strip().lower(), telegram_id)

            resultado_admin = eh_admin(telegram_id)
            logging.info(f"Resultado de eh_admin: {resultado_admin}")
            if metodo_pagamento == "FREE" and not resultado_admin:
                logging.warning("❌ Acesso negado: produto gratuito disponível apenas para administradores.")
                return jsonify({"error": "produto gratuito é exclusivo para administradores"}), 403

            try:
                ativar_usuario_por_telegram_id(telegram_id)
                logging.info("🟢 Usuário ativado com sucesso.")
                iniciar_configuracao_via_webhook(telegram_id)
            except Exception as e:
                logging.error(f"❌ Erro ao ativar usuário: {e}")

            try:
                atualizar_plano_usuario(telegram_id, nome_plano)
                logging.info("🔁 Plano do usuário atualizado com sucesso.")
                atualizar_status_pagamento(telegram_id, "aprovado")
                logging.info("📌 Status de pagamento atualizado para aprovado.")
                logging.info(f"✅ Usuário {telegram_id} ativado com plano: {nome_plano}")
            except Exception as e:
                logging.error(f"❌ Erro ao salvar plano: {e}")

        elif status in ["REFUNDED", "EXPIRED", "CHARGEBACK"]:
            atualizar_status_compra(sale_id, status)
            telegram_id = buscar_telegram_por_email(email.strip().lower())
            if telegram_id:
                from core.database import desativar_usuario_por_telegram_id
                desativar_usuario_por_telegram_id(telegram_id)
                atualizar_status_pagamento(telegram_id, status.lower())
                logging.warning(f"🔻 Usuário {telegram_id} desativado devido ao status: {status}")
            logging.warning(f"⚠️ Pagamento não válido. Status: {status}")
            return jsonify({"ok": True, "status": status}), 200

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