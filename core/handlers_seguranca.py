import logging
import os
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError, BadRequest
from telegram.helpers import escape_markdown

from core.database import buscar_configuracao_canal, limpar_caminho_imagem_perfil, buscar_dono_do_canal

logger = logging.getLogger(__name__)

async def verificar_novo_membro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para verificar novos membros em canais de clientes.
    Remove qualquer usuário que não seja o dono do canal.
    """
    if not update.chat_member:
        return

    chat_id = update.chat_member.chat.id
    novo_membro = update.chat_member.new_chat_member

    # Ignora se não for um novo membro entrando (ex: promoção a admin, etc.)
    if novo_membro.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.OWNER]:
        return

    id_usuario_novo = novo_membro.user.id

    try:
        id_dono_canal = buscar_dono_do_canal(chat_id)

        # Se o canal não for um canal de cliente registrado, não faz nada.
        if id_dono_canal is None:
            return

        # Se o novo membro não for o dono do canal, remove-o.
        if id_usuario_novo != id_dono_canal:
            logger.info(f"Usuário intruso (ID: {id_usuario_novo}) tentou entrar no canal {chat_id} do dono {id_dono_canal}. Removendo...")
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=id_usuario_novo)
            await context.bot.unban_chat_member(chat_id=chat_id, user_id=id_usuario_novo) # Desbane para permitir futuras tentativas com link válido
            logger.info(f"Usuário {id_usuario_novo} removido e desbanido do canal {chat_id}.")
        
        # Se o novo membro for o dono, customiza o canal.
        elif id_usuario_novo == id_dono_canal:
            logger.info(f"Dono do canal (ID: {id_dono_canal}) entrou no canal {chat_id}. Iniciando customização...")
            
            config = buscar_configuracao_canal(id_dono_canal)
            if not config:
                logger.warning(f"Não foi possível encontrar a configuração para o dono {id_dono_canal} ao customizar o canal {chat_id}.")
                return

            # A customização só roda uma vez, verificando se o caminho da imagem existe no DB.
            caminho_imagem_perfil = config.get('caminho_imagem_perfil')
            if not caminho_imagem_perfil:
                logger.info(f"Customização para o canal {chat_id} já foi realizada ou não é necessária. Pulando.")
                return

            nome_exibicao = novo_membro.user.username or novo_membro.user.first_name
            # Escapa o nome para evitar erros de formatação no Markdown
            nome_exibicao_escaped = escape_markdown(nome_exibicao)

            try:
                # 1. Customizar Título e Foto
                await context.bot.set_chat_title(chat_id=chat_id, title=f"Clipador 🎥 @{nome_exibicao}")
                if caminho_imagem_perfil and os.path.exists(caminho_imagem_perfil):
                    with open(caminho_imagem_perfil, 'rb') as photo_file:
                        await context.bot.set_chat_photo(chat_id=chat_id, photo=photo_file)
                
                # 2. Enviar Mensagem de Boas-Vindas
                streamers = [s.strip() for s in config.get('streamers_monitorados', '').split(',') if s.strip()]
                num_streamers = len(streamers)
                slots_ativos = config.get('slots_ativos', 1)
                modo = config.get('modo_monitoramento', 'N/A')
                streamers_str = "\n".join([f"• `{escape_markdown(s)}`" for s in streamers]) if streamers else "Nenhum streamer configurado."

                welcome_message_parts = [
                    f"🎉 Bem-vindo(a) ao seu canal Clipador, @{nome_exibicao_escaped}!\n",
                    "Sua configuração inicial está pronta para começar a clipar os melhores momentos. 🚀\n",
                    "*" + ("-" * 25) + "*",
                    "📋 *Resumo da sua Configuração:*",
                    f"📺 *Streamers Monitorados ({num_streamers}/{slots_ativos}):*",
                    streamers_str,
                    f"🧠 *Modo de Monitoramento:* `{escape_markdown(modo)}`",
                    "*" + ("-" * 25) + "*\n"
                ]
                await context.bot.send_message(chat_id=chat_id, text="\n".join(welcome_message_parts), parse_mode="Markdown")

                # 3. Limpeza
                if caminho_imagem_perfil and os.path.exists(caminho_imagem_perfil):
                    os.remove(caminho_imagem_perfil)
                limpar_caminho_imagem_perfil(id_dono_canal)
                logger.info(f"Customização do canal {chat_id} para o dono {id_dono_canal} concluída com sucesso.")

            except BadRequest as e:
                logger.error(f"Erro de BadRequest (provavelmente Markdown) ao customizar o canal {chat_id}: {e}")
            except TelegramError as e: # Captura outras exceções do Telegram
                logger.error(f"Erro de Telegram ao customizar o canal {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Erro inesperado ao customizar o canal {chat_id}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Erro ao verificar novo membro no canal {chat_id}: {e}", exc_info=True)