import requests
import uuid
from core.ambiente import MERCADO_PAGO_ACCESS_TOKEN
from configuracoes import TIPO_LOG

MERCADO_PAGO_API = "https://api.mercadopago.com"

HEADERS = {
    "Authorization": f"Bearer {MERCADO_PAGO_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def consultar_pagamento(id_pagamento: int) -> str:
    url = f"{MERCADO_PAGO_API}/v1/payments/{id_pagamento}"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    print("📦 CONSULTA PAGAMENTO:", data)
    return data.get("status", "erro")

def criar_pagamento_pix(valor: float, descricao: str):
    idempotency_key = str(uuid.uuid4())

    payload = {
        "transaction_amount": valor,
        "description": descricao,
        "payment_method_id": "pix",
        "payer": {
            "email": f"{uuid.uuid4().hex[:8]}@sandbox.com"
        }
    }

    headers = {
        **HEADERS,
        "X-Idempotency-Key": idempotency_key
    }

    response = requests.post(f"{MERCADO_PAGO_API}/v1/payments", json=payload, headers=headers)
    data = response.json()

    if TIPO_LOG == "DESENVOLVEDOR":
        print("📦 RESPOSTA MP (PIX):", data)

    if "point_of_interaction" not in data or "transaction_data" not in data["point_of_interaction"]:
        raise Exception("A resposta do Mercado Pago não contém os dados do Pix (provavelmente falha na sandbox).")

    return {
        "valor": valor,
        "descricao": descricao,
        "qrcode": data["point_of_interaction"]["transaction_data"]["qr_code"],
        "imagem": data["point_of_interaction"]["transaction_data"]["qr_code_base64"],
        "id_pagamento": data["id"]
    }


def criar_pagamento_cartao(valor: float, descricao: str):
    payload = {
        "items": [
            {
                "title": descricao,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": valor
            }
        ],
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

    response = requests.post(f"{MERCADO_PAGO_API}/checkout/preferences", json=payload, headers=HEADERS)
    data = response.json()

    if TIPO_LOG == "DESENVOLVEDOR":
        print("📦 RESPOSTA MP (CARTÃO):", data)

    return data["init_point"]
