from core.database import (
    buscar_telegram_por_email,
    is_usuario_admin,
    buscar_compra_aprovada_por_email,
    registrar_log_pagamento
)

def verificar_pagamento_email(email: str, telegram_id: int) -> tuple:
    """Verifica se o e-mail está vinculado a uma compra aprovada e se o usuário pode ser ativado."""
    ja_usado = buscar_telegram_por_email(email)
    if ja_usado and ja_usado != telegram_id:
        registrar_log_pagamento({"erro": "email_duplicado", "email": email, "telegram_id": telegram_id})
        return "duplicado", None

    compra = buscar_compra_aprovada_por_email(email)
    if not compra:
        registrar_log_pagamento({"erro": "email_sem_compra", "email": email, "telegram_id": telegram_id})
        return "pendente", None

    if compra["payment_method"] == "FREE" and not is_usuario_admin(telegram_id):
        registrar_log_pagamento({"erro": "free_mas_nao_admin", "email": email, "telegram_id": telegram_id})
        return "pendente", None

    registrar_log_pagamento({
        "status": "compra_aprovada",
        "email": email,
        "telegram_id": telegram_id,
        "plano": compra["plano_assinado"]
    })
    return "approved", compra["plano_assinado"]

def verificar_pagamento_email_e_registrar(email: str, telegram_id: int):
    status, plano = verificar_pagamento_email(email, telegram_id)
    if status == "approved" and plano:
        from core.database import registrar_compra_kirvano
        registrar_compra_kirvano(email, plano)
    return status, plano