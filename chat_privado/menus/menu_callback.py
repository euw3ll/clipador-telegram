from telegram.ext import CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from core.pagamento import consultar_pagamento
from chat_privado.menus.menu_configurar_canal import menu_configurar_canal, responder_menu_7_configurar
from core.database import atualizar_telegram_id_simples, usuario_ja_usou_teste
from chat_privado.usuarios import get_nivel_usuario # Importar get_nivel_usuario
from configuracoes import PLANOS_PRECOS, TESTE_GRATUITO_ATIVO
from core.database import buscar_configuracao_canal

from telegram.error import BadRequest

def atualizar_usuario_contexto(update, context):
    telegram_user_id = update.effective_user.id
    context.user_data["telegram_id"] = telegram_user_id
    atualizar_telegram_id_simples(telegram_user_id, telegram_user_id)

# menu_0 → Menu inicial (roteador)
async def responder_menu_0(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sempre obter o nível mais atualizado do banco de dados
    nivel = get_nivel_usuario(update.effective_user.id)
    tipo_plano = context.user_data.get("tipo_plano", "indefinido")
    atualizar_usuario_contexto(update, context)
    if nivel == 2:
        await responder_menu_assinante(update, context)
    elif nivel == 3:
        await responder_menu_ex_assinante(update, context)
    elif nivel == 999:
        await responder_menu_admin(update, context)
    else:
        await responder_menu_novo_usuario(update, context)

# menu_padrao → Menu inicial (callback renomeado)
async def responder_menu_padrao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    atualizar_usuario_contexto(update, context)
    await responder_menu_0(update, context)


# Menus por nível de usuário
async def responder_menu_novo_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()
    texto = (
        "👋 *Bem-vindo ao Clipador!*\n\n"
        "Eu sou o bot que vai transformar seus clipes em ouro (ou pelo menos em muitos views)!\n\n"
        "Escolha uma opção abaixo para descobrir mais:"
    )
    botoes = [
        [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
        [InlineKeyboardButton("💰 Ver planos", callback_data="menu_3")],
        [InlineKeyboardButton("🚀 Assinar", callback_data="menu_3")],
    ]
    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


async def responder_menu_assinante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()
    texto = (
        "🎉 *Menu do Assinante Clipador!*\n\n"
        "Você já faz parte do clube dos clippers profissionais!\n"
        "O que deseja fazer agora? (Além de ficar famoso, claro 😎)"
    )
    botoes = [
        [InlineKeyboardButton("📡 Ver canal", callback_data="abrir_canal")],
        [InlineKeyboardButton("🔧 Configurar canal", callback_data="menu_7_configurar")],
        [InlineKeyboardButton("📝 Plano atual", callback_data="menu_3")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]
    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


async def responder_menu_ex_assinante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()
    texto = (
        "😢 *Sua assinatura expirou!*\n\n"
        "Mas não se preocupe, ainda dá tempo de voltar para o lado dos clippers felizes.\n"
        "Veja como funciona ou confira nossos planos para voltar com tudo!"
    )
    botoes = [
        [InlineKeyboardButton("📚 Como funciona", callback_data="menu_1")],
        [InlineKeyboardButton("💰 Ver planos", callback_data="menu_3")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]
    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


async def responder_menu_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()
    texto = (
        "🛠️ *Painel Administrativo Clipador*\n\n"
        "Bem-vindo, mestre dos clipes! Aqui estão suas ferramentas secretas:"
    )
    botoes = [
        [InlineKeyboardButton("👥 Ver usuários", callback_data="admin_ver_usuarios")],
        [InlineKeyboardButton("📈 Gerar relatório", callback_data="admin_gerar_relatorio")],
        [InlineKeyboardButton("💳 Pagamentos", callback_data="admin_pagamentos")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]
    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


# menu_1 → Como funciona
async def responder_menu_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    texto = (
        "📚 *COMO FUNCIONA O CLIPADOR*\n\n"
        "🎥 O Clipador monitora automaticamente os streamers que você escolher e envia *os melhores momentos das lives* direto no seu canal no Telegram.\n\n"
        "🔄 *Monitoramento 24h/dia*, sem precisar fazer nada.\n"
        "🧠 O bot identifica grupos de clipes virais e filtra o que realmente importa.\n"
        "📥 Você pode ver o preview do clipe e fazer o download para subir na sua plataforma de preferência.\n\n"
        "💡 *O que são slots?*\n"
        "Cada slot representa 1 streamer monitorado.\n"
        "Você pode contratar mais slots extras para monitorar múltiplos streamers no mesmo canal.\n\n"
        "📊 *Modos de monitoramento:*\n"
        "- Modo Louco 🔥 (envia tudo que viraliza)\n"
        "- Modo Padrão 🎯 (equilíbrio entre qualidade e frequência)\n"
        "- Modo Cirúrgico 🧬 (só clipes realmente bombásticos)"
    )

    botoes = [
        [InlineKeyboardButton("💸 Ver planos", callback_data="menu_2")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")],
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)

# menu_2 → Planos disponíveis
async def responder_menu_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    texto = (
        f"💸 *PLANOS DO CLIPADOR*\n\n"
        f"✅ *Mensal Solo* — R${PLANOS_PRECOS.get('Mensal Solo', 0.0):.2f}/mês\n"
        "• 1 streamer monitorado\n"
        "• Troca de streamer 1x/mês\n"
        "• Máximo 1 slot extra\n\n"
        f"🏆 *Mensal Plus* — R${PLANOS_PRECOS.get('Mensal Plus', 0.0):.2f}/mês\n"
        "• Até 3 canais monitorados\n"
        "• Ideal pra clippers/agências\n"
        "• Até 3 slots extras\n\n"
        f"👑 *Anual Pro* — R${PLANOS_PRECOS.get('Anual Pro', 0.0):.2f}/ano\n"
        "• 3 canais + 1 slot bônus\n"
        "• Economia de 2 meses\n"
        "• Até 5 slots extras\n\n"
        f"➕ *Slot Extra:* R${PLANOS_PRECOS.get('Slot Extra', 0.0):.2f} (pagamento único para qualquer plano)"
    )

    botoes = [
        [InlineKeyboardButton("📝 Quero assinar", callback_data="menu_3")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")],
    ]
    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


# menu_3 → Lista de Planos
async def responder_menu_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    texto = (
        f"🧾 *PLANOS DO CLIPADOR*\n\n"
        f"✅ *Mensal Solo* — R${PLANOS_PRECOS.get('Mensal Solo', 0.0):.2f}/mês\n"
        "• 1 streamer monitorado\n"
        "• Troca de streamer 1x/mês\n"
        "• Máximo 1 slot extra\n\n"
        f"🏆 *Mensal Plus* — R${PLANOS_PRECOS.get('Mensal Plus', 0.0):.2f}/mês\n"
        "• Até 3 canais monitorados\n"
        "• Ideal pra clippers/agências\n"
        "• Até 3 slots extras\n\n"
        f"👑 *Anual Pro* — R${PLANOS_PRECOS.get('Anual Pro', 0.0):.2f}/ano\n"
        "• 3 canais + 1 slot bônus\n"
        "• Economia de 2 meses\n"
        "• Até 5 slots extras\n\n"
        f"➕ *Slot Extra:* R${PLANOS_PRECOS.get('Slot Extra', 0.0):.2f} (pagamento único para qualquer plano)"
    )

    botoes = [
        [InlineKeyboardButton("💳 Mensal Solo", callback_data="menu_4_mensal")],
        [InlineKeyboardButton("🏆 Mensal Plus", callback_data="menu_4_plus")],
        [InlineKeyboardButton("👑 Anual Pro", callback_data="menu_4_anual")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
    ]

    # NOVO: Adiciona o botão de teste gratuito se as condições forem atendidas
    telegram_id = update.effective_user.id
    if TESTE_GRATUITO_ATIVO and not usuario_ja_usou_teste(telegram_id):
        # Insere o botão de teste antes dos planos pagos
        botoes.insert(0, [InlineKeyboardButton("⭐ Teste Gratuito (3 dias)", callback_data="menu_5_teste")])

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


# menu_4 → Resumo plano Mensal Solo
async def responder_menu_4_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    texto = (
        f"*📝 RESUMO DO PLANO MENSAL SOLO*\n\n"
        f"💰 R$ {PLANOS_PRECOS.get('Mensal Solo', 0.0):.2f}/mês\n"
        "🔹 1 streamer monitorado\n"
        "🔄 Troca de streamer 1x por mês\n"
        f"➕ Máximo 1 slot extra (R${PLANOS_PRECOS.get('Slot Extra', 0.0):.2f} - pagamento único)\n"
        "📅 Renovação mensal\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Escolher este plano", callback_data="menu_5_mensal")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


# menu_4 → Resumo plano Mensal Plus
async def responder_menu_4_plus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    texto = (
        f"*📝 RESUMO DO PLANO MENSAL PLUS*\n\n"
        f"💰 R$ {PLANOS_PRECOS.get('Mensal Plus', 0.0):.2f}/mês\n"
        "🔹 Até 3 streamers monitorados\n"
        "📦 Ideal para agências/clippers\n"
        f"➕ Até 3 slots adicionais (R${PLANOS_PRECOS.get('Slot Extra', 0.0):.2f} cada - pagamento único)\n"
        "📅 Renovação mensal\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Escolher este plano", callback_data="menu_5_plus")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


# menu_4 → Resumo plano Anual Pro
async def responder_menu_4_anual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    texto = (
        f"*📝 RESUMO DO PLANO ANUAL PRO*\n\n"
        f"💰 R$ {PLANOS_PRECOS.get('Anual Pro', 0.0):.2f}/ano\n"
        "🔹 3 streamers monitorados + 1 slot bônus\n"
        "🎁 Economia de 2 meses\n"
        f"➕ Até 5 slots adicionais (R${PLANOS_PRECOS.get('Slot Extra', 0.0):.2f} cada - pagamento único)\n"
        "📅 Renovação anual\n\n"
        "Deseja continuar com esse plano?"
    )

    botoes = [
        [InlineKeyboardButton("✅ Escolher este plano", callback_data="menu_5_anual")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="menu_3")]
    ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode=ParseMode.MARKDOWN)


# menu_6 → Confirmação de pagamento
from core.pagamento import consultar_pagamento
from chat_privado.menus.menu_configurar_canal import menu_configurar_canal


async def responder_menu_6_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    pagamento_id = context.user_data.get("id_pagamento")

    if not pagamento_id:
        await query.edit_message_text(
            "❌ Nenhum pagamento encontrado.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Voltar ao início", callback_data="menu_0")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    status = consultar_pagamento(pagamento_id)

    if status == "approved":
        await query.edit_message_text("✅ Pagamento confirmado! Vamos configurar seu canal...")
        await menu_configurar_canal(update, context)

    elif status == "pending":
        await query.edit_message_text(
            "⏳ O pagamento ainda não foi identificado.\n"
            "Isso pode levar alguns minutos, tente novamente em instantes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Verificar novamente", callback_data="menu_6")],
                [InlineKeyboardButton("🔙 Voltar ao início", callback_data="menu_0")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(
            f"❌ Ocorreu um erro ao consultar o pagamento (status: {status})",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Tentar novamente", callback_data="menu_0")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )

async def responder_menu_7_configurar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    atualizar_usuario_contexto(update, context)
    await query.answer()

    telegram_id = context.user_data.get("telegram_id")
    configurado = buscar_configuracao_canal(telegram_id)

    if configurado and configurado.get("streamers_monitorados"):
        texto = f"⚙️ E aí, meu assinante favorito?\n\nSeu canal já está configurado com sucesso!\nO que deseja fazer agora?"
        botoes = [
            [InlineKeyboardButton("🎯 Streamers", callback_data="alterar_streamer")],
            [InlineKeyboardButton("⚙️ Modo de monitoramento", callback_data="alterar_modo_monitoramento")],
            [InlineKeyboardButton("➕ Adicionar slot", callback_data="adicionar_slot")],
            [InlineKeyboardButton("🔑 Reconfigurar chaves da Twitch", callback_data="iniciar_envio_twitch")],
            [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
        ]
    else:
        texto = "🔧 Vamos começar a configuração do seu canal personalizado."
        botoes = [
            [InlineKeyboardButton("➡️ Continuar", callback_data="iniciar_envio_twitch")],
            [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="menu_0")]
        ]

    try:
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes))
    except BadRequest:
        await query.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(botoes))


# Registrar handler para menu_7_configurar
def registrar_menu_configurar(application):
    application.add_handler(CallbackQueryHandler(responder_menu_7_configurar, pattern="^menu_7_configurar$"))

# Handlers para os submenus do botão "Configurar canal"
def registrar_submenus_configuracao(application):
    application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer("🚧 Em breve: Alterar streamer!"), pattern="^alterar_streamer$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer("🚧 Em breve: Alterar modo de monitoramento!"), pattern="^alterar_modo_monitoramento$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer("🚧 Em breve: Adicionar slot!"), pattern="^adicionar_slot$"))
    application.add_handler(CallbackQueryHandler(responder_menu_7_configurar, pattern="^configurar_chaves_twitch$"))


# Handler para iniciar envio twitch
async def responder_menu_iniciar_envio_twitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "🧩 Vamos configurar seu Clipador!\n\n"
        "Para funcionar, você precisa criar um app na Twitch com as seguintes credenciais:\n\n"
        "1️⃣ Vá em https://dev.twitch.tv/console/apps\n"
        "2️⃣ Clique em *Register Your Application*\n"
        "3️⃣ Nomeie como quiser\n"
        "4️⃣ Redirecione para: `https://localhost`\n"
        "5️⃣ Selecione 'Chat Bot'\n\n"
        "Depois de criar, me envie:\n"
        "- `Client ID`\n"
        "- `Client Secret`\n\n"
        "Pode colar aqui mesmo, eu vou te guiando! 😎"
    )

    try:
        await query.edit_message_text(text=texto, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await query.message.reply_text(text=texto, parse_mode=ParseMode.MARKDOWN)


def registrar_menu_iniciar_envio_twitch(application):
    application.add_handler(CallbackQueryHandler(responder_menu_iniciar_envio_twitch, pattern="^iniciar_envio_twitch$"))