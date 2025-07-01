import os
import sqlite3
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from core.ambiente import MERCADO_PAGO_ACCESS_TOKEN
from core.database import (
    buscar_configuracao_canal,
    salvar_progresso_configuracao,
    limpar_progresso_configuracao,
    conectar,
    buscar_link_canal,
    marcar_configuracao_completa, # Importação necessária para a verificação
    salvar_configuracao_canal_completa, # Importação para salvar a configuração final
    is_configuracao_completa # Importação necessária para a verificação
    , obter_plano_usuario # Importar para obter o plano do usuário
)
from configuracoes import SUPPORT_USERNAME
from chat_privado.usuarios import get_nivel_usuario
import chat_privado.menus.menu_inicial as menu_inicial # Importa o módulo inteiro
from core.telethon_criar_canal import criar_canal_telegram
from canal_gratuito.core.twitch import TwitchAPI # Importa a TwitchAPI para validação
from core.image_utils import gerar_imagem_canal_personalizada

logger = logging.getLogger(__name__)

async def limpar_e_enviar_nova_etapa(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str, botoes: list, parse_mode="Markdown", usar_force_reply=False):
    # Identify the message that triggered the current callback, if any
    current_message_id = None
    if hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message:
        current_message_id = update.callback_query.message.message_id

    # Apagar mensagens antigas armazenadas
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        if msg_id != current_message_id: # Don't delete the current message if we intend to edit it
            try:
                await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
            except Exception: # Catch specific exceptions if possible, e.g., MessageCantBeDeleted
                pass
    context.user_data["mensagens_para_apagar"] = []

    # Tentar editar a mensagem se for callback, senão enviar nova
    reply_markup = InlineKeyboardMarkup(botoes) if botoes else None
    if usar_force_reply:
        from telegram import ForceReply
        reply_markup = ForceReply(selective=True)

    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer()
            nova_msg = await update.callback_query.edit_message_text(
                text=texto,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            nova_msg = await update.message.reply_text(
                text=texto,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        context.user_data["mensagens_para_apagar"] = [nova_msg.message_id]
    except Exception: # Catch specific exceptions if possible, e.g., BadRequest
        # Fallback para enviar uma nova mensagem se a edição falhar
        target_message = update.effective_message
        nova_msg = await target_message.reply_text(
            text=texto,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        context.user_data["mensagens_para_apagar"] = [nova_msg.message_id]

ESPERANDO_CREDENCIAIS, ESPERANDO_STREAMERS, ESCOLHENDO_MODO = range(3)
CONFIGURANDO_PARCEIRO, ESPERANDO_USERNAME_CHEFE, ESCOLHENDO_MODO_PARCEIRO = range(3, 6)

def verificar_status_pagamento(pagamento_id: int) -> str:
    """
    Verifica o status de pagamento no Mercado Pago.
    Esta função parece ser específica para Mercado Pago e não Kirvano.
    Se você está usando Kirvano, esta função pode ser removida ou adaptada.
    """
    # Nota: Esta função parece ser para Mercado Pago. Se você está usando Kirvano,
    # a lógica de verificação de pagamento deve vir do banco de dados,
    # que é atualizado pelo webhook da Kirvano.
    # Se você não usa Mercado Pago, esta função e suas chamadas podem ser removidas.
    # Mantendo por enquanto para compatibilidade com o código existente.
    if not MERCADO_PAGO_ACCESS_TOKEN:
        logger.error("MERCADO_PAGO_ACCESS_TOKEN não configurado. Não é possível verificar pagamento.")
        return "erro"
    url = f"https://api.mercadopago.com/v1/payments/{pagamento_id}"
    headers = {"Authorization": f"Bearer {MERCADO_PAGO_ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        return response.json().get("status", "erro")
    except Exception as e:
        logger.error(f"Erro ao verificar pagamento: {e}")
        return "erro"

async def verificar_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.delete_message()
    except:
        pass
    query = update.callback_query
    await query.answer()
    pagamento_id = context.user_data.get("id_pagamento")

    if not pagamento_id:
        await query.edit_message_text("❌ Não foi possível validar o pagamento. Tente novamente.")
        return

    status = verificar_status_pagamento(pagamento_id)
    if status == "approved":
        # Apagar todas as mensagens anteriores, inclusive o menu de planos
        for msg_id in context.user_data.get("mensagens_para_apagar", []):
            try:
                await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
            except:
                pass
        context.user_data["mensagens_para_apagar"] = []
        # Armazene a mensagem anterior de plano selecionado para posterior exclusão
        context.user_data["mensagem_plano_selecionado"] = query.message.message_id
        # Apagar a mensagem de plano selecionado com botões, se existir
        if "mensagem_plano_selecionado" in context.user_data:
            try:
                await context.bot.delete_message(chat_id=query.from_user.id, message_id=context.user_data["mensagem_plano_selecionado"])
            except:
                pass
            context.user_data.pop("mensagem_plano_selecionado", None)
        # Recuperar o email de pagamento
        email_pagamento = context.user_data.get("email_pagamento", "desconhecido")
        await iniciar_configuracao_pos_pagamento(update, context, email_pagamento)
    elif status == "pending":
        await query.edit_message_text(
            "⏳ Pagamento ainda *pendente*. Clique novamente no botão abaixo após aprovação.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Já paguei", callback_data="verificar_pagamento")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]
            ]),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ Pagamento *não aprovado* ou expirado. Tente novamente.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_3")]
            ]),
            parse_mode="Markdown"
        )

