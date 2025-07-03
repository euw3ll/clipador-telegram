from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler

# --- FUNÇÃO MOVIDA PARA CÁ ---
async def avancar_para_nova_etapa(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str, botoes: list, parse_mode="Markdown", usar_force_reply=False):
    mensagens_para_apagar = context.user_data.get("mensagens_para_apagar", [])
    for msg_id in mensagens_para_apagar:
        try: # Tenta apagar mensagens anteriores
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=msg_id) 
        except Exception:
            pass
    context.user_data["mensagens_para_apagar"] = []

    if update.message:
        target = update.message
    elif update.callback_query:
        target = update.callback_query.message
    else:
        return

    if usar_force_reply:
        nova_msg = await target.reply_text(
            texto,
            reply_markup=ForceReply(selective=True),
            parse_mode=parse_mode
        )
    else:
        nova_msg = await target.reply_text(
            texto,
            reply_markup=InlineKeyboardMarkup(botoes) if botoes else None,
            parse_mode=parse_mode
        )

    context.user_data.setdefault("mensagens_para_apagar", []).append(nova_msg.message_id)
from core.database import (
    adicionar_usuario,
    salvar_plano_usuario,
    is_usuario_admin,
    email_ja_utilizado_por_outro_usuario, # Adicionado importação
    buscar_pagamento_por_email, # Usado para buscar detalhes da compra
    registrar_log_pagamento, # Adicionado importação
    vincular_email_usuario,
    vincular_compra_e_ativar_usuario, # Nova função para ativar usuário e vincular compra
    adicionar_slot_extra
)
from io import BytesIO
from chat_privado.menus.menu_configurar_canal import responder_inicio # Importa a nova função centralizada
import logging
from core.pagamento import criar_pagamento_pix, criar_pagamento_cartao # Usado apenas se o gateway for Mercado Pago
from configuracoes import GATEWAY_PAGAMENTO, KIRVANO_LINKS, PLANOS_PRECOS
import base64

logger = logging.getLogger(__name__)

PEDIR_EMAIL = 1

def obter_valor_plano(plano: str) -> float:
    """Busca o valor do plano no arquivo de configurações."""
    return PLANOS_PRECOS.get(plano, 0.0)

# MENU 5: Mostrar opções de pagamento por plano
async def responder_menu_5_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plano_esperado"] = "Mensal Solo"
    await exibir_opcoes_pagamento(update, context, "Mensal Solo")

async def responder_menu_5_plus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plano_esperado"] = "Mensal Plus"
    await exibir_opcoes_pagamento(update, context, "Mensal Plus")

async def responder_menu_5_anual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plano_esperado"] = "Anual Pro"
    await exibir_opcoes_pagamento(update, context, "Anual Pro")

# Exibe botões com base no gateway
async def exibir_opcoes_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    valor = obter_valor_plano(plano_nome)

    texto = (
        f"📦 *Plano selecionado: {plano_nome}*\n"
        f"💰 Valor: R${valor:.2f}\n\n"
    )

    if GATEWAY_PAGAMENTO == "KIRVANO":
        texto += "Clique abaixo para acessar o link de pagamento:"
        botoes = [
            [InlineKeyboardButton("📎 Acessar link de pagamento", url=KIRVANO_LINKS[plano_nome])],
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
        ]
    elif GATEWAY_PAGAMENTO == "MERCADOPAGO":
        texto += "Escolha a forma de pagamento:"
        botoes = [
            [InlineKeyboardButton("💸 Pagar com Pix", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
            [InlineKeyboardButton("💳 Pagar com Cartão", callback_data=f"pagar_cartao_{plano_nome.replace(' ', '_')}")],
            [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
        ]
    else:
        texto += "❌ Gateway de pagamento inválido."
        botoes = [[InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]]
    
    # A mensagem com os botões de pagamento será editada ou substituída.
    # A função `avancar_para_nova_etapa` (ou similar) na próxima etapa cuidará da limpeza.
    try:
        msg = await query.edit_message_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(botoes),
            parse_mode="Markdown"
        )
        context.user_data.setdefault("mensagens_para_apagar", []).append(query.message.message_id)
    except BadRequest:
        msg = await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
        context.user_data.setdefault("mensagens_para_apagar", []).append(msg.message_id)

# GERAÇÃO DE PIX (somente Mercado Pago)
async def gerar_pagamento_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    try:
        dados = criar_pagamento_pix(
            valor=obter_valor_plano(plano_nome),
            descricao=f"Assinatura Clipador - {plano_nome}"
        )

        imagem_bytes = base64.b64decode(dados["imagem"])
        imagem_io = BytesIO(imagem_bytes)
        imagem_io.name = "qrcode.png"

        texto = (
            f"💸 *Pagamento via Pix gerado com sucesso!*\n\n"
            f"📦 Plano: *{plano_nome}*\n"
            f"💰 Valor: *R${dados['valor']:.2f}*\n\n"
            "Copie o código abaixo ou escaneie o QR Code:"
        )

        botoes = [
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
        ]

        await query.message.reply_photo(
            photo=imagem_io,
            caption=texto + f"\n\n`{dados['qrcode']}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botoes)
        )

    except Exception as e:
        await query.message.reply_text(
            text=f"❌ Erro ao gerar o pagamento via Pix.\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_pix_{plano_nome.replace(' ', '_')}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
            ]),
            parse_mode="Markdown"
        )

