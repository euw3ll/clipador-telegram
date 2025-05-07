from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest, EditAdminRequest, InviteToChannelRequest
from telethon.tl.types import InputChatUploadedPhoto, ChatAdminRights
import os

# Essas variáveis devem vir de https://my.telegram.org
API_ID = os.getenv("TELETHON_API_ID") or 123456  # substitua pelo seu real
API_HASH = os.getenv("TELETHON_API_HASH") or "abc123..."  # substitua pelo seu real

SESSION_NAME = "clipador_session"  # será salvo localmente

# Caminho da imagem do canal
IMAGEM_PATH = os.path.join("imagens", "logo_canal.jpg")  # certifique-se que essa imagem exista

async def criar_canal_telegram(nome_usuario: str, nome_exibicao: str = None):
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        # Cria o canal
        canal = await client(CreateChannelRequest(
            title=nome_exibicao or f"Clipador 🎥 @{nome_usuario}",
            about="Canal gerado automaticamente pelo Clipador.",
            megagroup=False
        ))
        canal_entidade = canal.chats[0]

        # Define a imagem do canal (se existir)
        if os.path.exists(IMAGEM_PATH):
            file = await client.upload_file(IMAGEM_PATH)
            await client(EditPhotoRequest(
                channel=canal_entidade,
                photo=InputChatUploadedPhoto(file)
            ))

        print(f"✅ Canal criado: {canal_entidade.title}")
        print(f"🆔 ID do canal: {canal_entidade.id}")
        return canal_entidade.id

if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Uso: python telethon_criar_canal.py nome_usuario")
    else:
        asyncio.run(criar_canal_telegram(sys.argv[1]))