async def menu_configurar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function is the entry point for the configuration funnel.
    # Esta função foi refatorada para permitir a continuação da configuração.
    try:
        await update.callback_query.delete_message()
    except Exception:
        pass

    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    # 1. Verifica se a configuração já está totalmente completa
    telegram_id = update.effective_user.id # Ensure telegram_id is defined here
    if is_configuracao_completa(telegram_id):
        link_canal = buscar_link_canal(telegram_id)
        texto = "⚙️ Seu canal já está configurado.\n\nO que deseja fazer?"
        botoes = [
            [InlineKeyboardButton("👁 Abrir canal", url=link_canal if link_canal else "https://t.me/")],
            [InlineKeyboardButton("🔧 Gerenciar canal", callback_data="abrir_menu_gerenciar_canal")],
            [InlineKeyboardButton("ℹ️ Ver plano", callback_data="ver_plano_atual")], # This callback is in menu_gerenciamento.py
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_0")]
        ]
        await limpar_e_enviar_nova_etapa(update, context, texto, botoes, parse_mode=None)
        return

    # 2. Se não estiver completa, SEMPRE mostra o tutorial inicial.
    # A lógica de "retomar de onde parou" será tratada dentro das funções de cada etapa
    # (iniciar_envio_twitch, iniciar_envio_streamers, escolher_modo_monitoramento)
    # que serão chamadas via botões ou comandos.
    texto = (
        "👣 *Passo 1* — Crie um aplicativo na Twitch:\n"
        "Acesse o painel de desenvolvedor da Twitch e crie um novo aplicativo:\n"
        "https://dev.twitch.tv/console/apps\n\n"
        "Preencha os campos da seguinte forma:\n"
        "• *Nome:* `Clipador`\n"
        "• *URL de redirecionamento OAuth:* `https://clipador.com.br/redirect`\n"
        "• *Categoria:* `Chat Bot`\n"
        "• *Tipo de cliente:* **Confidencial**\n\n"
        "Após criar, na tela de gerenciamento do aplicativo:\n"
        "1. Copie o *ID do cliente*.\n"
        "2. Clique no botão **`[Novo segredo]`** para gerar o seu *Segredo do cliente*. Copie-o e guarde em um local seguro, pois ele só é exibido uma vez!\n\n"
        "Quando estiver com os dois dados em mãos, clique no botão abaixo para enviá-los."
    )
    botoes = [
        [InlineKeyboardButton("📨 Enviar dados da Twitch", callback_data="enviar_twitch")]
    ]

    # Check if there's partial data to inform the user they are resuming
    configuracao = buscar_configuracao_canal(telegram_id)
    if configuracao:
        # Carrega dados parciais para o contexto para continuidade
        context.user_data["twitch_id"] = configuracao.get("twitch_client_id")
        context.user_data["twitch_secret"] = configuracao.get("twitch_client_secret")
        db_streamers_str = configuracao.get("streamers_monitorados")
        context.user_data["streamers"] = [s.strip() for s in db_streamers_str.split(',') if s.strip()] if db_streamers_str else []
        context.user_data["modo_monitoramento"] = configuracao.get("modo_monitoramento")

        plano_assinado = obter_plano_usuario(telegram_id)
        limite_streamers = 1 # Padrão para Mensal Solo
        if plano_assinado == "Mensal Plus":
            limite_streamers = 3
        elif plano_assinado == "Anual Pro":
            limite_streamers = 4  # 3 do plano + 1 de bônus
        elif plano_assinado == "PARCEIRO":
            limite_streamers = 1
        elif plano_assinado == "SUPER":
            limite_streamers = 999
        context.user_data["limite_streamers"] = limite_streamers

        # If any part of the configuration is already saved, add a "resume" message
        if configuracao.get("twitch_client_id") or configuracao.get("streamers_monitorados") or configuracao.get("modo_monitoramento"):
            texto = "✅ Você está retomando a configuração do seu canal.\n\n" + texto
            # Add a button to jump directly to the next incomplete step if they prefer
            # This makes the "resume" more explicit and user-friendly.
            if not configuracao.get("twitch_client_id") or not configuracao.get("twitch_client_secret"):
                # If credentials are missing, the "Enviar dados da Twitch" button is already there.
                # No need for a separate "Continuar Credenciais" button.
                pass
            elif not configuracao.get("streamers_monitorados"):
                botoes.insert(0, [InlineKeyboardButton("➡️ Continuar Streamers", callback_data="iniciar_envio_streamers_callback")]) # New callback for this
            elif not configuracao.get("modo_monitoramento"):
                botoes.insert(0, [InlineKeyboardButton("➡️ Continuar Modo", callback_data="escolher_modo_monitoramento_callback")]) # New callback for this

    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)

