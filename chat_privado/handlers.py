from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

from chat_privado.usuarios import registrar_usuario

from chat_privado.menus.menu_configurar_canal import configurar_canal_conversa

# Menus principais
from chat_privado.menus.menu_inicial import responder_inicio, voltar_ao_menu
from chat_privado.menus.menu_comandos import responder_help

# Menus interativos
from chat_privado.menus.menu_callback import (
    responder_menu_1,
    responder_menu_2,
    responder_menu_3,
    responder_menu_4_mensal,
    responder_menu_4_plus,
    responder_menu_4_anual,
    responder_menu_6_confirmar,
    responder_menu_7_configurar
)

# Menus de pagamento
from chat_privado.menus import menu_pagamento
from chat_privado.menus.menu_pagamento import (
    responder_menu_5_mensal,
    responder_menu_5_plus,
    responder_menu_5_anual,
    roteador_pagamento,
    responder_menu_6,
    PEDIR_EMAIL,
    receber_email
)

def registrar_handlers(application):
    # 🟢 Mensagem inicial e comandos
    application.add_handler(CommandHandler("start", responder_inicio, block=False))
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
            lambda update, context: registrar_usuario(update.effective_user.id, update.effective_user.full_name)
        )
    )
    application.add_handler(CommandHandler("help", responder_help))

    # 🧭 Comandos diretos equivalentes aos botões
    application.add_handler(CommandHandler("menu", voltar_ao_menu))
    application.add_handler(CommandHandler("como_funciona", responder_menu_1))
    application.add_handler(CommandHandler("planos", responder_menu_2))
    application.add_handler(CommandHandler("assinar", responder_menu_3))

    # 📋 Menus interativos via Callback
    application.add_handler(CallbackQueryHandler(voltar_ao_menu, pattern="^menu_0$"))
    application.add_handler(CallbackQueryHandler(responder_menu_1, pattern="^menu_1$"))
    application.add_handler(CallbackQueryHandler(responder_menu_2, pattern="^menu_2$"))
    application.add_handler(CallbackQueryHandler(responder_menu_3, pattern="^menu_3$"))

    # Menu 4 – Escolha de plano
    application.add_handler(CallbackQueryHandler(responder_menu_4_mensal, pattern="^menu_4_mensal$"))
    application.add_handler(CallbackQueryHandler(responder_menu_4_plus, pattern="^menu_4_plus$"))
    application.add_handler(CallbackQueryHandler(responder_menu_4_anual, pattern="^menu_4_anual$"))

    # Menu 5 – Pagamento
    application.add_handler(CallbackQueryHandler(responder_menu_5_mensal, pattern="^menu_5_mensal$"))
    application.add_handler(CallbackQueryHandler(responder_menu_5_plus, pattern="^menu_5_plus$"))
    application.add_handler(CallbackQueryHandler(responder_menu_5_anual, pattern="^menu_5_anual$"))
    application.add_handler(CallbackQueryHandler(roteador_pagamento, pattern="^pagar_.*$"))

    # Menu 6 – Já paguei
    application.add_handler(CallbackQueryHandler(responder_menu_6_confirmar, pattern="^menu_6_confirmar$"))

    # Menu 7 – Configuração do canal
    application.add_handler(CallbackQueryHandler(responder_menu_7_configurar, pattern="^menu_7_configurar$"))
    application.add_handler(CallbackQueryHandler(responder_menu_7_configurar, pattern="^continuar_configuracao$"))
    # Acesso direto ao menu de configuração do canal pelo botão principal
    application.add_handler(CallbackQueryHandler(responder_menu_7_configurar, pattern="^configurar_canal$"))
    from chat_privado.menus.menu_configurar_canal import menu_configurar_canal
    application.add_handler(CallbackQueryHandler(menu_configurar_canal, pattern="^abrir_configurar_canal$"))

    # Conversa para receber o e-mail do cliente
    application.add_handler(
        ConversationHandler(
            entry_points=[CallbackQueryHandler(responder_menu_6, pattern="^menu_6$")],
            states={PEDIR_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_email)]},
            fallbacks=[MessageHandler(filters.ALL, receber_email)],
        )
    )

    # Tratamento direto para "Tentar novamente" no menu_6 após erro
    application.add_handler(CallbackQueryHandler(responder_menu_6, pattern="^menu_6$"))

    # Conversa para configuração do canal após pagamento validado
    application.add_handler(configurar_canal_conversa())

    application.add_handler(CommandHandler("start", responder_inicio, block=False))

    # Handler temporário para testar se o menu_configurar_canal está sendo chamado corretamente
    from chat_privado.menus.menu_configurar_canal import menu_configurar_canal
    application.add_handler(CallbackQueryHandler(menu_configurar_canal, pattern="^testar_menu_config$"))
