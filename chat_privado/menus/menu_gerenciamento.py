from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from configuracoes import KIRVANO_LINKS
from core.database import (
    buscar_configuracao_canal,
    obter_plano_usuario,
    buscar_usuario_por_id,
    atualizar_modo_monitoramento,
    atualizar_streamers_monitorados,
    atualizar_configuracao_manual
)
from datetime import datetime, timedelta, timezone
import logging
from canal_gratuito.core.twitch import TwitchAPI # Reutilizando a TwitchAPI

logger = logging.getLogger(__name__)

# Estados para as conversas
(
    GERENCIANDO_STREAMERS, AGUARDANDO_ADICAO, AGUARDANDO_REMOCAO, # Gerenciamento de Streamers
    CONFIG_MIN_CLIPS, CONFIG_INTERVALO # Configuração Manual
) = range(5)

async def ver_plano_atual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe os detalhes do plano atual do usuário."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    plano = obter_plano_usuario(telegram_id)
    usuario = buscar_usuario_por_id(telegram_id)
    config = buscar_configuracao_canal(telegram_id)

    if not plano or not usuario:
        await query.edit_message_text(
            "❌ Não foi possível encontrar os dados da sua assinatura.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]])
        )
        return

    data_expiracao_str = usuario.get('data_expiracao', 'N/A')
    try:
        data_expiracao = datetime.fromisoformat(data_expiracao_str).strftime('%d/%m/%Y às %H:%M')
    except (ValueError, TypeError):
        data_expiracao = "N/A"

    streamers = config.get('streamers_monitorados', '').split(',') if config and config.get('streamers_monitorados') else []
    num_streamers = len(streamers) if streamers and streamers[0] else 0

    limite_streamers = config.get('slots_ativos', 1) if config else 1

    texto = (
        f"📋 *Seu Plano Atual*\n\n"
        f"📦 *Plano:* {plano}\n"
        f"🗓️ *Expira em:* {data_expiracao}\n"
        f"📺 *Slots em uso:* {num_streamers}/{limite_streamers}\n\n"
        "Obrigado por fazer parte do Clipador! 🔥"
    )

    botoes = [[InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]]

    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )

async def abrir_menu_gerenciar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o menu de gerenciamento para um canal já configurado."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    config = buscar_configuracao_canal(telegram_id)
    if not config:
        await query.edit_message_text(
            "❌ Você não tem um canal configurado para gerenciar.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]])
        )
        return

    client_id = config.get('twitch_client_id', 'Não configurado')
    client_secret = config.get('twitch_client_secret', 'Não configurado')
    secret_masked = f"{client_secret[:4]}...{client_secret[-4:]}" if client_secret and len(client_secret) > 8 else client_secret
    modo_atual = config.get('modo_monitoramento', 'Não definido')

    texto = (
        f"⚙️ *Gerenciamento do Canal*\n\n"
        f"Aqui você pode ajustar as configurações do seu canal.\n\n"
        f"🧠 *Modo de Monitoramento Atual:* `{modo_atual}`\n\n"
        f"🔑 *Credenciais Twitch (somente visualização):*\n"
        f"  - Client ID: `{client_id}`\n"
        f"  - Client Secret: `{secret_masked}`\n"
    )

    botoes = [
        [InlineKeyboardButton("🧠 Alterar Modo de Monitoramento", callback_data="gerenciar_modo")],
        [InlineKeyboardButton("📺 Gerenciar Streamers", callback_data="gerenciar_streamers")],
        [InlineKeyboardButton("➕ Comprar Slot de Streamer", callback_data="comprar_slot_extra")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]

    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )

async def comprar_slot_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o menu para comprar um slot extra."""
    query = update.callback_query
    await query.answer()
    context.user_data["plano_esperado"] = "Slot Extra"

    texto = (
        "➕ *Comprar Slot Extra*\n\n"
        "Adicione um novo streamer para monitorar em seu canal!\n\n"
        "💰 *Valor:* R$14,90\n"
        "💳 *Pagamento:* Único (não é uma assinatura)\n\n"
        "Clique no botão abaixo para ir para a página de pagamento. "
        "Após a confirmação, seu novo slot será liberado automaticamente."
    )

    link_pagamento = KIRVANO_LINKS.get("Slot Extra")
    if not link_pagamento or "COLE_SEU_LINK" in link_pagamento:
        await query.edit_message_text(
            "❌ A opção de compra de slot extra está indisponível no momento.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]])
        )
        return

    botoes = [
        [InlineKeyboardButton("💳 Pagar R$14,90", url=link_pagamento)],
        [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]
    ]

    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

async def placeholder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback de placeholder para funcionalidades em desenvolvimento."""
    query = update.callback_query
    await query.answer("Esta funcionalidade será implementada em breve.", show_alert=True)