# GERAÇÃO DE CARTÃO (somente Mercado Pago)
async def gerar_pagamento_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE, plano_nome: str):
    query = update.callback_query
    await query.answer()

    try:
        link_checkout = criar_pagamento_cartao(
            valor=obter_valor_plano(plano_nome),
            descricao=f"Assinatura Clipador - {plano_nome}"
        )

        texto = (
            f"💳 *Pagamento via Cartão de Crédito*\n\n"
            f"📦 Plano: *{plano_nome}*\n"
            f"💰 Valor: *R${obter_valor_plano(plano_nome):.2f}*\n\n"
            "Clique abaixo para finalizar a compra:"
        )

        botoes = [
            [InlineKeyboardButton("💳 Pagar com Cartão", url=link_checkout)],
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
        ]

        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")

    except Exception as e:
        await query.edit_message_text(
            text="❌ Erro ao gerar pagamento com cartão. Deseja tentar novamente?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data=f"pagar_cartao_{plano_nome.replace(' ', '_')}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
            ])
        )

# MENU 6: Já paguei (pede e-mail)
async def responder_menu_6(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        # Salva o ID da mensagem de botões para poder editar depois
        context.user_data["mensagem_pagamento_id"] = query.message.message_id

    # Envia uma nova mensagem pedindo o e-mail, respondendo à mensagem do menu
    # para que o menu original não seja apagado.
    nova_msg = await query.message.reply_text(
        "😎 Beleza! Agora me diga qual e-mail você usou para fazer o pagamento:",
        reply_markup=ForceReply(selective=True)
    )
    # Salva o ID da mensagem de "qual seu e-mail" para apagar depois
    context.user_data["mensagem_pedindo_email_id"] = nova_msg.message_id

    return PEDIR_EMAIL

async def pular_pagamento_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # Adiciona 'plano_simulado' como argumento opcional
    """
    Comando de admin para simular um pagamento aprovado e avançar o funil.
    Exclusivo para administradores.
    """
    telegram_id = update.effective_user.id
    if not is_usuario_admin(telegram_id):
        # Encerra o funil para não-administradores, sem enviar mensagem.
        # Se for um comando, responde para o usuário.
        if update.message:
            await update.message.reply_text("❌ Você não tem permissão para usar este comando.")
        return ConversationHandler.END

    plano_simulado = context.args[0] if context.args else "Mensal Plus" # Pega o primeiro argumento ou define um padrão

    # Simula um pagamento aprovado
    email = f"admin_skip_{telegram_id}@clipador.com" # Email dummy para admin skips
    
    # Garante que o usuário exista no DB e tenha um email vinculado para vincular_compra_e_ativar_usuario
    adicionar_usuario(telegram_id, update.effective_user.first_name)
    vincular_email_usuario(telegram_id, email)

    try:
        vincular_compra_e_ativar_usuario(telegram_id, email, plano_simulado, "approved")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao simular ativação da assinatura para admin: {e}")
        return ConversationHandler.END # Encerra o funil em caso de erro para o admin

    await avancar_para_nova_etapa(
        update, context,
        f"✅ Pagamento simulado com sucesso para admin!\n\nPlano assinado: *{plano_simulado}*.\nSeu acesso foi liberado. Agora vamos configurar seu canal privado.",
        [[InlineKeyboardButton("⚙️ Continuar configuração", callback_data="abrir_configurar_canal")]]
    )
    return ConversationHandler.END

async def receber_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe e-mail do usuário ou usa o e-mail já registrado (compra de slot extra)."""
    from core.gateway.kirvano import verificar_status_compra_para_ativacao # Função correta

    # Se o email já foi passado, usa ele. Senão, tenta obter da mensagem do usuário.
    email = context.args[0] if context.args else None
    if not email and update.message:
        # Apaga a mensagem de prompt e a resposta do usuário
        mensagem_pedindo_email_id = context.user_data.pop("mensagem_pedindo_email_id", None)
        if mensagem_pedindo_email_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mensagem_pedindo_email_id)
            except Exception: pass
        try:
            await update.message.delete() # Apaga o e-mail enviado pelo usuário
        except Exception: pass
        email = update.message.text.strip()

    vincular_email_usuario(update.effective_user.id, email) # Mantido, pois associa o email ao usuário no DB

    if not email or "@" not in email or "." not in email:
        await update.message.reply_text(
            f"📧 E-mail informado: {email}\n\n"
            "❌ E-mail inválido ou não informado. Por favor, digite um e-mail válido para continuar.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return PEDIR_EMAIL

    await update.message.chat.send_action(action="typing")

    telegram_id = update.effective_user.id
    
    if email_ja_utilizado_por_outro_usuario(email, telegram_id):
        await update.message.reply_text(
            "❌ Este e-mail já está vinculado a outro usuário.\nVerifique se digitou corretamente ou use outro e-mail.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return PEDIR_EMAIL

    try:
        # Busca a compra mais recente para o e-mail
        compra_db = buscar_pagamento_por_email(email)
        status_compra = compra_db["status"].lower() if compra_db else "not_found"
        plano_real = compra_db["plano"] if compra_db else None
        metodo_pagamento = compra_db["metodo_pagamento"] if compra_db else None
        registrar_log_pagamento(telegram_id, email, plano_real, status_compra)
    except Exception as e:
        print(f"[ERRO] Exceção ao buscar pagamento no DB: {str(e)}")
        await update.message.reply_text(
            "❌ Ocorreu um erro inesperado durante a verificação do pagamento.\nTente novamente mais tarde.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return PEDIR_EMAIL

    # Se o status for final (aprovado, não encontrado, etc.), apaga o menu de pagamento.
    # Se for pendente, o menu será editado, não apagado.
    if status_compra != "pending":
        mensagem_pagamento_id = context.user_data.pop("mensagem_pagamento_id", None)
        if mensagem_pagamento_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mensagem_pagamento_id)
            except Exception: pass

    # Lógica centralizada de tratamento de status
    if status_compra == "approved":
        plano_esperado = context.user_data.get("plano_esperado")

        # Se a compra for de um Slot Extra
        if plano_real == "Slot Extra":
            try:
                adicionar_slot_extra(telegram_id)
                await avancar_para_nova_etapa(
                    update,
                    context,
                    "✅ Slot extra adicionado com sucesso!\n\nVocê já pode configurar um novo streamer.",
                    [[InlineKeyboardButton("🔧 Gerenciar canal", callback_data="abrir_menu_gerenciar_canal")]]
                )
                return ConversationHandler.END
            except Exception as e:
                logger.error(f"Erro ao adicionar slot extra para {telegram_id}: {e}")
                await update.message.reply_text(
                    "❌ Ocorreu um erro ao adicionar seu slot extra. Por favor, contate o suporte.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="abrir_menu_gerenciar_canal")]])
                )
                return ConversationHandler.END
        else: # Se a compra for de um plano de assinatura
            # Se o método de pagamento é FREE, verifica se o usuário é admin
            if metodo_pagamento and metodo_pagamento.upper() == "FREE": # Verifica se é um plano "FREE"
                if not is_usuario_admin(telegram_id):
                    await update.message.reply_text(
                        "❌ Produtos gratuitos só podem ser usados por administradores.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_2")]
                        ])
                    )
                    return PEDIR_EMAIL
                print(f"[DEBUG] Admin {telegram_id} ativando acesso gratuito com e-mail {email}.") # Log para admin
            
            if plano_real != plano_esperado and (not metodo_pagamento or metodo_pagamento.upper() != "FREE"):
                await update.message.reply_text(
                    "❌ O plano selecionado não corresponde ao plano que você comprou.\n"
                    f"Você comprou o plano *{plano_real}*, mas selecionou o *{plano_esperado}*.\n"
                    "Volte e selecione o plano correto.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
                    ])
                )
                return PEDIR_EMAIL
            
            # Mensagem informativa se o plano pago for diferente do selecionado
            if plano_real != plano_esperado:
                await update.message.reply_text(
                    f"⚠️ Você selecionou o plano *{plano_esperado}*, mas seu pagamento foi para o plano *{plano_real}*.\n"
                    f"Sua assinatura foi ativada para o plano *{plano_real}*.",
                    parse_mode="Markdown"
                )

            # Ativa o usuário
            print(f"[DEBUG] Pagamento aprovado para {email}, ativando usuário {telegram_id}...")
            try: # Sempre ativa com o plano_real
                vincular_compra_e_ativar_usuario(telegram_id, email, plano_real, "approved")
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Erro ao ativar sua assinatura: {e}\nPor favor, tente novamente ou contate o suporte.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")], [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]])
                )
                return PEDIR_EMAIL
            
            # Mensagem de sucesso e continuação
            await avancar_para_nova_etapa(
                update,
                context,
                f"✅ Pagamento confirmado com sucesso!\n\n"
                f"Plano assinado: *{plano_real}*.\n"
                f"Seu acesso foi liberado. Agora vamos configurar seu canal privado.",
                [[InlineKeyboardButton("⚙️ Continuar configuração", callback_data="abrir_configurar_canal")]]
            )
            return ConversationHandler.END

    elif status_compra == "pending":
        # Lógica para pagamento pendente
        print("[DEBUG] Pagamento pendente.")
        mensagem_id = context.user_data.get("mensagem_pagamento_id") # Usa .get() para não remover a chave
        chat_id = update.effective_chat.id
        plano_esperado = context.user_data.get("plano_esperado")
        
        botoes = [
            [InlineKeyboardButton("📎 Acessar link de pagamento", url=KIRVANO_LINKS.get(plano_esperado, ""))],
            [InlineKeyboardButton("✅ Já paguei", callback_data="menu_6")],
            [InlineKeyboardButton("🔙 Voltar aos planos", callback_data="menu_2")]
        ]
        texto_pendente = (
            f"📧 E-mail informado: {email}\n\n"
            "🕐 Pagamento ainda pendente.\n"
            "Aguarde a confirmação e clique novamente em 'Já paguei'."
        )
        if mensagem_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=mensagem_id,
                    text=texto_pendente,
                    reply_markup=InlineKeyboardMarkup(botoes)
                )
            except Exception as e:
                print(f"[DEBUG] Falha ao editar mensagem pendente: {e}")
                await update.message.reply_text(texto_pendente, reply_markup=InlineKeyboardMarkup(botoes))
        else:
            await update.message.reply_text(texto_pendente, reply_markup=InlineKeyboardMarkup(botoes))
        return PEDIR_EMAIL

    elif status_compra == "not_found":
        print("[DEBUG] Pagamento não encontrado.")
        await update.message.reply_text(
            "❌ Pagamento não encontrado para este e-mail.\nVerifique se digitou corretamente.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Corrigir e-mail", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
        return PEDIR_EMAIL

    else: # Status como REFUNDED, EXPIRED, CHARGEBACK, ou qualquer outro não tratado
        print(f"[DEBUG] Pagamento com status não aprovado: {status_compra}")
        await update.message.reply_text(
            f"❌ O pagamento para o e-mail *{email}* não está aprovado ou está em um status inválido ({status_compra}).\n"
            "Por favor, verifique o status da sua compra ou contate o suporte.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_2")]
            ])
        )
    return PEDIR_EMAIL

async def pular_configuracao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Encerra a conversa de configuração para o admin configurar depois."""
    query = update.callback_query
    telegram_id = update.effective_user.id
    await query.answer()

    await query.edit_message_text(
        "✅ Ok, entendido!\n\n"
        "Você pode iniciar a configuração do seu canal a qualquer momento usando o comando /start."
    )
    return ConversationHandler.END

from telegram.ext import CallbackQueryHandler
# HANDLER PARA MENU DE CONFIGURAÇÃO DO CANAL

pagamento_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(responder_menu_6, pattern="^menu_6$")],
    states={
        PEDIR_EMAIL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_email),
            CallbackQueryHandler(responder_menu_6, pattern="^menu_6$"), # Adicionado para o botão "Corrigir e-mail"
            CommandHandler("pular", pular_pagamento_admin), # Adiciona o comando /pular para admins
            CallbackQueryHandler(pular_configuracao_callback, pattern="^pular_configuracao$")
        ],
    },
    fallbacks=[CommandHandler("start", responder_inicio)], # Usa a nova função centralizada
    per_message=False
)


# ROTEADOR
async def roteador_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pagar_pix_"):
        plano = data.replace("pagar_pix_", "").replace("_", " ")
        await gerar_pagamento_pix(update, context, plano)

    elif data.startswith("pagar_cartao_"):
        plano = data.replace("pagar_cartao_", "").replace("_", " ")
        await gerar_pagamento_cartao(update, context, plano)

    elif data == "abrir_configurar_canal":
        from chat_privado.menus.menu_configurar_canal import menu_configurar_canal # Importação local para quebrar o ciclo
        print("[DEBUG] Callback abrir_configurar_canal acionado. Roteando...")
        await update.callback_query.answer()
        await menu_configurar_canal(update, context)