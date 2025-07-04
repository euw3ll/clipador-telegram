from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error as telegram_error
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
from configuracoes import KIRVANO_LINKS, PLANOS_PRECOS
from core.database import (
    buscar_configuracao_canal,
    obter_plano_usuario,
    buscar_usuario_por_id,
    atualizar_modo_monitoramento,
    atualizar_streamers_monitorados,
    atualizar_configuracao_manual,
    obter_slots_base_plano
)
from datetime import datetime, timedelta, timezone
import asyncio
import re
import logging
from chat_privado.menus.menu_configurar_canal import cancelar_e_iniciar
from canal_gratuito.core.twitch import TwitchAPI # Reutilizando a TwitchAPI

logger = logging.getLogger(__name__)

# Estados para as conversas
(
    GERENCIANDO_STREAMERS, AGUARDANDO_ADICAO, AGUARDANDO_REMOCAO, # Gerenciamento de Streamers
    CONFIG_MIN_CLIPS, CONFIG_INTERVALO, CONFIG_MIN_CLIPS_VOD # Configuração Manual
) = range(6)

async def ver_plano_atual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe os detalhes do plano atual do usuário."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    plano = obter_plano_usuario(telegram_id)
    usuario = buscar_usuario_por_id(telegram_id)
    config = buscar_configuracao_canal(telegram_id)

    if not plano or not usuario or not config:
        await query.edit_message_text(
            "❌ Não foi possível encontrar os dados da sua assinatura ou canal.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]])
        )
        return

    data_expiracao_str = usuario.get('data_expiracao', 'N/A')
    try:
        data_expiracao = datetime.fromisoformat(data_expiracao_str).strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        data_expiracao = "N/A"

    # Lógica para calcular slots
    slots_ativos = config.get('slots_ativos', 1)
    slots_base = obter_slots_base_plano(plano)
    slots_extras = max(0, slots_ativos - slots_base)

    texto = (
        f"📋 *Detalhes da sua Assinatura*\n\n"
        f"📦 *Plano:* {plano}\n"
        f"🗓️ *Expira em:* {data_expiracao}\n\n"
        f"🎰 *Slots Contratados:*\n"
        f"  - Slots do plano: `{slots_base}`\n"
        f"  - Slots extras: `{slots_extras}`\n"
        f"  - *Total:* `{slots_ativos}`\n\n"
        "Obrigado por fazer parte do Clipador! 🔥"
    )

    botoes = [
        [InlineKeyboardButton("⚙️ Gerenciar Canal", callback_data="abrir_menu_gerenciar_canal")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]

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
        [InlineKeyboardButton("🔔 Gerenciar Notificações", callback_data="abrir_menu_notificacoes")],
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

    preco_slot = PLANOS_PRECOS.get("Slot Extra", 0.0)
    texto = (
        "➕ *Comprar Slot Extra*\n\n"
        "Adicione um novo streamer para monitorar em seu canal!\n\n"
        f"💰 *Valor:* R${preco_slot:.2f}\n"
        "💳 *Pagamento:* Único (não é uma assinatura)\n\n"
        "Clique no link de pagamento e, após concluir, clique em *'Já Paguei'* abaixo."
    )

    link_pagamento = KIRVANO_LINKS.get("Slot Extra")
    if not link_pagamento or "COLE_SEU_LINK" in link_pagamento:
        await query.edit_message_text(
            "❌ A opção de compra de slot extra está indisponível no momento.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]])
        )
        return

    botoes = [
        [InlineKeyboardButton(f"💳 Pagar R${preco_slot:.2f}", url=link_pagamento)],
        [InlineKeyboardButton("✅ Já Paguei", callback_data="verificar_compra_slot")],
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
                text=f"<b>🧠 O modo de monitoramento foi alterado para: {novo_modo}.</b>",
                parse_mode="HTML"
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

async def _construir_menu_streamers(telegram_id: int, mensagem_feedback: str = None) -> tuple[str, InlineKeyboardMarkup]:
    """Helper para construir a mensagem e os botões do menu de gerenciamento de streamers."""
    config = buscar_configuracao_canal(telegram_id)
    streamers = [s for s in config.get('streamers_monitorados', '').split(',') if s] if config and config.get('streamers_monitorados') else []
    num_streamers = len(streamers)

    # Mensagem informativa padrão sobre a regra de remoção.
    modification_info_message = "\n\n_A remoção de streamers só é permitida na primeira hora após a configuração ou na renovação da assinatura._"

    limite_streamers = config.get('slots_ativos', 1)

    texto_lista = "\n".join([f"{i+1}. `{s}`" for i, s in enumerate(streamers)]) if num_streamers > 0 else "Nenhum streamer configurado."

    # Adiciona a mensagem de feedback se ela existir, com uma linha divisória
    feedback_str = f"{mensagem_feedback}\n{'-'*25}\n\n" if mensagem_feedback else ""

    texto = (
        f"{feedback_str}"
        f"📺 *Gerenciar Streamers*\n\n"
        f"Você está usando *{num_streamers}/{limite_streamers}* slots.\n\n"
        f"*Sua lista atual:*\n{texto_lista}"
        f"{modification_info_message}" # A mensagem agora é sempre a mesma
    )

    botoes_linha_1 = []
    # Botão de adicionar aparece se houver slots vagos.
    if num_streamers < limite_streamers:
        botoes_linha_1.append(InlineKeyboardButton("➕ Adicionar", callback_data="add_streamer"))
    
    # Botão de remover aparece se houver streamers na lista. A verificação de tempo será na ação.
    if num_streamers > 0:
        botoes_linha_1.append(InlineKeyboardButton("➖ Remover", callback_data="remove_streamer"))
    
    keyboard_list = []
    if botoes_linha_1:
        keyboard_list.append(botoes_linha_1)
    
    # Botão de comprar slot extra.
    if num_streamers >= limite_streamers:
        keyboard_list.append([InlineKeyboardButton("➕ Comprar Slot Extra", callback_data="comprar_slot_extra")])

    keyboard_list.append([InlineKeyboardButton("🔙 Voltar", callback_data="voltar_gerenciamento")])
    
    return texto, InlineKeyboardMarkup(keyboard_list)

async def _limpar_feedback_menu(context: ContextTypes.DEFAULT_TYPE):
    """Callback do JobQueue para limpar a mensagem de feedback do menu."""
    job = context.job
    chat_id = job.data['chat_id']
    message_id = job.data['message_id']
    
    try:
        texto_limpo, keyboard_limpo = await _construir_menu_streamers(chat_id)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=texto_limpo,
            reply_markup=keyboard_limpo,
            parse_mode="Markdown"
        )
        logger.info(f"Feedback do menu de streamers limpo para o chat {chat_id}.")
    except telegram_error.BadRequest as e:
        if "Message is not modified" in str(e) or "Query is too old" in str(e):
            logger.debug(f"Menu para {chat_id} já estava atualizado ou o query expirou. Nenhuma limpeza de feedback necessária.")
        else:
            logger.warning(f"Não foi possível limpar o feedback do menu para {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao limpar feedback do menu para {chat_id}: {e}", exc_info=True)

async def iniciar_gerenciamento_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ponto de entrada para o gerenciamento de streamers."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    # Salva o ID da mensagem do menu para poder editá-la depois
    context.user_data['gerenciamento_streamer_menu_id'] = query.message.message_id
    
    texto, keyboard = await _construir_menu_streamers(telegram_id) # A primeira chamada não tem feedback
    
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

    # Etapa 4.1: Preparar a função para múltiplos streamers
    nomes_input = update.message.text.strip().replace('@', '')
    # Usa regex para separar por vírgula ou espaço e filtra itens vazios
    nomes_para_adicionar = [nome for nome in re.split(r'[,\s]+', nomes_input) if nome]

    if not nomes_para_adicionar:
        return GERENCIANDO_STREAMERS # Não faz nada se a entrada for vazia

    config = buscar_configuracao_canal(telegram_id)
    twitch_id = config.get("twitch_client_id")
    twitch_secret = config.get("twitch_client_secret")
    streamers_atuais = [s for s in (config.get('streamers_monitorados', '') or '').split(',') if s]
    limite_slots = config.get('slots_ativos', 1)

    adicionados_sucesso = []
    falhas_validacao = []
    falhas_limite = []
    ja_existentes = []

    # Etapa 4.2: Implementar o loop de validação
    try:
        twitch = TwitchAPI(twitch_id, twitch_secret)
        for nome_streamer in nomes_para_adicionar:
            # Verifica se o usuário já atingiu o limite de slots
            if len(streamers_atuais) + len(adicionados_sucesso) >= limite_slots:
                falhas_limite.append(nome_streamer)
                continue

            # Verifica se o streamer já está na lista (ignorando maiúsculas/minúsculas)
            if nome_streamer.lower() in [s.lower() for s in streamers_atuais] or nome_streamer.lower() in [s.lower() for s in adicionados_sucesso]:
                ja_existentes.append(nome_streamer)
                continue

            if twitch.get_user_info(nome_streamer):
                adicionados_sucesso.append(nome_streamer)
            else:
                falhas_validacao.append(nome_streamer)
    except Exception as e:
        logger.error(f"Erro ao validar streamers para {telegram_id}: {e}")
        await update.message.reply_text("❌ Erro ao validar streamers. Verifique suas credenciais e tente novamente.")
        return GERENCIANDO_STREAMERS

    # Etapa 4.3: Salvar, notificar e atualizar a interface
    if adicionados_sucesso:
        streamers_atuais.extend(adicionados_sucesso)
        atualizar_streamers_monitorados(telegram_id, streamers_atuais)
        if config.get('id_canal_telegram'):
            await context.bot.send_message(
                chat_id=config['id_canal_telegram'],
                text=f"<b>➕ Streamer(s) adicionado(s): {', '.join(adicionados_sucesso)}.</b>",
                parse_mode="HTML"
            )

    # Constrói a mensagem de feedback
    feedback_parts = []
    if adicionados_sucesso: feedback_parts.append(f"✅ Adicionados: `{', '.join(adicionados_sucesso)}`")
    if ja_existentes: feedback_parts.append(f"ℹ️ Já na lista: `{', '.join(ja_existentes)}`")
    if falhas_validacao: feedback_parts.append(f"❌ Não encontrados: `{', '.join(falhas_validacao)}`")
    if falhas_limite: feedback_parts.append(f"🚫 Limite de slots atingido. Não foi possível adicionar: `{', '.join(falhas_limite)}`")

    feedback_final_str = "\n".join(feedback_parts) if feedback_parts else None

    menu_msg_id = context.user_data.get('gerenciamento_streamer_menu_id')
    if not menu_msg_id:
        logger.warning(f"Não foi possível encontrar o ID do menu para o usuário {telegram_id}. O menu não será atualizado.")
        return GERENCIANDO_STREAMERS

    # Atualiza o menu com a mensagem de feedback (mesmo que seja None, a função lida com isso)
    texto, keyboard = await _construir_menu_streamers(telegram_id, mensagem_feedback=feedback_final_str)
    try:
        await context.bot.edit_message_text(chat_id=telegram_id, message_id=menu_msg_id, text=texto, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro ao editar menu com feedback para {telegram_id}: {e}")
        return GERENCIANDO_STREAMERS

    # Se houve uma mensagem de feedback, agenda um job para removê-la após 10 segundos.
    if feedback_final_str and context.job_queue:
        context.job_queue.run_once(
            _limpar_feedback_menu,
            10,
            data={'chat_id': telegram_id, 'message_id': menu_msg_id},
            name=f"limpar_feedback_add_{telegram_id}_{menu_msg_id}"
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
    menu_msg_id = context.user_data.get('gerenciamento_streamer_menu_id')

    # Apaga a mensagem do usuário e o prompt do bot
    await update.message.delete()
    prompt_msg_id = context.user_data.pop('prompt_msg_id', None)
    if prompt_msg_id:
        try:
            await context.bot.delete_message(chat_id=telegram_id, message_id=prompt_msg_id)
        except Exception:
            pass
            
    # --- VERIFICAÇÃO DE TEMPO LIMITE ANTES DE PROCESSAR A REMOÇÃO ---
    config = buscar_configuracao_canal(telegram_id)
    last_mod_str = config.get('streamers_ultima_modificacao')
    
    feedback_str = None
    proximo_estado = GERENCIANDO_STREAMERS

    if last_mod_str:
        try:
            last_mod_datetime = datetime.fromisoformat(last_mod_str).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_mod_datetime > timedelta(hours=1):
                feedback_str = "❌ A remoção só é permitida na primeira hora."
        except ValueError:
            logger.warning(f"Could not parse streamers_ultima_modificacao: {last_mod_str} for user {telegram_id}")

    if not feedback_str: # Só processa a remoção se não houver erro de tempo
        try:
            indice = int(update.message.text.strip()) - 1
            streamers = [s for s in config.get('streamers_monitorados', '').split(',') if s]

            if 0 <= indice < len(streamers):
                removido = streamers.pop(indice)
                atualizar_streamers_monitorados(telegram_id, streamers)
                
                if config.get('id_canal_telegram'):
                    await context.bot.send_message(
                        chat_id=config['id_canal_telegram'],
                        text=f"<b>➖ Streamer {removido} removido da lista de monitoramento.</b>",
                        parse_mode="HTML"
                    )
                feedback_str = f"➖ Removido: `{removido}`"
            else:
                feedback_str = "❌ Número inválido. Tente novamente."
                proximo_estado = AGUARDANDO_REMOCAO
        except (ValueError, IndexError):
            feedback_str = "❌ Entrada inválida. Por favor, envie apenas o número."
            proximo_estado = AGUARDANDO_REMOCAO

    # --- Lógica de atualização do menu ---
    if menu_msg_id:
        texto, keyboard = await _construir_menu_streamers(telegram_id, mensagem_feedback=feedback_str)
        try:
            await context.bot.edit_message_text(chat_id=telegram_id, message_id=menu_msg_id, text=texto, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Erro ao editar menu de remoção com feedback para {telegram_id}: {e}")
            return proximo_estado

        # Se houve uma mensagem de feedback, agenda um job para removê-la após 10 segundos.
        if feedback_str and context.job_queue:
            context.job_queue.run_once(
                _limpar_feedback_menu,
                10,
                data={'chat_id': telegram_id, 'message_id': menu_msg_id},
                name=f"limpar_feedback_remove_{telegram_id}_{menu_msg_id}"
            )

    return proximo_estado

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
        fallbacks=[
            CallbackQueryHandler(encerrar_gerenciamento_streamers, pattern="^voltar_gerenciamento$"),
            CommandHandler("start", cancelar_e_iniciar)
        ],
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
    min_clips = config.get('manual_min_clips', 'Não definido') if config else 'Não definido'
    
    texto = (
        f"⚙️ *Configuração Manual: Mínimo de Clipes*\n\n"
        f"Defina quantos clipes precisam ser criados no mesmo momento para que o bot considere o evento como viral.\n\n"
        f"🔹 *Valor atual:* `{min_clips}`\n"
        f"💡 *Recomendado:* 2 ou mais clipes.\n"
        f"⚠️ *Limite:* Mínimo 1 clipe.\n\n"
        "Por favor, envie o novo valor."
    )
    botoes = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_config_manual")]]
    
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return CONFIG_MIN_CLIPS

async def receber_min_clips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe e valida o mínimo de clipes."""
    try:
        valor = int(update.message.text)
        if valor < 1:
            await update.message.reply_text("❌ Valor inválido. O mínimo de clipes deve ser 1 ou mais. Tente novamente.")
            return CONFIG_MIN_CLIPS
    except ValueError:
        await update.message.reply_text("❌ Por favor, envie apenas um número. Tente novamente.")
        return CONFIG_MIN_CLIPS
        
    context.user_data['manual_min_clips'] = valor
    
    config = buscar_configuracao_canal(update.effective_user.id)
    intervalo = config.get('manual_interval_sec', 'Não definido') if config else 'Não definido'

    texto = (
        f"✅ Mínimo de clipes definido para: *{valor}*\n\n"
        f"⚙️ *Configuração Manual: Intervalo entre Clipes*\n\n"
        f"Defina qual a diferença de tempo os clipes precisam ter para se considerar um grupo viral.\n\n"
        f"_Explicação: Imagine a 'janela de tempo' de um evento viral. Se vários clipes são criados dentro desta janela (ex: 60 segundos), o bot entende que todos fazem parte do mesmo grande momento._\n\n"
        f"🔹 *Valor atual:* `{intervalo}`\n"
        f"💡 *Recomendado:* 60 segundos.\n"
        f"⚠️ *Limite:* Mínimo 10 segundos.\n\n"
        "Por favor, envie o novo valor."
    )
    botoes = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_config_manual")]]
    
    await update.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return CONFIG_INTERVALO

async def receber_intervalo_e_pedir_vod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe o intervalo para clipes ao vivo e pede a configuração para VODs."""
    try:
        valor = int(update.message.text)
        if valor < 10:
            await update.message.reply_text("❌ Valor inválido. O intervalo deve ser de no mínimo 10 segundos. Tente novamente.")
            return CONFIG_INTERVALO
    except ValueError:
        await update.message.reply_text("❌ Por favor, envie apenas um número. Tente novamente.")
        return CONFIG_INTERVALO
        
    context.user_data['manual_interval_sec'] = valor
    
    config = buscar_configuracao_canal(update.effective_user.id)
    min_clips_vod = config.get('manual_min_clips_vod', 'Não definido') if config else 'Não definido'

    texto = (
        f"✅ Intervalo para clipes ao vivo definido para: *{valor} segundos*\n\n"
        f"⚙️ *Configuração Manual: Clipes de VOD (Offline)*\n\n"
        "Agora, defina quantos clipes precisam ser criados em um VOD (quando o streamer está offline) para o bot enviar.\n\n"
        "Isso evita o envio de clipes menos relevantes que não aconteceram durante a live.\n\n"
        "⚠️ *Importante:* Esta configuração só tem efeito quando o *Modo Manual* está ativo.\n\n"
        f"🔹 *Valor atual:* `{min_clips_vod}`\n"
        f"💡 *Recomendado:* 3 ou mais clipes.\n"
        f"⚠️ *Limite:* Mínimo 1 clipe.\n\n"
        "Por favor, envie o novo valor."
    )
    botoes = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_config_manual")]]
    
    await update.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return CONFIG_MIN_CLIPS_VOD

async def receber_min_clips_vod_e_salvar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe o mínimo de clipes para VOD, salva todas as configurações e encerra."""
    telegram_id = update.effective_user.id
    try:
        valor = int(update.message.text)
        if valor < 1:
            await update.message.reply_text("❌ Valor inválido. O mínimo de clipes para VOD deve ser 1 ou mais. Tente novamente.")
            return CONFIG_MIN_CLIPS_VOD
    except ValueError:
        await update.message.reply_text("❌ Por favor, envie apenas um número. Tente novamente.")
        return CONFIG_MIN_CLIPS_VOD
        
    min_clips_live = context.user_data.pop('manual_min_clips')
    interval_sec_live = context.user_data.pop('manual_interval_sec')
    min_clips_vod = valor
    
    atualizar_configuracao_manual(
        telegram_id=telegram_id,
        min_clips=min_clips_live,
        interval_sec=interval_sec_live,
        min_clips_vod=min_clips_vod
    )
    atualizar_modo_monitoramento(telegram_id, "MANUAL")
    
    texto_sucesso = (
        f"✅ *Configuração Manual Salva!*\n\n"
        f"Seu modo de monitoramento foi alterado para `MANUAL` com os seguintes parâmetros:\n\n"
        f"*AO VIVO (ONLINE):*\n"
        f"- Mínimo de Clipes: `{min_clips_live}`\n"
        f"- Intervalo entre Clipes: `{interval_sec_live}` segundos\n\n"
        f"*VOD (OFFLINE):*\n"
        f"- Mínimo de Clipes: `{min_clips_vod}`\n\n"
        "Lembre-se que estas regras só se aplicam enquanto o modo `MANUAL` estiver ativo."
    )
    botoes = [[InlineKeyboardButton("🔙 Voltar ao Gerenciamento", callback_data="abrir_menu_gerenciar_canal")]]
    
    await update.message.reply_text(text=texto_sucesso, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    return ConversationHandler.END

async def cancelar_config_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela a conversa de configuração manual e volta para o menu de modos."""
    context.user_data.pop('manual_min_clips', None)
    context.user_data.pop('manual_interval_sec', None) # Limpa ambos os dados parciais

    # Re-exibe o menu de seleção de modo, sem mensagem de cancelamento.
    # A função abrir_menu_alterar_modo já lida com a edição da mensagem.
    await abrir_menu_alterar_modo(update, context)

    return ConversationHandler.END

def configurar_manual_conversa():
    """Cria o ConversationHandler para a configuração do modo manual."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_configuracao_manual, pattern="^configurar_manual_iniciar$")],
        states={
            CONFIG_MIN_CLIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_min_clips)],
            CONFIG_INTERVALO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_intervalo_e_pedir_vod)],
            CONFIG_MIN_CLIPS_VOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_min_clips_vod_e_salvar)],
        },
        fallbacks=[
            CallbackQueryHandler(cancelar_config_manual, pattern="^cancelar_config_manual$"),
            CommandHandler("start", cancelar_e_iniciar)
        ],
        map_to_parent={
            ConversationHandler.END: -1
        }
    )