async def abrir_menu_alterar_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe os botões para o usuário escolher um novo modo de monitoramento."""
    query = update.callback_query
    await query.answer()

    texto = (
        "🧠 *Escolha o novo Modo de Monitoramento:*\n\n"
        "🤖 *Automático:* O Clipador escolhe o melhor modo.\n"
        "🚀 *Modo Louco:* Muitos clipes rapidamente.\n"
        "🎯 *Modo Padrão:* Equilíbrio entre qualidade e quantidade.\n"
        "🔬 *Modo Cirúrgico:* Apenas clipes virais.\n"
        "🛠 *Manual:* Você define as regras de monitoramento."
    )
    botoes = [
        [InlineKeyboardButton("🤖 Automático", callback_data="novo_modo_AUTOMATICO")],
        [InlineKeyboardButton("🚀 Modo Louco", callback_data="novo_modo_MODO_LOUCO")],
        [InlineKeyboardButton("🎯 Modo Padrão", callback_data="novo_modo_MODO_PADRAO")],
        [InlineKeyboardButton("🔬 Modo Cirúrgico", callback_data="novo_modo_MODO_CIRURGICO")],
        [InlineKeyboardButton("🛠 Manual", callback_data="configurar_manual_iniciar")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]
    ]

    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

async def salvar_novo_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Salva o novo modo de monitoramento e notifica o usuário."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    novo_modo = query.data.replace("novo_modo_", "")

    try:
        atualizar_modo_monitoramento(telegram_id, novo_modo)
        config = buscar_configuracao_canal(telegram_id)
        id_canal_telegram = config.get('id_canal_telegram')

        if id_canal_telegram:
            await context.bot.send_message(
                chat_id=id_canal_telegram,
                text=f"🔔 *Atualização de Configuração*\n\nO modo de monitoramento foi alterado para: `{novo_modo}`.",
                parse_mode="Markdown"
            )

        await query.edit_message_text(
            text=f"✅ Modo de monitoramento alterado com sucesso para `{novo_modo}`!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Erro ao alterar modo para {telegram_id}: {e}")
        await query.edit_message_text(
            text="❌ Ocorreu um erro ao tentar alterar o modo. Por favor, tente novamente.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]])
        )

async def _construir_menu_streamers(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Helper para construir a mensagem e os botões do menu de gerenciamento de streamers."""
    plano = obter_plano_usuario(telegram_id)
    config = buscar_configuracao_canal(telegram_id)
    streamers = [s for s in config.get('streamers_monitorados', '').split(',') if s] if config and config.get('streamers_monitorados') else []
    num_streamers = len(streamers)

    # Lógica de cooldown para alterações de streamers
    last_mod_str = config.get('streamers_ultima_modificacao')
    allow_streamer_modification = True
    modification_info_message = ""
    add_buy_slot_button = False # Flag para adicionar o botão de compra

    if last_mod_str:
        try:
            # Converte a string TIMESTAMP do banco de dados para objeto datetime (assumindo UTC)
            last_mod_datetime = datetime.fromisoformat(last_mod_str).replace(tzinfo=timezone.utc)
            time_since_last_mod = datetime.now(timezone.utc) - last_mod_datetime
            cooldown_period = timedelta(hours=1)

            if time_since_last_mod < cooldown_period: # Ainda dentro da janela de 1 hora
                remaining_time = cooldown_period - time_since_last_mod
                total_seconds = int(remaining_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                modification_info_message = f"\n\n⚠️ Você tem *{hours}h {minutes}m* restantes para alterar a lista de streamers."
            else: # 1 hora se passou, modificações não são mais permitidas para este período
                allow_streamer_modification = False
                modification_info_message = "\n\n❌ O período para alterar a lista de streamers expirou. Para adicionar um novo streamer, você pode aguardar a renovação do seu plano ou comprar um slot extra."
                add_buy_slot_button = True
        except ValueError:
            logger.warning(f"Could not parse streamers_ultima_modificacao: {last_mod_str}")
            modification_info_message = "\n\n⚠️ Erro ao verificar o período de modificação. Por favor, contate o suporte."

    limite_streamers = config.get('slots_ativos', 1)

    texto_lista = "\n".join([f"{i+1}. `{s}`" for i, s in enumerate(streamers)]) if num_streamers > 0 else "Nenhum streamer configurado."

    texto = (
        f"📺 *Gerenciar Streamers*\n\n"
        f"Você está usando *{num_streamers}/{limite_streamers}* slots.\n\n"
        f"*Sua lista atual:*\n{texto_lista}\n\n"
        f"{modification_info_message}" # Mensagem sobre o tempo de alteração
    )

    botoes_linha_1 = []
    if allow_streamer_modification: # Adiciona botões apenas se a modificação for permitida
        if num_streamers < limite_streamers:
            botoes_linha_1.append(InlineKeyboardButton("➕ Adicionar", callback_data="add_streamer"))
        if num_streamers > 0:
            botoes_linha_1.append(InlineKeyboardButton("➖ Remover", callback_data="remove_streamer"))
    
    keyboard_list = []
    if botoes_linha_1:
        keyboard_list.append(botoes_linha_1)
    
    if add_buy_slot_button:
        keyboard_list.append([InlineKeyboardButton("➕ Comprar Slot Extra", callback_data="comprar_slot_extra")])

    keyboard_list.append([InlineKeyboardButton("🔙 Voltar", callback_data="voltar_gerenciamento")])
    
    return texto, InlineKeyboardMarkup(keyboard_list)

async def iniciar_gerenciamento_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ponto de entrada para o gerenciamento de streamers."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    # Salva o ID da mensagem do menu para poder editá-la depois
    context.user_data['gerenciamento_streamer_menu_id'] = query.message.message_id
    
    texto, keyboard = await _construir_menu_streamers(telegram_id)
    
    await query.edit_message_text(text=texto, reply_markup=keyboard, parse_mode="Markdown")
    
    return GERENCIANDO_STREAMERS

async def pedir_novo_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Envia uma nova mensagem para não apagar a lista
    prompt_msg = await query.message.reply_text("Qual o nome do streamer que você deseja adicionar? (ex: @gaules)")
    # Salva o ID da mensagem de prompt para apagar depois
    context.user_data['prompt_msg_id'] = prompt_msg.message_id

    return AGUARDANDO_ADICAO

async def adicionar_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id

    # Apaga a mensagem do usuário e o prompt do bot
    await update.message.delete()
    prompt_msg_id = context.user_data.pop('prompt_msg_id', None)
    if prompt_msg_id:
        try:
            await context.bot.delete_message(chat_id=telegram_id, message_id=prompt_msg_id)
        except Exception:
            pass

    nome_streamer = update.message.text.strip().replace('@', '')

    config = buscar_configuracao_canal(telegram_id)
    twitch_id = config.get("twitch_client_id")
    twitch_secret = config.get("twitch_client_secret")
    
    try:
        twitch = TwitchAPI(twitch_id, twitch_secret) # Agora passa as credenciais do usuário
        if not twitch.get_user_info(nome_streamer):
            # Informa o erro e re-exibe o menu principal de gerenciamento
            await update.message.reply_text(f"❌ Streamer '{nome_streamer}' não encontrado. Tente novamente.", quote=False)
            texto, keyboard = await _construir_menu_streamers(telegram_id)
            menu_msg_id = context.user_data.get('gerenciamento_streamer_menu_id')
            if menu_msg_id:
                await context.bot.edit_message_text(chat_id=telegram_id, message_id=menu_msg_id, text=texto, reply_markup=keyboard, parse_mode="Markdown")
            return GERENCIANDO_STREAMERS # Volta para o estado principal
    except Exception as e:
        await update.message.reply_text("❌ Erro ao validar streamer. Verifique suas credenciais e tente novamente.", quote=False)
        return GERENCIANDO_STREAMERS

    streamers = config.get('streamers_monitorados', '').split(',') if config.get('streamers_monitorados') else []
    streamers = [s for s in streamers if s] # Limpa strings vazias
    streamers.append(nome_streamer)
    atualizar_streamers_monitorados(telegram_id, streamers)

    if config.get('id_canal_telegram'):
        await context.bot.send_message(
            chat_id=config['id_canal_telegram'],
            text=f"➕ Streamer `{nome_streamer}` adicionado à lista de monitoramento.",
            parse_mode="Markdown"
        )

    # Edita a mensagem original do menu com a lista atualizada
    menu_msg_id = context.user_data.get('gerenciamento_streamer_menu_id')
    texto, keyboard = await _construir_menu_streamers(telegram_id)
    if menu_msg_id:
        await context.bot.edit_message_text(
            chat_id=telegram_id,
            message_id=menu_msg_id,
            text=texto, 
            reply_markup=keyboard, 
            parse_mode="Markdown"
        )
    
    return GERENCIANDO_STREAMERS

async def pedir_remocao_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Envia uma nova mensagem para não apagar a lista
    prompt_msg = await query.message.reply_text("Digite o número do streamer que você deseja remover da lista.")
    # Salva o ID da mensagem de prompt para apagar depois
    context.user_data['prompt_msg_id'] = prompt_msg.message_id
    
    return AGUARDANDO_REMOCAO

async def remover_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id

    # Apaga a mensagem do usuário e o prompt do bot
    await update.message.delete()
    prompt_msg_id = context.user_data.pop('prompt_msg_id', None)
    if prompt_msg_id:
        try:
            await context.bot.delete_message(chat_id=telegram_id, message_id=prompt_msg_id)
        except Exception:
            pass
            
    try:
        indice = int(update.message.text.strip()) - 1
        config = buscar_configuracao_canal(telegram_id)
        streamers = config.get('streamers_monitorados', '').split(',')
        streamers = [s for s in streamers if s] # Limpa strings vazias

        if 0 <= indice < len(streamers):
            removido = streamers.pop(indice)
            atualizar_streamers_monitorados(telegram_id, streamers)
            
            if config.get('id_canal_telegram'):
                await context.bot.send_message(
                    chat_id=config['id_canal_telegram'],
                    text=f"➖ Streamer `{removido}` removido da lista de monitoramento.",
                    parse_mode="Markdown"
                )
            
            # Edita a mensagem original do menu com a lista atualizada
            menu_msg_id = context.user_data.get('gerenciamento_streamer_menu_id')
            texto, keyboard = await _construir_menu_streamers(telegram_id)
            if menu_msg_id:
                await context.bot.edit_message_text(
                    chat_id=telegram_id,
                    message_id=menu_msg_id,
                    text=texto, 
                    reply_markup=keyboard, 
                    parse_mode="Markdown"
                )
            return GERENCIANDO_STREAMERS
        else:
            await update.message.reply_text("❌ Número inválido. Tente novamente.", quote=False)
            return AGUARDANDO_REMOCAO
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Entrada inválida. Por favor, envie apenas o número.", quote=False)
        return AGUARDANDO_REMOCAO

async def encerrar_gerenciamento_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Volta para o menu de gerenciamento principal e limpa mensagens pendentes."""
    query = update.callback_query
    
    # Limpa o prompt se existir
    prompt_msg_id = context.user_data.pop('prompt_msg_id', None)
    if prompt_msg_id:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=prompt_msg_id)
        except Exception:
            pass
            
    await abrir_menu_gerenciar_canal(update, context)
    return ConversationHandler.END

def gerenciar_streamers_conversa():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_gerenciamento_streamers, pattern="^gerenciar_streamers$")],
        states={
            GERENCIANDO_STREAMERS: [
                CallbackQueryHandler(pedir_novo_streamer, pattern="^add_streamer$"),
                CallbackQueryHandler(pedir_remocao_streamer, pattern="^remove_streamer$"),
                CallbackQueryHandler(encerrar_gerenciamento_streamers, pattern="^voltar_gerenciamento$")
            ],
            AGUARDANDO_ADICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, adicionar_streamer)],
            AGUARDANDO_REMOCAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, remover_streamer)],
        },
        fallbacks=[CallbackQueryHandler(encerrar_gerenciamento_streamers, pattern="^voltar_gerenciamento$")],
        map_to_parent={
            ConversationHandler.END: -1
        }
    )

# --- CONVERSA DE CONFIGURAÇÃO MANUAL ---

async def iniciar_configuracao_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia a conversa para configurar o modo manual."""
    query = update.callback_query
    await query.answer()
    
    config = buscar_configuracao_canal(update.effective_user.id)
    min_clips = config.get('manual_min_clips', 'Não definido')
    
    texto = (
        f"⚙️ *Configuração Manual: Mínimo de Clipes*\n\n"
        f"Defina quantos clipes diferentes do mesmo momento precisam ser criados para que o bot considere o evento como viral.\n\n"
        f"🔹 *Valor atual:* `{min_clips}`\n"
        f"💡 *Recomendado:* 3\n"
        f"⚠️ *Limite:* Mínimo 2.\n\n"
        "Por favor, envie o novo valor."
    )
    botoes = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_config_manual")]]
    
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return CONFIG_MIN_CLIPS

async def receber_min_clips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe e valida o mínimo de clipes."""
    try:
        valor = int(update.message.text)
        if valor < 2:
            await update.message.reply_text("❌ Valor inválido. O mínimo de clipes deve ser 2 ou mais. Tente novamente.")
            return CONFIG_MIN_CLIPS
    except ValueError:
        await update.message.reply_text("❌ Por favor, envie apenas um número. Tente novamente.")
        return CONFIG_MIN_CLIPS
        
    context.user_data['manual_min_clips'] = valor
    
    config = buscar_configuracao_canal(update.effective_user.id)
    intervalo = config.get('manual_interval_sec', 'Não definido')

    texto = (
        f"✅ Mínimo de clipes definido para: *{valor}*\n\n"
        f"⚙️ *Configuração Manual: Intervalo entre Clipes*\n\n"
        f"É a 'janela de tempo' de um evento viral. Se vários clipes são criados dentro desta janela (ex: 60 segundos), o bot entende que todos fazem parte do mesmo grande momento. Isso ajuda a separar um acontecimento de outro que ocorre minutos depois.\n\n"
        f"🔹 *Valor atual:* `{intervalo}`\n"
        f"💡 *Recomendado:* 60\n"
        f"⚠️ *Limite:* Mínimo 10 segundos.\n\n"
        "Por favor, envie o novo valor."
    )
    botoes = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_config_manual")]]
    
    await update.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return CONFIG_INTERVALO

async def receber_intervalo_e_salvar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe o intervalo, salva todas as configurações manuais e encerra a conversa."""
    telegram_id = update.effective_user.id
    try:
        valor = int(update.message.text)
        if valor < 10:
            await update.message.reply_text("❌ Valor inválido. O intervalo deve ser de no mínimo 10 segundos. Tente novamente.")
            return CONFIG_INTERVALO
    except ValueError:
        await update.message.reply_text("❌ Por favor, envie apenas um número. Tente novamente.")
        return CONFIG_INTERVALO
        
    min_clips = context.user_data.pop('manual_min_clips')
    interval_sec = valor
    
    atualizar_configuracao_manual(telegram_id=telegram_id, min_clips=min_clips, interval_sec=interval_sec)
    atualizar_modo_monitoramento(telegram_id, "MANUAL")
    
    texto_sucesso = (
        f"✅ *Configuração Manual Salva!*\n\n"
        f"A frequência de monitoramento é padronizada em *60 segundos* para garantir a estabilidade para todos os usuários.\n\n"
        f"Seu modo de monitoramento foi alterado para `MANUAL` com os seguintes parâmetros:\n"
        f"- Mínimo de Clipes: `{min_clips}`\n"
        f"- Intervalo entre Clipes: `{interval_sec}` segundos"
    )
    botoes = [[InlineKeyboardButton("🔙 Voltar ao Gerenciamento", callback_data="abrir_menu_gerenciar_canal")]]
    
    await update.message.reply_text(text=texto_sucesso, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return ConversationHandler.END

async def cancelar_config_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela a conversa de configuração manual."""
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('manual_min_clips', None)
    context.user_data.pop('manual_interval_sec', None)
    
    await query.edit_message_text(
        "Operação cancelada.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar para Modos", callback_data="gerenciar_modo")]])
    )
    return ConversationHandler.END

def configurar_manual_conversa():
    """Cria o ConversationHandler para a configuração do modo manual."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_configuracao_manual, pattern="^configurar_manual_iniciar$")],
        states={
            CONFIG_MIN_CLIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_min_clips)],
            CONFIG_INTERVALO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_intervalo_e_salvar)],
        },
        fallbacks=[CallbackQueryHandler(cancelar_config_manual, pattern="^cancelar_config_manual$")],
        map_to_parent={
            ConversationHandler.END: -1
        }
    )