async def iniciar_configuracao_pos_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE, email_pagamento: str = ""):
    await update.callback_query.answer()
    # Apagar a mensagem de plano selecionado com botões, se existir
    if "mensagem_plano_selecionado" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=context.user_data["mensagem_plano_selecionado"])
        except:
            pass
        context.user_data.pop("mensagem_plano_selecionado", None)
    # Limpar mensagens salvas e remover qualquer mensagem do tipo "Plano selecionado"
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=f"🔓 Produto gratuito ativado para admin.\nPlano: *{context.user_data.get('nome_plano', 'Indefinido')}*.\n📧 Ativado com: `{email_pagamento}`\n\nClique no botão abaixo para configurar seu canal personalizado:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Continuar configuração", callback_data="continuar_configuracao")]
        ]),
        parse_mode="Markdown"
    )
    await menu_configurar_canal(update, context)

async def iniciar_envio_twitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Não apaga a mensagem anterior (o tutorial), apenas responde a ela.
    texto_instrucao = (
        "Envie suas credenciais da Twitch no formato abaixo, substituindo `SEU_ID_AQUI` e "
        "`SEU_SEGREDO_AQUI` pelos seus dados.\n\n"
        "`ID do cliente: SEU_ID_AQUI`\n`Segredo do cliente: SEU_SEGREDO_AQUI`"
    )
    from telegram import ForceReply
    # Usa reply_text na mensagem original do tutorial para criar um "fio" de conversa
    msg = await query.message.reply_text(
        text=texto_instrucao,
        reply_markup=ForceReply(selective=True),
        parse_mode="Markdown"
    )
    # Adiciona a nova mensagem à lista de exclusão para a próxima etapa,
    # mas mantém a mensagem do tutorial.
    context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
    return ESPERANDO_CREDENCIAIS

# New callback handlers to jump directly to a step from the main tutorial screen
async def iniciar_envio_streamers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # This will call the existing function that sends the streamer prompt with ForceReply
    return await iniciar_envio_streamers(update, context)

async def escolher_modo_monitoramento_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # This will call the existing function that sends the mode selection buttons
    return await escolher_modo_monitoramento(update, context)

