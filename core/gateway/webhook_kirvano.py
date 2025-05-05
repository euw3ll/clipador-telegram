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

app = Flask(__name__)
WEBHOOK_TOKEN = "clipador2024secure"

@app.route("/webhook-kirvano", methods=["POST"])
def webhook_kirvano():
    headers_recebidos = dict(request.headers)
    print("📩 Headers recebidos:", headers_recebidos)
    data = request.json
    print("📬 Webhook recebido:", data)

    token = headers_recebidos.get("Security-Token")
    if token != WEBHOOK_TOKEN:
        print("🔒 Token inválido recebido no webhook.")
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
        print("⚠️ Nenhum e-mail recebido.")
        return jsonify({"error": "email ausente"}), 400

    print(f"🔍 Procurando usuário com e-mail: {email}")
    telegram_id = buscar_telegram_por_email(email.strip().lower())
    print(f"📢 Resultado da busca: {telegram_id}")
    if not telegram_id:
        print(f"⚠️ Nenhum usuário encontrado para o e-mail: {email}")
        return jsonify({"error": "usuario nao encontrado"}), 404

    if status == "APPROVED":
        if metodo_pagamento == "FREE" and not eh_admin(telegram_id):
            print(f"❌ Acesso negado: produto gratuito disponível apenas para administradores.")
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
        print("📦 Compra registrada com sucesso.")

        ativar_usuario_por_telegram_id(telegram_id)
        print("🟢 Usuário ativado com sucesso.")

        salvar_plano_usuario(telegram_id, nome_plano)
        print("💾 Plano salvo com sucesso.")
        print(f"✅ Usuário {telegram_id} ativado com plano: {nome_plano}")

    elif status in ["REFUNDED", "EXPIRED", "CHARGEBACK"]:
        atualizar_status_compra(sale_id, status)
        print(f"⚠️ Pagamento não válido. Status: {status}")

    return jsonify({"ok": True}), 200

@app.route("/", methods=["GET"])
def index():
    return "✅ Webhook Kirvano ativo!", 200

def iniciar_webhook():
    print("🚀 Iniciando servidor do Webhook Kirvano...")
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    iniciar_webhook()