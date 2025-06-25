from telethon import TelegramClient
from telethon.tl.functions.channels import DeleteChannelRequest, EditBannedRequest
from telethon.tl.types import ChatBannedRights
from dotenv import load_dotenv
import os

load_dotenv()

API_ID = os.getenv("TELETHON_API_ID")
API_HASH = os.getenv("TELETHON_API_HASH")
SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "clipador_session")

async def remover_usuario_do_canal(id_canal: int, telegram_id_usuario: int):
    """Remove (bane) um usuário de um canal específico."""
    if not all([API_ID, API_HASH, SESSION_NAME]):
        print("❌ Credenciais do Telethon não configuradas para gerenciamento.")
        return False

    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            print(f"Removendo usuário {telegram_id_usuario} do canal {id_canal}...")
            # A forma de remover um usuário de um canal de transmissão é "bani-lo".
            await client(EditBannedRequest(
                channel=id_canal,
                participant=telegram_id_usuario,
                banned_rights=ChatBannedRights(until_date=None, view_messages=True)
            ))
            print(f"✅ Usuário {telegram_id_usuario} removido com sucesso.")
            return True
        except Exception as e:
            print(f"❌ Erro ao remover usuário {telegram_id_usuario} do canal {id_canal}: {e}")
            return False

async def excluir_canal_telegram(id_canal: int):
    """Exclui um canal permanentemente."""
    if not all([API_ID, API_HASH, SESSION_NAME]):
        print("❌ Credenciais do Telethon não configuradas para gerenciamento.")
        return False
        
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            print(f"Excluindo canal {id_canal}...")
            await client(DeleteChannelRequest(channel=id_canal))
            print(f"✅ Canal {id_canal} excluído com sucesso.")
            return True
        except Exception as e:
            print(f"❌ Erro ao excluir canal {id_canal}: {e}")
            return False