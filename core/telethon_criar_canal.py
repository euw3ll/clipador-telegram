import asyncio
import logging
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest, InviteToChannelRequest, EditAdminRequest, DeleteChannelRequest, GetFullChannelRequest, EditBannedRequest
from telethon.tl.functions.messages import ExportChatInviteRequest # Import ChatAdminRights
from telethon.tl.types import InputChatUploadedPhoto, ChatBannedRights, User, ChatAdminRights # Import User here
from telethon.errors import ChannelPrivateError, FloodWaitError, UserBotError, UserNotMutualContactError, UserBlockedError, UserPrivacyRestrictedError, PeerFloodError # Import specific errors

# Adiciona a capacidade de carregar o arquivo .env ao executar este script diretamente
from dotenv import load_dotenv
load_dotenv()
import os

logger = logging.getLogger(__name__)


# --- Credenciais da API do Telegram (my.telegram.org) ---
API_ID = os.getenv("TELETHON_API_ID")
API_HASH = os.getenv("TELETHON_API_HASH")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME") # Novo: Username do bot Telegram
if not API_ID or not API_HASH:
    raise ValueError("As variáveis de ambiente TELETHON_API_ID e TELETHON_API_HASH devem ser configuradas.")

# --- Credenciais da Conta de Serviço do Telegram ---
# Recomenda-se usar uma conta dedicada para o bot, não a sua pessoal.
SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "clipador_session")

# --- Configurações do Canal ---

# Caminho da imagem do canal
IMAGEM_PADRAO_PATH = os.path.join("images", "logo_canal.jpg")  # certifique-se que essa imagem exista

async def criar_canal_telegram(nome_exibicao: str, telegram_id: int, caminho_imagem: str = None):
    """
    Cria um canal privado no Telegram, adiciona o usuário e define a foto.
    Utiliza um arquivo de sessão para evitar logins interativos repetidos.
    Na primeira execução, pode ser necessário um login interativo para criar o arquivo .session.
    """
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        # Garante que o cliente está conectado. Se o arquivo .session existir, ele será usado.
        # Se não, um login interativo será iniciado. É recomendado gerar o .session localmente uma vez.
        me = await client.get_me()
        logger.info(f"Telethon conectado como: {me.username}")

        # Cria o canal
        logger.info(f"Telethon: Criando canal para {nome_exibicao} (ID: {telegram_id})...")
        canal = await client(CreateChannelRequest(
            title=f"Clipador 🎥 {nome_exibicao}", # Usa o nome de exibição diretamente
            about=f"⚙️ Gerencie seu canal em {TELEGRAM_BOT_USERNAME}\n\nQue a caça aos clipes comece! 🏹",
            megagroup=False # False para criar um canal de transmissão, não um supergrupo
        ))
        canal_entidade = canal.chats[0]
        logger.info(f"Telethon: Canal '{canal_entidade.title}' (ID: {canal_entidade.id}) criado.")

        # Adiciona uma pequena pausa para garantir que o canal seja totalmente inicializado
        await asyncio.sleep(0.5)

        # 1. Adiciona o bot do Telegram como administrador
        if TELEGRAM_BOT_USERNAME:
            try:
                bot_entity = await client.get_entity(TELEGRAM_BOT_USERNAME)
                if isinstance(bot_entity, User) and bot_entity.bot:
                    # Direitos mínimos para o bot poder postar e gerenciar o canal
                    bot_admin_rights = ChatAdminRights(post_messages=True, edit_messages=True, delete_messages=True, change_info=True, invite_users=True, pin_messages=True)
                    
                    # Tenta promover o bot a administrador diretamente.
                    # Isso deve adicionar o bot ao canal se ele ainda não for membro.
                    logger.info(f"Telethon: Promovendo bot @{TELEGRAM_BOT_USERNAME} a administrador do canal {canal_entidade.id}...")
                    await client(EditAdminRequest(channel=canal_entidade, user_id=bot_entity, admin_rights=bot_admin_rights, rank="ClipadorBot"))
                    logger.info(f"✅ Bot @{TELEGRAM_BOT_USERNAME} promovido a administrador do canal.")
                else:
                    logger.warning(f"⚠️ Aviso: Entidade '{TELEGRAM_BOT_USERNAME}' não é um bot válido. Não foi adicionado como admin.")
            except Exception as e:
                logger.error(f"❌ Erro ao adicionar o bot como administrador: {e}", exc_info=True)
                raise # Re-lança a exceção para que o fluxo principal saiba que falhou.
        else:
            logger.warning("⚠️ Aviso: Variável de ambiente TELEGRAM_BOT_USERNAME não configurada. O bot não será adicionado como administrador do canal.")

        # 2. Define a imagem do canal (personalizada ou padrão)
        try:
            caminho_final_imagem = caminho_imagem or IMAGEM_PADRAO_PATH
            if os.path.exists(caminho_final_imagem):
                logger.info(f"Telethon: Definindo imagem de perfil do canal {canal_entidade.id} com '{caminho_final_imagem}'...")
                uploaded_photo = await client.upload_file(caminho_final_imagem)
                await client(EditPhotoRequest(
                    channel=canal_entidade,
                    photo=InputChatUploadedPhoto(uploaded_photo)
                ))
                logger.info(f"✅ Imagem de perfil definida para o canal {canal_entidade.id}.")
            else:
                logger.warning(f"⚠️ Aviso: Imagem não encontrada em {caminho_final_imagem}. Canal criado sem imagem de perfil.")
        except Exception as e:
            logger.error(f"⚠️ Aviso: Não foi possível definir a foto do canal. Erro: {e}", exc_info=True)
            # Não interrompe o fluxo, continua mesmo que a foto falhe

        # 3. Adiciona o usuário (cliente) ao canal
        try:
            logger.info(f"Telethon: Adicionando usuário {telegram_id} ao canal {canal_entidade.id}...")
            await client(InviteToChannelRequest(
                channel=canal_entidade,
                users=[telegram_id]
            ))
            logger.info(f"✅ Usuário {telegram_id} adicionado ao canal.")
        except (UserPrivacyRestrictedError, UserNotMutualContactError, ValueError) as e:
            logger.warning(f"⚠️ Não foi possível adicionar {telegram_id} diretamente ao canal devido às suas configurações de privacidade: {e}. Um link de convite será usado como alternativa.")
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar usuário {telegram_id} ao canal: {e}", exc_info=True)

        # 4. Gera o link de convite (essencial como fallback e para o botão final)
        logger.info(f"Telethon: Gerando link de convite para o canal {canal_entidade.id}...")
        link_convite = await client(ExportChatInviteRequest(peer=canal_entidade))
        logger.info(f"✅ Link de convite gerado: {link_convite.link}")

        # O ID do canal para a API de Bot deve ser o ID base (positivo) prefixado com -100.
        id_canal_bot_api = int(f"-100{canal_entidade.id}")
        logger.info(f"✅ Canal criado: {canal_entidade.title} | ID Base: {canal_entidade.id} | ID para Bot API: {id_canal_bot_api}")
        return id_canal_bot_api, link_convite.link

