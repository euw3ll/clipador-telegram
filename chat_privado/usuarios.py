from core.database import (
    adicionar_usuario,
    obter_nivel_usuario as obter_nivel,
    atualizar_nivel_usuario,
    listar_usuarios
)

IDS_ADMINISTRADORES = [1527996001]  # Seu ID

def get_nivel_usuario(user_id: int, nome: str = "") -> int:
    if user_id in IDS_ADMINISTRADORES:
        return 9

    nivel = obter_nivel(user_id)
    if nivel == 1:
        adicionar_usuario(user_id, nome, nivel=1)
    return nivel