async def iniciar_envio_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Função para iniciar a etapa de envio de streamers.
    Pode ser chamada para iniciar ou retomar esta etapa.
    Usa ForceReply para indicar que o bot está aguardando uma resposta.
    """
    from telegram import ForceReply

    limite_streamers = context.user_data.get("limite_streamers", 1)
    streamers_atuais = context.user_data.get("streamers", [])

    if streamers_atuais:
        lista = "\n".join([f"{i+1}. {s}" for i, s in enumerate(streamers_atuais)])
        texto_etapa = (
            f"📺 *Streamers atuais:*\n{lista}\n\n"
            f"Envie o nome de outro streamer que deseja monitorar (ex: @gaules).\n"
            f"Você pode cadastrar até {limite_streamers} streamers.\n"
            f"Se preferir, digite `/continuar` para avançar."
        )
    else:
        texto_etapa = (
            f"✅ Credenciais recebidas!\n\n"
            f"Agora envie o nome do streamer que deseja monitorar (ex: @gaules). Você pode usar @ ou não, como preferir.\n\n"
            f"📌 Você pode cadastrar até {limite_streamers} streamers.\n"
            f"Se preferir, você poderá configurar os streamers depois. Digite `/continuar` para avançar."
        )

    msg = await update.effective_message.reply_text(
        text=texto_etapa,
        reply_markup=ForceReply(selective=True),
        parse_mode="Markdown"
    )
    context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
    return ESPERANDO_STREAMERS

async def receber_credenciais(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Apagar mensagens anteriores da etapa de credenciais
    context.user_data.setdefault("mensagens_para_apagar", []).append(update.message.message_id)
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []

    texto = update.message.text
    twitch_id, twitch_secret = "", ""
    for linha in texto.splitlines():
        if linha.lower().strip().startswith("id do cliente:"):
            twitch_id = linha.split(":", 1)[1].strip()
        elif linha.lower().strip().startswith("segredo do cliente:"):
            twitch_secret = linha.split(":", 1)[1].strip()

    if not twitch_id or not twitch_secret or len(twitch_id) < 10 or len(twitch_secret) < 10:
        await limpar_e_enviar_nova_etapa(
            update,
            context,
            "❌ Formato inválido. Envie no formato:\n\n`ID do cliente: SEU_ID_AQUI`\n`Segredo do cliente: SEU_SEGREDO_AQUI`",
            [],
        )
        return ESPERANDO_CREDENCIAIS

    context.user_data["twitch_id"] = twitch_id
    context.user_data["twitch_secret"] = twitch_secret

    telegram_id = update.message.from_user.id
    nome = update.message.from_user.full_name
    
    # Obter o plano assinado do usuário do banco de dados
    plano_assinado = obter_plano_usuario(telegram_id)
    
    # Definir limite de streamers com base no plano assinado
    limite_streamers = 1  # Padrão para Mensal Solo
    if plano_assinado == "Mensal Plus":
        limite_streamers = 3
    elif plano_assinado == "Anual Pro":
        limite_streamers = 4  # 3 do plano + 1 de bônus
    elif plano_assinado == "PARCEIRO":
        limite_streamers = 1
    elif plano_assinado == "SUPER":
        limite_streamers = 999
    
    logger.info(f"Usuário {telegram_id} com plano '{plano_assinado}'. Limite de streamers: {limite_streamers}")

    context.user_data.update({
        "limite_streamers": limite_streamers,
        "streamers": []
    })
    # Persistência dos dados parciais
    context.user_data["canal_config"] = {
        "twitch_id": twitch_id,
        "twitch_secret": twitch_secret,
        "streamers": [],
        "modo": None
    }
    # Salvar progresso da configuração (etapa credenciais)
    from core.database import salvar_progresso_configuracao
    salvar_progresso_configuracao(telegram_id, etapa="credenciais", dados_parciais={
        "twitch_client_id": twitch_id,
        "twitch_client_secret": twitch_secret
    })

    # Avança para a próxima etapa, que agora usa ForceReply para guiar o usuário
    return await iniciar_envio_streamers(update, context)

async def receber_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Envia uma ação de "digitando" para dar feedback imediato ao usuário
    await update.message.chat.send_action(action="typing")
    context.user_data.setdefault("mensagens_para_apagar", []).append(update.message.message_id)

    nome_raw = update.message.text.strip()
    nome = nome_raw.replace('@', '') # Remove @ se o usuário enviar

    # --- Adicionar validação do streamer ---
    twitch_id = context.user_data.get("twitch_id")
    twitch_client_secret = context.user_data.get("twitch_secret")

    try:
        twitch = TwitchAPI(twitch_id, twitch_client_secret) # Agora passa as credenciais do usuário
        streamer_info = twitch.get_user_info(nome)
        if not streamer_info:
            await update.message.reply_text(f"❌ Streamer '{nome_raw}' não encontrado na Twitch. Verifique o nome e tente novamente.")
            return ESPERANDO_STREAMERS
    except Exception as e:
        logger.error(f"Erro ao validar streamer '{nome}' na Twitch: {e}")
        await update.message.reply_text("❌ Ocorreu um erro ao verificar o streamer na Twitch. Verifique suas credenciais ou tente novamente mais tarde.")
        return ESPERANDO_STREAMERS
    # --- Fim da validação ---
    streamers = context.user_data.get("streamers", [])
    limite = context.user_data.get("limite_streamers")

    if nome.isdigit():
        indice = int(nome) - 1
        if 0 <= indice < len(streamers):
            removido = streamers.pop(indice)
            await limpar_e_enviar_nova_etapa(update, context, f"❌ Removido: {removido}", [])
            context.user_data["streamers"] = streamers
            # Atualiza persistência
            if "canal_config" in context.user_data:
                context.user_data["canal_config"]["streamers"] = streamers
            # Salvar progresso da configuração (etapa streamers)
            from core.database import salvar_progresso_configuracao
            salvar_progresso_configuracao(update.message.from_user.id, etapa="streamers", dados_parciais={
                "streamers": streamers
            })
            return ESPERANDO_STREAMERS

    if len(streamers) >= limite:
        await limpar_e_enviar_nova_etapa(update, context, "❌ Você já atingiu o limite de streamers.", [])
        # Salvar progresso da configuração (etapa streamers)
        from core.database import salvar_progresso_configuracao
        salvar_progresso_configuracao(update.message.from_user.id, etapa="streamers", dados_parciais={
            "streamers": streamers
        })
        # Limpar mensagens antes de ir para a escolha de modo
        context.user_data["mensagens_para_apagar"] = []
        return await escolher_modo_monitoramento(update, context)

    streamers.append(nome)
    context.user_data["streamers"] = streamers
    # Atualiza persistência
    if "canal_config" in context.user_data:
        context.user_data["canal_config"]["streamers"] = streamers
    # Salvar progresso da configuração (etapa streamers)
    from core.database import salvar_progresso_configuracao
    salvar_progresso_configuracao(update.message.from_user.id, etapa="streamers", dados_parciais={
        "streamers": streamers
    })

    if len(streamers) < limite:
        lista = "\n".join([f"{i+1}. {s}" for i, s in enumerate(streamers)])
        restante = limite - len(streamers)
        texto = (
            f"✅ Adicionado: {nome}\n\nStreamers atuais:\n{lista}\n\n"
            f"Você pode enviar mais {restante}, digite /continuar ou envie o número para remover."
        )
        # Usa ForceReply para manter o fluxo de conversa e indicar que o bot espera mais nomes
        from telegram import ForceReply
        msg = await update.message.reply_text(
            text=texto,
            reply_markup=ForceReply(selective=True),
            parse_mode="Markdown"
        )
        context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)
        return ESPERANDO_STREAMERS
    else:
        # Limpar mensagens antes de ir para a escolha de modo
        context.user_data["mensagens_para_apagar"] = []
        return await escolher_modo_monitoramento(update, context)

async def comando_continuar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await escolher_modo_monitoramento(update, context)

async def escolher_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Limpeza das mensagens anteriores de configuração de streamers
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []
    texto = (
        "🧠 *Modos de Monitoramento do Clipador:*\n\n"
        "🤖 *Automático:* O Clipador escolhe o melhor modo.\n"
        "🚀 *Modo Louco:* Muitos clipes rapidamente.\n"
        "🎯 *Modo Padrão:* Equilíbrio entre qualidade e quantidade.\n"
        "🔬 *Modo Cirúrgico:* Apenas clipes virais.\n"
        "🛠 *Manual:* (em breve)\n\n"
        "📌 Você poderá alterar o modo depois."
    )
    botoes = [
        [InlineKeyboardButton("🤖 Automático", callback_data="modo_AUTOMATICO")],
        [InlineKeyboardButton("🚀 Modo Louco", callback_data="modo_MODO_LOUCO")],
        [InlineKeyboardButton("🎯 Modo Padrão", callback_data="modo_MODO_PADRAO")],
        [InlineKeyboardButton("🔬 Modo Cirúrgico", callback_data="modo_MODO_CIRURGICO")],
        [InlineKeyboardButton("🛠 Manual", callback_data="abrir_menu_manual")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_streamers")]
    ]
    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
    return ESCOLHENDO_MODO

async def voltar_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    streamers = context.user_data.get("streamers", [])
    limite = context.user_data.get("limite_streamers", 1)
    restante = limite - len(streamers)
    lista = "\n".join([f"{i+1}. {s}" for i, s in enumerate(streamers)])
    texto = f"📺 *Streamers atuais:*\n{lista}\n\nVocê pode enviar mais {restante} ou digitar /continuar para avançar."
    await query.edit_message_text(text=texto, parse_mode="Markdown")
    return ESPERANDO_STREAMERS

async def mostrar_botoes_modos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "🧠 *Modos de Monitoramento do Clipador:*\n\n"
        "🤖 *Automático:* O Clipador escolhe a melhor forma de monitorar.\n"
        "🚀 *Modo Louco:* Todos os clipes, sem falta.\n"
        "🎯 *Modo Padrão:* Equilíbrio entre qualidade e quantidade.\n"
        "🔬 *Modo Cirúrgico:* Apenas clipes muito interessantes.\n"
        "🛠 *Manual: Você define as regras de monitoramento.\n\n"
        "📌 Você poderá alterar o modo depois."
    )
    botoes = [
        [InlineKeyboardButton("🤖 Automático", callback_data="modo_AUTOMATICO")],
        [InlineKeyboardButton("🚀 Modo Louco", callback_data="modo_MODO_LOUCO")],
        [InlineKeyboardButton("🎯 Modo Padrão", callback_data="modo_MODO_PADRAO")],
        [InlineKeyboardButton("🔬 Modo Cirúrgico", callback_data="modo_MODO_CIRURGICO")],
        [InlineKeyboardButton("🛠 Manual", callback_data="abrir_menu_manual")],
        [InlineKeyboardButton("🔙 Voltar para Streamers", callback_data="voltar_streamers")]
    ]
    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
    return ESCOLHENDO_MODO

async def abrir_menu_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre o menu de configuração manual."""
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
        [InlineKeyboardButton("1️⃣ Mínimo de clipes (Em breve)", callback_data="config_manual_placeholder")],
        [InlineKeyboardButton("2️⃣ Intervalo (segundos) (Em breve)", callback_data="config_manual_placeholder")],
        [InlineKeyboardButton("3️⃣ Frequência (minutos) (Em breve)", callback_data="config_manual_placeholder")],
        [InlineKeyboardButton("🔙 Voltar para Modos", callback_data="escolher_modo")]
    ]

    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
    return ESCOLHENDO_MODO

