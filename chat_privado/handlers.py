from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Menus principais
from chat_privado.menus.menu_inicial import responder_inicio

from chat_privado.menus.menu_callback import (
    responder_menu_0,
    responder_menu_1,
    responder_menu_2,
    responder_menu_3,
    responder_menu_4_mensal,
    responder_menu_4_plus,
    responder_menu_4_anual,
    responder_menu_6_confirmar
)
from chat_privado.menus.menu_comandos import responder_help

# Menus de pagamento
from chat_privado.menus.menu_pagamento import (
    responder_menu_5_mensal,
    responder_menu_5_plus,
    responder_menu_5_anual,
    roteador_pagamento
)

def registrar_handlers(application):
    # 🟢 Mensagem inicial e texto comum
    application.add_handler(CommandHandler("start", responder_inicio))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_inicio))

    # 🧭 Comandos diretos equivalentes aos botões
    application.add_handler(CommandHandler("menu", responder_menu_0))
    application.add_handler(CommandHandler("como_funciona", responder_menu_1))
    application.add_handler(CommandHandler("planos", responder_menu_2))
    application.add_handler(CommandHandler("assinar", responder_menu_3))
    application.add_handler(CommandHandler("help", responder_help))

    # 📋 Menus interativos via Callback
    application.add_handler(CallbackQueryHandler(responder_menu_0, pattern="^menu_0$"))
    application.add_handler(CallbackQueryHandler(responder_menu_1, pattern="^menu_1$"))
    application.add_handler(CallbackQueryHandler(responder_menu_2, pattern="^menu_2$"))
    application.add_handler(CallbackQueryHandler(responder_menu_3, pattern="^menu_3$"))
    application.add_handler(CallbackQueryHandler(responder_menu_4_mensal, pattern="^menu_4_mensal$"))
    application.add_handler(CallbackQueryHandler(responder_menu_4_plus, pattern="^menu_4_plus$"))
    application.add_handler(CallbackQueryHandler(responder_menu_4_anual, pattern="^menu_4_anual$"))

    # 💳 Geração de pagamento Pix ou Cartão
    application.add_handler(CallbackQueryHandler(responder_menu_5_mensal, pattern="^menu_5_mensal$"))
    application.add_handler(CallbackQueryHandler(responder_menu_5_plus, pattern="^menu_5_plus$"))
    application.add_handler(CallbackQueryHandler(responder_menu_5_anual, pattern="^menu_5_anual$"))
    application.add_handler(CallbackQueryHandler(roteador_pagamento, pattern="^pagar_.*$"))

    application.add_handler(CallbackQueryHandler(responder_menu_6_confirmar, pattern="^menu_6$"))
