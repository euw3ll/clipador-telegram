from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# Importar handlers dos menus
from .menus.menu_inicial import responder_inicio
from .menus.menu_callback import (
    responder_menu_1,
    responder_menu_2,
    responder_menu_3,
    responder_menu_4_mensal,
    responder_menu_4_plus,
    responder_menu_4_anual,
)
from .menus.menu_pagamento import (
    pagamento_conversation_handler,
    roteador_pagamento,
    responder_menu_5_mensal,
    responder_menu_5_plus,
    responder_menu_5_anual,
)
from .menus.menu_configurar_canal import configurar_canal_conversa
from .menus.menu_gerenciamento import (
    gerenciar_streamers_conversa,
    configurar_manual_conversa,
    abrir_menu_gerenciar_canal,
    ver_plano_atual,
    comprar_slot_extra,
    abrir_menu_alterar_modo,
    salvar_novo_modo,
    placeholder_callback,
)
from .menus.menu_comandos import responder_help

def registrar_handlers(app: Application):
    """Registra todos os command, callback e conversation handlers do chat privado."""

    # 1. Handlers de Conversa (devem vir primeiro para ter prioridade)
    app.add_handler(pagamento_conversation_handler)
    app.add_handler(configurar_canal_conversa())
    app.add_handler(gerenciar_streamers_conversa())
    app.add_handler(configurar_manual_conversa())

    # 2. Comandos
    app.add_handler(CommandHandler("start", responder_inicio))
    app.add_handler(CommandHandler("help", responder_help))

    # 3. Handlers de CallbackQuery (menus)
    app.add_handler(CallbackQueryHandler(responder_inicio, pattern="^menu_0$"))
    app.add_handler(CallbackQueryHandler(responder_menu_1, pattern="^menu_1$"))
    app.add_handler(CallbackQueryHandler(responder_menu_2, pattern="^menu_2$"))
    app.add_handler(CallbackQueryHandler(responder_menu_3, pattern="^menu_3$"))
    app.add_handler(CallbackQueryHandler(responder_menu_4_mensal, pattern="^menu_4_mensal$"))
    app.add_handler(CallbackQueryHandler(responder_menu_4_plus, pattern="^menu_4_plus$"))
    app.add_handler(CallbackQueryHandler(responder_menu_4_anual, pattern="^menu_4_anual$"))
    app.add_handler(CallbackQueryHandler(responder_menu_5_mensal, pattern="^menu_5_mensal$"))
    app.add_handler(CallbackQueryHandler(responder_menu_5_plus, pattern="^menu_5_plus$"))
    app.add_handler(CallbackQueryHandler(responder_menu_5_anual, pattern="^menu_5_anual$"))
    app.add_handler(CallbackQueryHandler(roteador_pagamento, pattern="^pagar_"))
    app.add_handler(CallbackQueryHandler(abrir_menu_gerenciar_canal, pattern="^abrir_menu_gerenciar_canal$"))
    app.add_handler(CallbackQueryHandler(ver_plano_atual, pattern="^ver_plano_atual$"))
    app.add_handler(CallbackQueryHandler(comprar_slot_extra, pattern="^comprar_slot_extra$"))
    app.add_handler(CallbackQueryHandler(abrir_menu_alterar_modo, pattern="^gerenciar_modo$"))
    app.add_handler(CallbackQueryHandler(salvar_novo_modo, pattern="^novo_modo_"))
    app.add_handler(CallbackQueryHandler(placeholder_callback, pattern="^placeholder_callback$"))