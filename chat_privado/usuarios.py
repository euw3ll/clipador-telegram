from typing import Optional, List, Dict, Any
import core.database as db  # Importa nosso módulo centralizado de banco de dados

def get_nivel_usuario(telegram_id: int, nome: Optional[str] = None) -> Optional[int]:
    """
    Obtém o nível do usuário. Se não existir e um nome for fornecido,
    registra como um novo usuário e retorna o nível padrão.
    """
    nivel = db.obter_nivel_usuario(telegram_id)
    
    # Se o nível for 1 (padrão) e não houver um usuário real, pode ser um novo usuário.
    # Vamos verificar se o usuário existe de fato.
    usuario_existente = db.buscar_usuario_por_id(telegram_id)

    if usuario_existente:
        return usuario_existente.get('nivel', 1)
    
    if nome:
        # Usuário não existe, vamos registrá-lo usando a função centralizada.
        registrar_usuario(telegram_id, nome)
        return 1  # Retorna o nível padrão para novos usuários.
    
    return None # Não pode registrar sem nome e o usuário não foi encontrado.


def registrar_usuario(telegram_id: int, nome: str):
    """
    Registra um novo usuário no banco de dados com valores padrão,
    utilizando a função centralizada em core.database.
    """
    db.adicionar_usuario(user_id=telegram_id, nome=nome)


def atualizar_usuario(telegram_id: int, nome: Optional[str] = None, nivel: Optional[int] = None):
    """
    Atualiza o nome e/ou nível do usuário, utilizando a nova função de suporte
    em core.database.
    """
    db.atualizar_dados_usuario(telegram_id=telegram_id, nome=nome, nivel=nivel)


def remover_usuario(telegram_id: int):
    """
    Remove um usuário e todos os seus dados associados do banco,
    utilizando a função centralizada.
    """
    db.remover_usuario_por_id(telegram_id=telegram_id)


def listar_usuarios() -> List[Dict[str, Any]]:
    """
    Lista todos os usuários do sistema para fins de administração,
    utilizando a função centralizada.
    """
    return db.listar_todos_usuarios()