async def config_manual_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback de placeholder para botões de configuração manual."""
    query = update.callback_query
    await query.answer("Esta funcionalidade estará disponível em breve!", show_alert=True)

async def salvar_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data.replace("modo_", "")
    context.user_data["modo_monitoramento"] = modo
    # Atualiza persistência
    if "canal_config" in context.user_data:
        context.user_data["canal_config"]["modo"] = modo

    telegram_id = query.from_user.id
    # Salvar progresso da configuração (etapa modo)
    from core.database import salvar_progresso_configuracao
    salvar_progresso_configuracao(telegram_id, etapa="modo", dados_parciais={
        "modo_monitoramento": modo
    })
    twitch_client_id = context.user_data.get("twitch_id")
    twitch_client_secret = context.user_data.get("twitch_secret")
    streamers = context.user_data.get("streamers", [])

    texto = (
        f"📋 *Revisão final dos dados:*\n\n"
        f"👤 Usuário: @{query.from_user.username or query.from_user.first_name}\n"
        f"🧪 Client ID: `{twitch_client_id}`\n"
        f"🔐 Client Secret: `{twitch_client_secret[:6]}...`\n"
        f"📺 Streamers: `{', '.join(streamers) if streamers else 'Nenhum'}`\n"
        f"🧠 Modo: `{modo}`\n\n"
        f"⚠️ Após salvar, você terá até 1 hora para alterar os streamers preenchidos.\n"
        f"Slots vazios poderão ser preenchidos depois, sem prazo."
    )
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []
    botoes = [
        [InlineKeyboardButton("✅ Confirmar e salvar", callback_data="confirmar_salvar_canal")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="escolher_modo")]
    ]
    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
    return ESCOLHENDO_MODO

async def salvar_modo_monitoramento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data.replace("modo_", "")
    context.user_data["modo_monitoramento"] = modo
    # Atualiza persistência
    if "canal_config" in context.user_data:
        context.user_data["canal_config"]["modo"] = modo

    telegram_id = query.from_user.id
    # Salvar progresso da configuração (etapa modo)
    from core.database import salvar_progresso_configuracao
    salvar_progresso_configuracao(telegram_id, etapa="modo", dados_parciais={
        "modo": modo
    })
    twitch_client_id = context.user_data.get("twitch_id")
    twitch_client_secret = context.user_data.get("twitch_secret")
    streamers = context.user_data.get("streamers", [])

    texto = (
        f"📋 *Revisão final dos dados:*\n\n"
        f"👤 Usuário: @{query.from_user.username or query.from_user.first_name}\n"
        f"🧪 Client ID: `{twitch_client_id}`\n"
        f"🔐 Client Secret: `{twitch_client_secret[:6]}...`\n"
        f"📺 Streamers: `{', '.join(streamers)}`\n"
        f"🧠 Modo: `{modo}`\n\n"
        f"⚠️ Após salvar, você terá até 1 hora para alterar os streamers preenchidos.\n"
        f"Slots vazios poderão ser preenchidos depois, sem prazo."
    )
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        try:
            await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
        except:
            pass
    context.user_data["mensagens_para_apagar"] = []
    botoes = [
        [InlineKeyboardButton("✅ Confirmar e salvar", callback_data="confirmar_salvar_canal")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_streamers")]
    ]
    await limpar_e_enviar_nova_etapa(update, context, texto, botoes)
    return ESCOLHENDO_MODO

async def mostrar_revisao_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe a revisão final dos dados antes de salvar."""
    query = update.callback_query
    if query:
        await query.answer()
