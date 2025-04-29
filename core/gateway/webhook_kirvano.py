import os

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook-kirvano', methods=['POST'])
def webhook_kirvano():
    data = request.json
    print("📬 Webhook recebido:", data)

    if data.get('payment_status') == 'paid':
        pagamento_id = data.get('payment_id')
        email_cliente = data.get('customer_email')
        print(f"✅ Pagamento confirmado para {email_cliente} (ID: {pagamento_id})")

    return jsonify({"ok": True}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # <- Aqui a mágica
    app.run(host='0.0.0.0', port=port)
