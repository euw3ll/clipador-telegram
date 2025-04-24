import requests
import uuid
from core.ambiente import KIRVANO_API_KEY

KIRVANO_API = "https://api.kirvano.com/api/v1"
HEADERS = {
    "Authorization": f"Bearer {KIRVANO_API_KEY}",
    "Content-Type": "application/json"
}


def criar_pagamento_pix(valor: float, descricao: str):
    payload = {
        "name": descricao,
        "price": valor,
        "payment_type": "pix",
        "integration": "telegram"
    }

    response = requests.post(f"{KIRVANO_API}/charges", json=payload, headers=HEADERS)
    data = response.json()

    if not data.get("success"):
        raise Exception("Erro ao gerar pagamento Pix com a Kirvano")

    return {
        "valor": valor,
        "descricao": descricao,
        "qrcode": data["charge"]["pix"]["payload"],
        "imagem": None,  # Kirvano ainda não fornece base64 da imagem
        "id_pagamento": data["charge"]["id"]
    }


def criar_pagamento_cartao(valor: float, descricao: str):
    payload = {
        "name": descricao,
        "price": valor,
        "payment_type": "credit",
        "integration": "telegram"
    }

    response = requests.post(f"{KIRVANO_API}/charges", json=payload, headers=HEADERS)
    data = response.json()

    if not data.get("success"):
        raise Exception("Erro ao gerar pagamento com cartão pela Kirvano")

    return data["charge"]["checkout_url"]


def consultar_pagamento(id_pagamento: int) -> str:
    response = requests.get(f"{KIRVANO_API}/charges/{id_pagamento}", headers=HEADERS)
    data = response.json()

    if not data.get("success"):
        return "erro"

    status = data["charge"]["status"]
    if status == "paid":
        return "approved"
    elif status == "waiting_payment":
        return "pending"
    else:
        return status
