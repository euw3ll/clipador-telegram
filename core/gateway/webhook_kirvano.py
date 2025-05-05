import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
import os
from flask import Flask, request, jsonify
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
    # Token não é enviado em produção pela Kirvano, então a verificação foi removida.
    sale_id = data.get("sale_id")
    data_criacao = data.get("created_at")
    metodo_pagamento = data.get("payment_method")
    print("📬 Webhook recebido:", data)

    status = data.get("status")
    email = data.get("contactEmail") or data.get("customer", {}).get("email")

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

        ativar_usuario_por_telegram_id(telegram_id)
        salvar_plano_usuario(telegram_id, nome_plano)
        print(f"✅ Usuário {telegram_id} ativado com plano: {nome_plano}")

    elif status in ["REFUNDED", "EXPIRED", "CHARGEBACK"]:
        atualizar_status_compra(sale_id, status)
        print(f"⚠️ Pagamento não válido. Status: {status}")

    return jsonify({"ok": True}), 200

@app.route("/", methods=["GET"])
def index():
    return "✅ Webhook Kirvano ativo!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)