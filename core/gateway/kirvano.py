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
        registrar_log_pagamento(telegram_id, email, plano="desconhecido", status="email_duplicado")
        return "duplicado", None

    compra = buscar_compra_aprovada_por_email(email)
    if not compra:
        registrar_log_pagamento(telegram_id, email, plano="desconhecido", status="email_sem_compra")
        return "pendente", None

    if compra["payment_method"].upper() == "FREE":
        if not is_usuario_admin(telegram_id):
            registrar_log_pagamento(telegram_id, email, plano="FREE", status="nao_admin")
            return "negado", None

    registrar_log_pagamento(telegram_id, email, plano=compra["plano_assinado"], status="compra_aprovada")
    return "approved", compra["plano_assinado"]

def verificar_pagamento_email_e_registrar(email: str, telegram_id: int):
    status, plano = verificar_pagamento_email(email, telegram_id)
    if status == "approved" and plano:
        from core.database import registrar_compra_kirvano
        registrar_compra_kirvano(email=email, plano=plano, telegram_id=telegram_id)
    return status, plano