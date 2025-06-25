from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest, InviteToChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest, EditChatDefaultBannedRightsRequest
from telethon.tl.types import InputChatUploadedPhoto, ChatBannedRights

# Adiciona a capacidade de carregar o arquivo .env ao executar este script diretamente
from dotenv import load_dotenv
load_dotenv()
import os

# --- Credenciais da API do Telegram (my.telegram.org) ---
API_ID = os.getenv("TELETHON_API_ID")
API_HASH = os.getenv("TELETHON_API_HASH")
if not API_ID or not API_HASH:
    raise ValueError("As variáveis de ambiente TELETHON_API_ID e TELETHON_API_HASH devem ser configuradas.")

# --- Credenciais da Conta de Serviço do Telegram ---
# Recomenda-se usar uma conta dedicada para o bot, não a sua pessoal.
SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "clipador_session")

# --- Configurações do Canal ---

# Caminho da imagem do canal
IMAGEM_PADRAO_PATH = os.path.join("images", "logo_canal.jpg")  # certifique-se que essa imagem exista

async def criar_canal_telegram(nome_usuario: str, telegram_id: int, nome_exibicao: str = None, caminho_imagem: str = None):
    """
    Cria um canal privado no Telegram, adiciona o usuário e define a foto.
    Utiliza um arquivo de sessão para evitar logins interativos repetidos.
    Na primeira execução, pode ser necessário um login interativo para criar o arquivo .session.
    """
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        # Garante que o cliente está conectado. Se o arquivo .session existir, ele será usado.
        # Se não, um login interativo será iniciado. É recomendado gerar o .session localmente uma vez.
        me = await client.get_me()
        print(f"Telethon conectado como: {me.username}")

        # Cria o canal
        canal = await client(CreateChannelRequest(
            title=nome_exibicao or f"Clipador 🎥 @{nome_usuario}",
            about="Canal gerado automaticamente pelo Clipador.",
            megagroup=False # False para criar um canal de transmissão, não um supergrupo
        ))
        canal_entidade = canal.chats[0]

        # 1. Define as permissões padrão do canal (read-only para membros)
        # Isso garante que apenas admins (o bot) possam postar.
        permissoes_padrao = ChatBannedRights(
            until_date=None,
            send_messages=True,
            send_media=True,
            send_stickers=True,
            send_gifs=True,
            send_games=True,
            send_inline=True,
            embed_links=True,
            send_polls=True,
            change_info=True,
            invite_users=True,
            pin_messages=True
        )
        await client(EditChatDefaultBannedRightsRequest(peer=canal_entidade, banned_rights=permissoes_padrao))

        # 2. Adiciona o usuário (cliente) ao canal como um membro normal
        await client(InviteToChannelRequest(
            channel=canal_entidade,
            users=[telegram_id]
        ))

        # 3. Define a imagem do canal (se existir) de forma segura
        try:
            caminho_final_imagem = caminho_imagem or IMAGEM_PADRAO_PATH
            if os.path.exists(caminho_final_imagem):
                file = await client.upload_file(caminho_final_imagem)
                await client(EditPhotoRequest(
                    channel=canal_entidade,
                    photo=InputChatUploadedPhoto(file)
                ))
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível definir a foto do canal. Verifique o arquivo '{caminho_imagem or IMAGEM_PADRAO_PATH}'. Erro: {e}")

        # 4. Gera o link de convite
        link_convite = await client(ExportChatInviteRequest(peer=canal_entidade))

        print(f"✅ Canal criado: {canal_entidade.title}")
        print(f"🆔 ID do canal: {canal_entidade.id}")
        return canal_entidade.id, link_convite.link

if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 3:
        print("Uso para teste manual: python core/telethon_criar_canal.py <username_do_usuario> <id_numerico_do_usuario>")
        print("Exemplo: python core/telethon_criar_canal.py meu_usuario 123456789")
        print("\nCertifique-se de que as variáveis de ambiente TELETHON_API_ID e TELETHON_API_HASH estão definidas.")
        print("Na primeira execução, um login interativo será necessário para criar o arquivo de sessão.")
    else:
        asyncio.run(criar_canal_telegram(sys.argv[1], int(sys.argv[2])))