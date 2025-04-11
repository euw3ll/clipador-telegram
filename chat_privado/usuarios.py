import json
import os

CAMINHO_USUARIOS = "memoria/usuarios.json"
IDS_ADMINISTRADORES = [123456789]  # Substitua pelos IDs reais

def carregar_usuarios():
    if not os.path.exists(CAMINHO_USUARIOS):
        salvar_usuarios({})
    with open(CAMINHO_USUARIOS, "r", encoding="utf-8") as f:
        return json.load(f)

# 🔁 Alias da função carregar_usuarios para compatibilidade
def carregar_db_usuarios():
    return carregar_usuarios()

def salvar_usuarios(dados):
    with open(CAMINHO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)

def get_nivel_usuario(user_id: int) -> int:
    if user_id in IDS_ADMINISTRADORES:
        return 9  # ADMIN
    usuarios = carregar_usuarios()
    return usuarios.get(str(user_id), 1)  # Padrão = 1

def registrar_usuario(user_id: int):
    usuarios = carregar_usuarios()
    if str(user_id) not in usuarios:
        usuarios[str(user_id)] = 1  # Nível padrão
        salvar_usuarios(usuarios)