async def adicionar_usuario_ao_canal(id_canal: int, id_usuario_alvo: int):
    """Adiciona um usuário a um canal específico."""
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            logger.info(f"Telethon: Adicionando usuário {id_usuario_alvo} ao canal {id_canal}...")
            await client(InviteToChannelRequest(
                channel=id_canal,
                users=[id_usuario_alvo]
            ))
            logger.info(f"✅ Usuário {id_usuario_alvo} adicionado ao canal {id_canal}.")
            return True, "Usuário adicionado com sucesso."
        except (UserPrivacyRestrictedError, UserNotMutualContactError):
            logger.warning(f"Não foi possível adicionar {id_usuario_alvo} ao canal {id_canal} devido às configurações de privacidade do usuário.")
            return False, "Não foi possível adicionar o usuário devido às suas configurações de privacidade."
        except Exception as e:
            logger.error(f"Erro inesperado ao adicionar usuário {id_usuario_alvo} ao canal {id_canal}: {e}", exc_info=True)
            return False, f"Erro inesperado: {e}"


async def remover_usuario_do_canal(id_canal: int, id_usuario_alvo: int):
    """Remove (bane/kicka) um usuário de um canal específico."""
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            logger.info(f"Telethon: Removendo usuário {id_usuario_alvo} do canal {id_canal}...")
            # Para remover, "banimos" o usuário com o direito de ver mensagens revogado.
            await client(EditBannedRequest(
                channel=id_canal,
                participant=id_usuario_alvo,
                banned_rights=ChatBannedRights(until_date=None, view_messages=True)
            ))
            logger.info(f"✅ Usuário {id_usuario_alvo} removido do canal {id_canal}.")
            return True, "Usuário removido com sucesso."
        except Exception as e:
            logger.error(f"Erro inesperado ao remover usuário {id_usuario_alvo} do canal {id_canal}: {e}", exc_info=True)
            return False, f"Erro inesperado: {e}"

async def deletar_canal_telegram(id_canal: int):
    """Deleta um canal do Telegram usando o Telethon."""
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            logger.info(f"Tentando deletar o canal com ID: {id_canal}")
            await client(DeleteChannelRequest(channel=id_canal))
            logger.info(f"Canal {id_canal} deletado com sucesso.")
            return True
        except ChannelPrivateError:
            logger.warning(f"Não foi possível deletar o canal {id_canal}: o bot não é admin ou o canal é privado.")
            return False
        except FloodWaitError as e:
            logger.error(f"Flood wait error ao tentar deletar canal {id_canal}. Aguardando {e.seconds} segundos.")
            await asyncio.sleep(e.seconds)
            return await deletar_canal_telegram(id_canal) # Tenta novamente
        except Exception as e:
            logger.error(f"Erro inesperado ao deletar o canal {id_canal}: {e}", exc_info=True)
            return False

async def obter_detalhes_canal(id_canal: int):
    """Obtém detalhes de um canal, como número de participantes."""
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            full_channel = await client(GetFullChannelRequest(channel=id_canal))
            return {
                "participants_count": full_channel.full_chat.participants_count,
                "about": full_channel.full_chat.about
            }
        except (ValueError, TypeError): # Handle cases where channel ID is invalid before request
            logger.error(f"ID do canal inválido fornecido: {id_canal}")
            return None
        except Exception as e:
            logger.error(f"Erro ao obter detalhes do canal {id_canal}: {e}", exc_info=True)
            return None

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