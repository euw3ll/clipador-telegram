from core.database import (
    buscar_telegram_por_email,
    is_usuario_admin,
    buscar_compra_aprovada_por_email,
    registrar_log_pagamento # Mantido para logs
)

def verificar_status_compra_para_ativacao(email: str, telegram_id: int) -> tuple:
    """
    Verifica o status de uma compra para fins de ativação do usuário pelo bot.
    Não registra a compra, apenas consulta o banco de dados.
    """
    ja_usado = buscar_telegram_por_email(email)
    if ja_usado and ja_usado != telegram_id:
        registrar_log_pagamento(telegram_id, email, plano="desconhecido", status="email_duplicado")
        return "duplicado", None

    compra = buscar_compra_aprovada_por_email(email)
    if not compra:
        registrar_log_pagamento(telegram_id, email, plano="desconhecido", status="email_sem_compra")
        return "not_found", None # Alterado para 'not_found' para ser mais claro

    # Retorna o status da compra e o plano real encontrado no DB
    return compra["status"].lower(), compra["plano"] # Retorna o status e o plano da compra