async def confirmar_salvar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    username = query.from_user.username or f"user{telegram_id}"

    canal_config = context.user_data.get("canal_config", {})
    twitch_client_id = context.user_data.get("twitch_id") or canal_config.get("twitch_id")
    twitch_client_secret = context.user_data.get("twitch_secret") or canal_config.get("twitch_secret")
    streamers = context.user_data.get("streamers") or canal_config.get("streamers", [])
    modo = context.user_data.get("modo_monitoramento") or canal_config.get("modo")

    # Get the ID of the message that triggered this callback
    current_message_id = query.message.message_id if query.message else None

    caminho_imagem_personalizada = None

    # Apagar mensagens antigas, exceto a mensagem atual que será editada
    messages_to_delete_ids = []
    for msg_id in context.user_data.get("mensagens_para_apagar", []):
        if msg_id != current_message_id:
            messages_to_delete_ids.append(msg_id)

    for msg_id in messages_to_delete_ids:
        try:
            await context.bot.delete_message(chat_id=telegram_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Could not delete message {msg_id}: {e}")
    context.user_data["mensagens_para_apagar"] = [current_message_id] if current_message_id else []

    try:
        # 1. Gerar a imagem personalizada ANTES de criar o canal
        await query.edit_message_text("⏳ Gerando imagem de perfil personalizada...", parse_mode="Markdown")
        caminho_imagem_personalizada = await gerar_imagem_canal_personalizada(telegram_id, context)

        # 2. Salvar configuração e criar o canal
        await query.edit_message_text("⏳ Salvando configurações e criando seu canal...")
        salvar_configuracao_canal_completa(telegram_id, twitch_client_id, twitch_client_secret, streamers, modo)
        id_canal, link_canal = await criar_canal_telegram(
            nome_usuario=username, telegram_id=telegram_id, nome_exibicao=query.from_user.first_name, caminho_imagem=caminho_imagem_personalizada
        )
        # Salva o link do canal no banco de dados para uso futuro
        from core.database import salvar_link_canal
        salvar_link_canal(telegram_id, id_canal, link_canal)
        # Marca a configuração como completa no banco de dados de usuários
        marcar_configuracao_completa(telegram_id, True)

        # Adiciona uma pequena pausa para garantir que o bot seja processado como membro do canal
        import asyncio
        await asyncio.sleep(1)

        # Busca a configuração salva para obter o número de slots
        config_completa = buscar_configuracao_canal(telegram_id)
        slots_ativos = config_completa.get('slots_ativos', 1)
        num_streamers = len(streamers)

        # Constrói a lista de streamers para a mensagem
        streamers_str = "\n".join([f"• `{s}`" for s in streamers]) if streamers else "Nenhum streamer configurado."

        # Monta a mensagem de boas-vindas rica em detalhes
        welcome_message_parts = [
            f"🎉 Bem-vindo(a) ao seu canal Clipador, @{username}!\n",
            "Sua configuração inicial está pronta para começar a clipar os melhores momentos. 🚀\n",
            "*" + ("-" * 25) + "*",
            "📋 *Resumo da sua Configuração:*",
            f"📺 *Streamers Monitorados ({num_streamers}/{slots_ativos}):*",
            streamers_str,
            f"🧠 *Modo de Monitoramento:* `{modo}`",
            "*" + ("-" * 25) + "*\n"
        ]

        # Adiciona um aviso se houver slots disponíveis
        slots_disponiveis = slots_ativos - num_streamers
        if slots_disponiveis > 0:
            plural_s = "s" if slots_disponiveis > 1 else ""
            welcome_message_parts.append(
                f"⚠️ Você ainda tem *{slots_disponiveis} slot{plural_s}* disponível{plural_s} para adicionar novos streamers! "
                "Você pode fazer isso a qualquer momento no menu de gerenciamento."
            )

        welcome_message_to_channel = "\n".join(welcome_message_parts)

        # --- Start of retry logic for sending welcome message ---
        max_retries_welcome_msg = 5
        for i in range(max_retries_welcome_msg):
            try:
                await context.bot.send_message(chat_id=id_canal, text=welcome_message_to_channel, parse_mode="Markdown")
                logger.info(f"✅ Mensagem de boas-vindas enviada para o canal {id_canal} na tentativa {i+1}.")
                break # Message sent successfully, exit loop
            except Exception as e:
                error_message_str = str(e)
                if ("Chat not found" in error_message_str or "Bad Request: chat not found" in error_message_str) and i < max_retries_welcome_msg - 1:
                    logger.warning(f"Tentativa {i+1}/{max_retries_welcome_msg}: Chat not found para o canal {id_canal}. Retentando em 2 segundos...")
                    await asyncio.sleep(2) # Wait a bit longer
                else:
                    logger.error(f"Falha ao enviar mensagem de boas-vindas para o canal {id_canal} após {i+1} tentativas.")
                    raise # Re-raise if it's not "Chat not found" or if max retries reached
        logger.info(f"✅ Canal criado e configurado com sucesso para o usuário {telegram_id}. Link: {link_canal}")

        await query.edit_message_text(
            f"✅ Tudo pronto!\n\n"
            f"📢 Seu canal exclusivo foi criado com sucesso!\n\n"
            "Você começará a receber clipes automaticamente com base nas suas configurações 🚀",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Abrir canal", url=link_canal)],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_0")]
            ]),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Erro crítico ao criar/configurar canal para o usuário {telegram_id}: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ocorreu um erro ao criar seu canal. Por favor, tente novamente mais tarde ou contate o suporte.\n\nDetalhes: {e}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="abrir_configurar_canal")],
                [InlineKeyboardButton("💬 Contatar Suporte", url=f"https://t.me/{SUPPORT_USERNAME}")]
            ]),
            parse_mode="Markdown"
        )
        # Garante que o status de configuração não seja marcado como completo em caso de falha
        marcar_configuracao_completa(telegram_id, False)
        return ConversationHandler.END
    finally:
        # Garante que a imagem temporária seja apagada, mesmo se houver uma falha
        # no meio do processo, após a imagem ter sido criada.
        if caminho_imagem_personalizada and os.path.exists(caminho_imagem_personalizada):
            try:
                os.remove(caminho_imagem_personalizada)
                logger.info(f"🗑️ Imagem temporária '{caminho_imagem_personalizada}' apagada na limpeza final.")
            except OSError as err:
                logger.error(f"❌ Erro ao apagar imagem temporária na limpeza final: {err}")

