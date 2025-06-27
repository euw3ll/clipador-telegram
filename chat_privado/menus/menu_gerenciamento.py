from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from core.database import (
    buscar_configuracao_canal,
    obter_plano_usuario,
    buscar_usuario_por_id,
    atualizar_modo_monitoramento,
    atualizar_streamers_monitorados
)
from datetime import datetime, timedelta, timezone
import logging
from canal_gratuito.core.twitch import TwitchAPI # Reutilizando a TwitchAPI

logger = logging.getLogger(__name__)

GERENCIANDO_STREAMERS, AGUARDANDO_ADICAO, AGUARDANDO_REMOCAO = range(3)

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

    limite_streamers = 1
    if plano == "Mensal Plus":
        limite_streamers = 3
    elif plano == "Anual Pro":
        limite_streamers = 5

    texto = (
        f"📋 *Seu Plano Atual*\n\n"
        f"📦 *Plano:* {plano}\n"
        f"🗓️ *Expira em:* {data_expiracao}\n"
        f"📺 *Streamers configurados:* {num_streamers}/{limite_streamers}\n\n"
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
        [InlineKeyboardButton("➕ Comprar Slot de Streamer", callback_data="comprar_slot_placeholder")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]

    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )

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
        [InlineKeyboardButton("🛠 Manual", callback_data="abrir_menu_manual_gerenciamento")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]
    ]

    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )

async def abrir_menu_manual_gerenciamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre o menu de configuração manual a partir do menu de gerenciamento."""
    query = update.callback_query
    await query.answer()

    texto = (
        "⚙️ *Configuração Manual*\n\n"
        "Ajuste os parâmetros do seu Clipador para ter controle total sobre o que é clipado. "
        "Ideal para estratégias específicas!\n\n"
        "1️⃣ *Mínimo de Clipes:*\n"
        "Define quantos clipes diferentes do mesmo momento precisam ser criados para que o bot considere o evento como viral. (Ex: 3)\n\n"
        "2️⃣ *Intervalo entre Clipes (segundos):*\n"
        "O tempo máximo em segundos entre um clipe e outro para que eles sejam agrupados no mesmo evento. (Ex: 60)\n\n"
        "3️⃣ *Frequência de Monitoramento (minutos):*\n"
        "De quantos em quantos minutos o bot deve verificar por novos clipes. Um valor menor significa clipes mais rápidos, mas mais uso da API. (Valor mínimo recomendado: 2 minutos)\n\n"
        "⚠️ *Atenção:* A configuração destes parâmetros estará disponível em breve."
    )

    botoes = [
        [InlineKeyboardButton("1️⃣ Mínimo de clipes (Em breve)", callback_data="placeholder_callback")],
        [InlineKeyboardButton("2️⃣ Intervalo (segundos) (Em breve)", callback_data="placeholder_callback")],
        [InlineKeyboardButton("3️⃣ Frequência (minutos) (Em breve)", callback_data="placeholder_callback")],
        [InlineKeyboardButton("🔙 Voltar para Modos", callback_data="gerenciar_modo")]
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
                modification_info_message = "\n\n❌ O período de 1 hora para alterações na lista de streamers expirou. Você poderá alterar novamente na próxima renovação do seu plano."
        except ValueError:
            logger.warning(f"Could not parse streamers_ultima_modificacao: {last_mod_str}")
            modification_info_message = "\n\n⚠️ Erro ao verificar o período de modificação. Por favor, contate o suporte."

    limite_streamers = 1
    if plano == "Mensal Plus":
        limite_streamers = 3
    elif plano == "Anual Pro":
        limite_streamers = 5

    texto_lista = "\n".join([f"{i+1}. `{s}`" for i, s in enumerate(streamers)]) if num_streamers > 0 else "Nenhum streamer configurado."

    texto = (
        f"📺 *Gerenciar Streamers*\n\n"
        f"Seu plano atual (`{plano}`) permite monitorar até *{limite_streamers}* streamers.\n"
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
    keyboard_list.append([InlineKeyboardButton("🔙 Voltar", callback_data="voltar_gerenciamento")])
    
    return texto, InlineKeyboardMarkup(keyboard_list)

async def iniciar_gerenciamento_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ponto de entrada para o gerenciamento de streamers."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    
    texto, keyboard = await _construir_menu_streamers(telegram_id)
    
    await query.edit_message_text(text=texto, reply_markup=keyboard, parse_mode="Markdown")
    
    return GERENCIANDO_STREAMERS

async def pedir_novo_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Qual o nome do streamer que você deseja adicionar? (ex: @gaules)")
    return AGUARDANDO_ADICAO

async def adicionar_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id
    nome_streamer = update.message.text.strip().replace('@', '')

    config = buscar_configuracao_canal(telegram_id)
    twitch_id = config.get("twitch_client_id")
    twitch_secret = config.get("twitch_client_secret")
    
    try:
        twitch = TwitchAPI(twitch_id, twitch_secret) # Agora passa as credenciais do usuário
        if not twitch.get_user_info(nome_streamer):
            await update.message.reply_text(f"❌ Streamer '{nome_streamer}' não encontrado. Tente novamente.")
            return AGUARDANDO_ADICAO
    except Exception as e:
        await update.message.reply_text("❌ Erro ao validar streamer. Verifique suas credenciais e tente novamente.")
        return GERENCIANDO_STREAMERS

    streamers = config.get('streamers_monitorados', '').split(',') if config.get('streamers_monitorados') else []
    streamers.append(nome_streamer)
    atualizar_streamers_monitorados(telegram_id, streamers)

    if config.get('id_canal_telegram'):
        await context.bot.send_message(
            chat_id=config['id_canal_telegram'],
            text=f"➕ Streamer `{nome_streamer}` adicionado à lista de monitoramento.",
            parse_mode="Markdown"
        )

    texto, keyboard = await _construir_menu_streamers(telegram_id)
    await update.message.reply_text(text=texto, reply_markup=keyboard, parse_mode="Markdown")
    return GERENCIANDO_STREAMERS

async def pedir_remocao_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Digite o número do streamer que você deseja remover da lista.")
    return AGUARDANDO_REMOCAO

async def remover_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id
    try:
        indice = int(update.message.text.strip()) - 1
        config = buscar_configuracao_canal(telegram_id)
        streamers = config.get('streamers_monitorados', '').split(',')

        if 0 <= indice < len(streamers):
            removido = streamers.pop(indice)
            atualizar_streamers_monitorados(telegram_id, streamers)
            
            if config.get('id_canal_telegram'):
                await context.bot.send_message(
                    chat_id=config['id_canal_telegram'],
                    text=f"➖ Streamer `{removido}` removido da lista de monitoramento.",
                    parse_mode="Markdown"
                )
            
            texto, keyboard = await _construir_menu_streamers(telegram_id)
            await update.message.reply_text(text=texto, reply_markup=keyboard, parse_mode="Markdown")
            return GERENCIANDO_STREAMERS
        else:
            await update.message.reply_text("❌ Número inválido. Tente novamente.")
            return AGUARDANDO_REMOCAO
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Entrada inválida. Por favor, envie apenas o número.")
        return AGUARDANDO_REMOCAO

async def encerrar_gerenciamento_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Volta para o menu de gerenciamento principal."""
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