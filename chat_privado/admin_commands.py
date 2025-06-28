import logging
import asyncio
from telegram import Update, error as telegram_error
from telegram.ext import ContextTypes
from typing import Optional

from core.database import (
    is_usuario_admin,
    resetar_estado_usuario_para_teste,
    buscar_configuracao_canal,
    deletar_configuracao_canal,
    marcar_configuracao_completa,
    buscar_usuario_por_id,
    buscar_usuario_por_email,
    conceder_plano_usuario,
    adicionar_slot_extra,
    remover_slots_extras,
    buscar_ids_assinantes_ativos,
    obter_estatisticas_gerais,
    atualizar_streamers_monitorados,
)
from core.telethon_criar_canal import (
    deletar_canal_telegram,
    obter_detalhes_canal,
    adicionar_usuario_ao_canal,
    remover_usuario_do_canal
)
from configuracoes import TELEGRAM_CHAT_ID
from datetime import datetime

logger = logging.getLogger(__name__)

def _parse_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Extrai o user_id dos argumentos do comando."""
    if not context.args:
        update.message.reply_text("❌ Por favor, forneça o ID do usuário. Ex: /comando 123456789 ou /comando me")
        return None
    
    identifier = context.args[0]
    if identifier.lower() == 'me':
        return update.effective_user.id

    try:
        return int(identifier)
    except (ValueError, IndexError):
        update.message.reply_text("❌ ID de usuário inválido.")
        return None

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o menu de ajuda para administradores."""
    if not is_usuario_admin(update.effective_user.id):
        return
    
    texto = (
        "🛠️ *Painel de Administrador*\n\n"
        "📊 *Estatísticas e Comunicação*\n"
        "`/stats` - Vê as estatísticas gerais do bot.\n"
        "`/channelstats <id | me | gratuito>` - Vê stats de um canal.\n"
        "`/broadcast <mensagem>` - Envia mensagem para todos.\n"
        "`/message <id | me> <mensagem>` - Envia msg privada.\n\n"
        "👤 *Gerenciamento de Usuários*\n"
        "`/userinfo <id | me | email>` - Vê resumo do usuário.\n"
        "`/setplan <id | me> <Plano> [dias]` - Define um plano.\n"
        "_(Planos: Mensal Solo, Mensal Plus, Anual Pro, SUPER, PARCEIRO)_\n"
        "`/addslot <id | me> [quantidade]` - Adiciona um ou mais slots extras.\n"
        "`/removeslots <id | me>` - Remove todos os slots extras.\n"
        "`/resetuser <id | me>` - Apaga TODOS os dados do usuário.\n\n"
        "📺 *Gerenciamento de Canais*\n"
        "`/setstreamers <id | me> <s1>...` - Altera a lista de streamers.\n"
        "`/createchannel <id | me>` - Verifica se um usuário pode criar um canal.\n"
        "`/delchannel <id | me>` - Apaga o canal de um usuário e reseta a config.\n"
        "`/channelmembers <add|remove> <owner_id|me> <target_id|me>` - Gerencia membros.\n"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def reset_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reseta completamente um usuário para testes."""
    if not is_usuario_admin(update.effective_user.id):
        return
    
    user_id = _parse_user_id(update, context)
    if not user_id:
        return

    await update.message.reply_text(f"⚠️ ATENÇÃO: Isso apagará TODOS os dados do usuário `{user_id}`. Aguarde...")
    try:
        await resetar_estado_usuario_para_teste(user_id)
        await update.message.reply_text(f"✅ Usuário `{user_id}` resetado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao resetar usuário {user_id}: {e}")
        await update.message.reply_text(f"❌ Erro ao resetar usuário: {e}")

async def create_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica se um usuário pode criar um canal."""
    if not is_usuario_admin(update.effective_user.id):
        return

    user_id = _parse_user_id(update, context)
    if not user_id:
        return

    # 1. Verificar se o usuário tem plano ativo
    usuario = buscar_usuario_por_id(user_id)
    if not usuario or usuario.get('nivel') != 2:
        await update.message.reply_text(f"❌ Não é possível criar o canal. O usuário `{user_id}` não é um assinante ativo.")
        return

    # 2. Verificar se já não existe um canal
    config = buscar_configuracao_canal(user_id)
    if config and config.get('id_canal_telegram'):
        await update.message.reply_text(f"❌ O usuário `{user_id}` já possui um canal configurado.")
        return

    await update.message.reply_text(
        f"✅ Verificação bem-sucedida. O usuário `{user_id}` é um assinante ativo e não possui um canal.\n\n"
        "Peça para que ele use o comando /start para iniciar a configuração."
    )

async def delete_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apaga o canal de um usuário e reseta seu status de configuração."""
    if not is_usuario_admin(update.effective_user.id):
        return

    user_id = _parse_user_id(update, context)
    if not user_id:
        return

    await update.message.reply_text(f"⏳ Apagando canal e resetando configuração para o usuário `{user_id}`. Aguarde...")

    try:
        config = buscar_configuracao_canal(user_id)
        if config and config.get('id_canal_telegram'):
            id_canal = int(config['id_canal_telegram'])
            await deletar_canal_telegram(id_canal)
            logger.info(f"Canal {id_canal} do usuário {user_id} deletado via admin.")
        
        # Reseta o estado de configuração no banco de dados
        deletar_configuracao_canal(user_id)
        marcar_configuracao_completa(user_id, False)

        await update.message.reply_text(f"✅ Canal do usuário `{user_id}` removido e configuração resetada. Ele pode usar /start para configurar novamente.")

    except Exception as e:
        logger.error(f"Erro ao deletar canal para o usuário {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao deletar o canal: {e}")

async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe um resumo completo dos dados de um usuário."""
    if not is_usuario_admin(update.effective_user.id): return

    if not context.args:
        await update.message.reply_text("❌ Uso: `/userinfo <id | email>`")
        return

    identifier = context.args[0]
    usuario = None
    user_id = None

    if identifier.isdigit():
        user_id = int(identifier)
        usuario = buscar_usuario_por_id(user_id)
    else:
        usuario = buscar_usuario_por_email(identifier)
        if usuario:
            user_id = usuario['telegram_id']

    if not usuario:
        await update.message.reply_text(f"❌ Usuário com identificador `{identifier}` não encontrado em nosso banco de dados.")
        return

    config = buscar_configuracao_canal(user_id)

    info = [f"ℹ️ *Informações do Usuário: `{user_id}`*"]
    info.append(f"👤 *Nome:* {usuario.get('nome', 'N/A')}")
    info.append(f"📧 *Email:* `{usuario.get('email', 'N/A')}`")
    info.append(f"📦 *Plano:* {usuario.get('plano_assinado', 'Nenhum')}")
    
    data_exp_str = usuario.get('data_expiracao')
    data_exp_fmt = datetime.fromisoformat(data_exp_str).strftime('%d/%m/%Y %H:%M') if data_exp_str else "N/A"
    info.append(f"🗓️ *Expira em:* {data_exp_fmt}")

    if config:
        id_canal = config.get('id_canal_telegram')
        info.append(f"📺 *Canal:* {'Criado (`' + str(id_canal) + '`)' if id_canal else 'Não criado'}")
        info.append("\n*--- Configuração do Canal ---*")
        info.append(f"🧠 *Modo:* `{config.get('modo_monitoramento', 'N/A')}`")
        streamers = [s for s in config.get('streamers_monitorados', '').split(',') if s]
        num_streamers = len(streamers)
        info.append(f"🎰 *Slots:* {num_streamers}/{config.get('slots_ativos', 'N/A')}")
        info.append(f"📡 *Streamers:* `{' | '.join(streamers) if streamers else 'Nenhum'}`")
        if config.get('modo_monitoramento') == 'MANUAL':
            info.append(f"  - *Mín. Clipes:* `{config.get('manual_min_clips', 'N/A')}`")
            info.append(f"  - *Intervalo:* `{config.get('manual_interval_sec', 'N/A')}`s")
    else:
        info.append("📺 *Canal:* Não criado")

    await update.message.reply_text("\n".join(info), parse_mode="Markdown")

async def set_plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Define ou concede um plano de assinatura a um usuário."""
    if not is_usuario_admin(update.effective_user.id): return

    if len(context.args) < 2:
        await update.message.reply_text("❌ Uso: `/setplan <user_id> <Nome do Plano> [dias]`\nEx: `/setplan 123 Mensal Solo 30`")
        return
    
    try:
        user_id = int(context.args[0])
        # Verifica se o último argumento é um número (dias)
        if context.args[-1].isdigit() and len(context.args) > 2:
            days = int(context.args[-1])
            plan_name = " ".join(context.args[1:-1])
        else: # Se não, assume dias padrão e o resto é o nome do plano
            days = 31
            plan_name = " ".join(context.args[1:])
        
        if not plan_name:
             await update.message.reply_text("❌ Nome do plano não fornecido.")
             return

        # Verifica se o usuário existe
        if not buscar_usuario_por_id(user_id):
            await update.message.reply_text(f"❌ Usuário com ID `{user_id}` não encontrado. Peça para ele dar /start primeiro.")
            return

        conceder_plano_usuario(user_id, plan_name, days)
        await update.message.reply_text(f"✅ Plano *{plan_name}* concedido ao usuário `{user_id}` por *{days} dias*.")

    except ValueError:
        await update.message.reply_text("❌ ID de usuário ou número de dias inválido.")
    except Exception as e:
        logger.error(f"Erro ao conceder plano para {context.args[0]}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao conceder plano: {e}")

async def add_slot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona um ou mais slots extras para um usuário."""
    if not is_usuario_admin(update.effective_user.id): return

    if not context.args:
        await update.message.reply_text("❌ Uso: `/addslot <user_id> [quantidade]`")
        return

    try:
        user_id = int(context.args[0])
        quantidade = int(context.args[1]) if len(context.args) > 1 else 1
        if quantidade <= 0:
            await update.message.reply_text("❌ A quantidade deve ser um número positivo.")
            return
    except (ValueError, IndexError):
        await update.message.reply_text("❌ ID de usuário ou quantidade inválida.")
        return

    # Verifica se o usuário tem uma configuração de canal, pois os slots são armazenados lá
    config = buscar_configuracao_canal(user_id)
    if not config:
        await update.message.reply_text(f"❌ Não é possível adicionar slot. O usuário `{user_id}` não possui um canal configurado.")
        return
    try:
        adicionar_slot_extra(user_id, quantidade)
        await update.message.reply_text(f"✅ {quantidade} slot(s) extra(s) adicionado(s) com sucesso para o usuário `{user_id}`.")
    except Exception as e:
        logger.error(f"Erro ao adicionar slot para {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao adicionar slot: {e}")

async def remove_slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove todos os slots extras de um usuário, resetando para o valor base do plano."""
    if not is_usuario_admin(update.effective_user.id): return

    user_id = _parse_user_id(update, context)
    if not user_id: return

    try:
        remover_slots_extras(user_id)
        await update.message.reply_text(f"✅ Todos os slots extras do usuário `{user_id}` foram removidos com sucesso.")
    except ValueError as e: # Captura o erro específico da função do DB
        await update.message.reply_text(f"❌ Erro: {e}")
    except Exception as e:
        logger.error(f"Erro ao remover slots extras para {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao remover slots extras: {e}")

async def manage_channel_members_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona ou remove um usuário de um canal de cliente."""
    if not is_usuario_admin(update.effective_user.id): return

    if len(context.args) != 3:
        await update.message.reply_text("❌ Uso: `/channelmembers <add|remove> <owner_user_id> <target_user_id>`")
        return

    action = context.args[0].lower()
    if action not in ['add', 'remove']:
        await update.message.reply_text("❌ Ação inválida. Use 'add' ou 'remove'.")
        return

    try:
        owner_user_id = int(context.args[1])
        target_user_id = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ IDs de usuário devem ser números.")
        return

    config = buscar_configuracao_canal(owner_user_id)
    if not config or not config.get('id_canal_telegram'):
        await update.message.reply_text(f"❌ O usuário proprietário `{owner_user_id}` não possui um canal configurado.")
        return
    
    channel_id = int(config['id_canal_telegram'])
    await update.message.reply_text(f"⏳ Processando... Ação: {action}, Alvo: {target_user_id}, Canal de: {owner_user_id} ({channel_id})")

    try:
        if action == 'add':
            success, message = await adicionar_usuario_ao_canal(channel_id, target_user_id)
        else: # remove
            success, message = await remover_usuario_do_canal(channel_id, target_user_id)
        
        if success:
            await update.message.reply_text(f"✅ Sucesso! {message}")
        else:
            await update.message.reply_text(f"❌ Falha! {message}")
    except Exception as e:
        logger.error(f"Erro ao gerenciar membros do canal {channel_id} para o alvo {target_user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ocorreu um erro inesperado: {e}")

async def set_streamers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Admin) Altera a lista de streamers de um cliente, substituindo a atual."""
    if not is_usuario_admin(update.effective_user.id): return

    if len(context.args) < 2:
        await update.message.reply_text("❌ Uso: `/setstreamers <user_id> <streamer1> [streamer2]...`\nIsso substituirá a lista atual.")
        return

    try:
        user_id = int(context.args[0])
        new_streamers = [s.strip().replace('@', '') for s in context.args[1:]]
    except ValueError:
        await update.message.reply_text("❌ ID de usuário inválido.")
        return

    config = buscar_configuracao_canal(user_id)
    if not config:
        await update.message.reply_text(f"❌ O usuário `{user_id}` não possui um canal configurado.")
        return

    try:
        atualizar_streamers_monitorados(user_id, new_streamers)
        await update.message.reply_text(f"✅ Lista de streamers do usuário `{user_id}` atualizada para: `{', '.join(new_streamers)}`")
    except Exception as e:
        logger.error(f"Erro ao alterar streamers para {user_id} via admin: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao atualizar streamers: {e}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia uma mensagem para todos os assinantes ativos."""
    if not is_usuario_admin(update.effective_user.id): return

    if not context.args:
        await update.message.reply_text("❌ Uso: `/broadcast <sua mensagem>`")
        return

    mensagem = " ".join(context.args)
    
    ids_assinantes = buscar_ids_assinantes_ativos()
    if not ids_assinantes:
        await update.message.reply_text("ℹ️ Nenhum assinante ativo encontrado para enviar a mensagem.")
        return

    await update.message.reply_text(f"📢 Iniciando envio da mensagem para {len(ids_assinantes)} assinantes...")

    sucessos = 0
    falhas = 0

    for user_id in ids_assinantes:
        try:
            await context.bot.send_message(chat_id=user_id, text=mensagem, parse_mode="Markdown")
            sucessos += 1
            await asyncio.sleep(0.1) # Pausa para não sobrecarregar a API
        except telegram_error.Forbidden:
            logger.warning(f"Falha no broadcast para {user_id}: Bot foi bloqueado pelo usuário.")
            falhas += 1
        except Exception as e:
            logger.error(f"Falha no broadcast para {user_id}: {e}")
            falhas += 1

    await update.message.reply_text(
        f"✅ Broadcast finalizado!\n\n"
        f"- Enviado com sucesso para: {sucessos} usuários.\n"
        f"- Falhas (usuários que bloquearam o bot): {falhas} usuários."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe estatísticas gerais do bot."""
    if not is_usuario_admin(update.effective_user.id): return

    stats = obter_estatisticas_gerais()

    texto = (
        "📊 *Estatísticas do Clipador*\n\n"
        f"👥 *Total de Usuários:* {stats['total_usuarios']}\n"
        f"✅ *Assinantes Ativos:* {stats['assinantes_ativos']}\n"
        f"📺 *Canais Monitorados:* {stats['canais_monitorados']}"
    )

    await update.message.reply_text(texto, parse_mode="Markdown")

async def message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia uma mensagem privada para um usuário específico."""
    if not is_usuario_admin(update.effective_user.id): return

    if len(context.args) < 2:
        await update.message.reply_text("❌ Uso: `/message <user_id> <sua mensagem>`")
        return

    try:
        user_id = int(context.args[0])
        mensagem = " ".join(context.args[1:])

        await context.bot.send_message(chat_id=user_id, text=mensagem, parse_mode="Markdown")
        await update.message.reply_text(f"✅ Mensagem enviada com sucesso para o usuário `{user_id}`.")

    except ValueError:
        await update.message.reply_text("❌ ID de usuário inválido.")
    except telegram_error.BadRequest as e:
        await update.message.reply_text(f"❌ Falha ao enviar: {e}. O usuário pode não ter iniciado o bot.")
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para {context.args[0]}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao enviar mensagem: {e}")

async def channel_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe estatísticas detalhadas de um canal específico."""
    if not is_usuario_admin(update.effective_user.id): return

    if not context.args:
        await update.message.reply_text("❌ Uso: `/channelstats <user_id>` ou `/channelstats gratuito`")
        return

    identifier = context.args[0]
    info = []

    if identifier.lower() == 'gratuito':
        info.append("📊 *Estatísticas do Canal Gratuito*")
        channel_id = int(TELEGRAM_CHAT_ID)
        
        # Detalhes do canal (membros)
        detalhes = await obter_detalhes_canal(channel_id)
        info.append(f"👥 *Membros:* {detalhes['participants_count'] if detalhes else 'N/A'}")

        # Requisições
        requests = context.bot_data.get('free_channel_requests', 'N/A')
        info.append(f"📈 *Requisições (último ciclo):* {requests}")

        # Streamers
        streamers = context.bot_data.get('free_channel_streamers', [])
        info.append(f"📡 *Streamers Monitorados ({len(streamers)}):*")
        if streamers:
            info.append(f"`{' | '.join(streamers)}`")
        else:
            info.append("Nenhum")

    elif identifier.isdigit():
        user_id = int(identifier)
        config = buscar_configuracao_canal(user_id)
        if not config or not config.get('id_canal_telegram'):
            await update.message.reply_text(f"❌ Nenhuma configuração de canal encontrada para o usuário `{user_id}`.")
            return

        info.append(f"📊 *Estatísticas do Canal do Usuário `{user_id}`*")
        channel_id = int(config['id_canal_telegram'])

        detalhes = await obter_detalhes_canal(channel_id)
        info.append(f"👥 *Membros:* {detalhes['participants_count'] if detalhes else 'N/A'}")
        requests = context.bot_data.get(f'client_{user_id}_requests', 'N/A')
        info.append(f"📈 *Requisições (último ciclo):* {requests}")
        info.append(f"🧠 *Modo:* `{config.get('modo_monitoramento', 'N/A')}`")
        streamers = [s for s in config.get('streamers_monitorados', '').split(',') if s]
        info.append(f"📡 *Streamers Monitorados ({len(streamers)}):* `{' | '.join(streamers) if streamers else 'Nenhum'}`")
        client_id = config.get('twitch_client_id', 'N/A')
        secret = config.get('twitch_client_secret', 'N/A')
        secret_masked = f"{secret[:4]}...{secret[-4:]}" if len(secret) > 8 else secret
        info.append("\n*--- Credenciais Twitch ---*")
        info.append(f"🔑 *Client ID:* `{client_id}`")
        info.append(f"🔒 *Client Secret:* `{secret_masked}`")

    else:
        await update.message.reply_text("❌ Identificador inválido. Use um ID de usuário ou a palavra 'gratuito'.")
        return

    await update.message.reply_text("\n".join(info), parse_mode="Markdown")