def atualizar_telegram_id_usuario(telegram_id):
    from core.database import conectar
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET telegram_id = ? WHERE id = ?", (telegram_id, telegram_id))
    conn.commit()
    conn.close()

# ConversationHandler do processo
def configurar_canal_conversa():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(iniciar_envio_twitch, pattern="^enviar_twitch$"),
            CallbackQueryHandler(menu_configurar_canal, pattern="^menu_configurar_canal$|^abrir_configurar_canal$"),
            CallbackQueryHandler(iniciar_envio_streamers_callback, pattern="^iniciar_envio_streamers_callback$"), # New entry point for resuming streamers
            CallbackQueryHandler(escolher_modo_monitoramento_callback, pattern="^escolher_modo_monitoramento_callback$"), # New entry point for resuming mode
            CallbackQueryHandler(responder_menu_7_configurar, pattern="^continuar_configuracao$")
        ],
        states={
            ESPERANDO_CREDENCIAIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_credenciais)],
            ESPERANDO_STREAMERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_streamer),
                CommandHandler("continuar", comando_continuar)
            ],
            ESCOLHENDO_MODO: [
                CallbackQueryHandler(mostrar_botoes_modos, pattern="^escolher_modo$"),
                CallbackQueryHandler(abrir_menu_manual, pattern="^abrir_menu_manual$"),
                CallbackQueryHandler(config_manual_placeholder, pattern="^config_manual_placeholder$"),
                CallbackQueryHandler(salvar_modo_monitoramento, pattern="^modo_"),
                CallbackQueryHandler(voltar_streamers, pattern="^voltar_streamers$"),
                CallbackQueryHandler(confirmar_salvar_canal, pattern="^confirmar_salvar_canal$")
            ]
        },
        fallbacks=[CommandHandler("start", menu_inicial.responder_inicio)],
        allow_reentry=True
    )

# Redirecionador manual para o menu
async def verificar_callback_configurar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await menu_configurar_canal(update, context)

# Resposta ao botão "continuar_configuracao"
async def responder_menu_7_configurar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("🚀 Continuando configuração do canal...")
    await menu_configurar_canal(update, context)