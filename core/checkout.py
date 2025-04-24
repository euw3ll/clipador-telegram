import requests
import uuid
from core.ambiente import MERCADO_PAGO_ACCESS_TOKEN

MERCADO_PAGO_API = "https://api.mercadopago.com"

HEADERS = {
    "Authorization": f"Bearer {MERCADO_PAGO_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def gerar_pagamento_pix(valor: float, descricao: str):
    payload = {
        "transaction_amount": valor,
        "description": descricao,
        "payment_method_id": "pix",
        "payer": {
            "email": f"{uuid.uuid4().hex[:8]}@sandbox.com"
        }
    }

    response = requests.post(f"{MERCADO_PAGO_API}/v1/payments", json=payload, headers=HEADERS)
    response.raise_for_status()

    data = response.json()
    return {
        "valor": valor,
        "descricao": descricao,
        "qrcode": data["point_of_interaction"]["transaction_data"]["qr_code"],
        "imagem": data["point_of_interaction"]["transaction_data"]["qr_code_base64"],
        "id_pagamento": data["id"]
    }

def gerar_link_pagamento_cartao(valor: float, descricao: str):
    payload = {
        "title": descricao,
        "quantity": 1,
        "currency_id": "BRL",
        "unit_price": valor
    }

    body = {
        "items": [payload],
        "payment_methods": {
            "excluded_payment_types": [{"id": "pix"}]
        },
        "back_urls": {
            "success": "https://clipador.com.br/sucesso",
            "failure": "https://clipador.com.br/erro",
            "pending": "https://clipador.com.br/pendente"
        },
        "auto_return": "approved"
    }

    response = requests.post(f"{MERCADO_PAGO_API}/checkout/preferences", json=body, headers=HEADERS)
    response.raise_for_status()

    return response.json()["init_point"]
