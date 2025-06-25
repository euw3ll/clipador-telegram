from telegram import Update
from telegram.ext import ContextTypes
from core.database import (
    is_usuario_admin, 
    marcar_configuracao_completa,
    buscar_usuario_por_id,
    is_configuracao_completa,
    salvar_link_canal,
    buscar_configuracao_canal
)
from core.telethon_criar_canal import criar_canal_telegram
from core.telethon_gerenciar_canal import excluir_canal_telegram
from core.image_utils import gerar_imagem_canal_personalizada
from core.database import resetar_estado_usuario_para_teste # Nova função para resetar o estado do usuário

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o menu de ajuda para administradores."""
    admin_id = update.effective_user.id
    if not is_usuario_admin(admin_id):
        await update.message.reply_text("❌ Este comando é exclusivo para administradores.")
        return

    texto_ajuda = (
        "🛠️ *Painel de Controle do Administrador*\n\n"
        "Comandos disponíveis:\n\n"
        "`/resetuser <ID>`\n"
        "↳ Limpa a configuração de um usuário, permitindo que ele refaça o funil.\n\n"
        "`/createchannel <ID>`\n"
        "↳ Cria manualmente um canal para um usuário e marca sua configuração como completa.\n\n"
        "`/delchannel <ID>`\n"
        "↳ Exclui o canal de um usuário do Telegram e do banco de dados."
    )
    await update.message.reply_text(texto_ajuda, parse_mode="Markdown")


async def reset_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando de admin para resetar o estado de configuração de um usuário.
    Uso: /resetuser <telegram_id>
    """
    admin_id = update.effective_user.id
    if not is_usuario_admin(admin_id):
        await update.message.reply_text("❌ Este comando é exclusivo para administradores.")
        return

    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Formato: `/resetuser <telegram_id>`", parse_mode="Markdown")
        return

    try:
        resetar_estado_usuario_para_teste(target_id)
        await update.message.reply_text(
            f"✅ Estado do usuário `{target_id}` resetado com sucesso.\n"
            "A configuração do canal foi removida e ele pode iniciar o funil novamente.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao resetar o usuário: {e}")

async def create_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cria manualmente um canal para um usuário."""
    admin_id = update.effective_user.id
    if not is_usuario_admin(admin_id):
        await update.message.reply_text("❌ Este comando é exclusivo para administradores.")
        return

    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Formato: `/createchannel <telegram_id>`", parse_mode="Markdown")
        return

    if is_configuracao_completa(target_id):
        await update.message.reply_text(f"⚠️ O usuário `{target_id}` já possui um canal configurado.", parse_mode="Markdown")
        return

    usuario_db = buscar_usuario_por_id(target_id)
    if not usuario_db or not usuario_db.get('nome'):
        await update.message.reply_text(f"❌ Usuário com ID `{target_id}` não encontrado no banco de dados.", parse_mode="Markdown")
        return

    try:
        await update.message.reply_text(f"⏳ Gerando imagem de perfil para o usuário {target_id}...")
        caminho_imagem_personalizada = await gerar_imagem_canal_personalizada(target_id, context)

        await update.message.reply_text(f"⏳ Criando canal para o usuário {target_id}...")
        id_canal, link_canal = await criar_canal_telegram(
            nome_usuario=usuario_db['nome'], telegram_id=target_id, caminho_imagem=caminho_imagem_personalizada
        )
        
        # Atualiza o banco de dados
        salvar_link_canal(target_id, id_canal, link_canal)
        marcar_configuracao_completa(target_id, True)

        await update.message.reply_text(
            f"✅ Canal criado com sucesso para o usuário `{target_id}`!\n"
            f"Link: {link_canal}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao criar o canal: {e}")

async def delete_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exclui o canal de um usuário."""
    admin_id = update.effective_user.id
    if not is_usuario_admin(admin_id):
        await update.message.reply_text("❌ Este comando é exclusivo para administradores.")
        return

    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Formato: `/delchannel <telegram_id>`", parse_mode="Markdown")
        return

    config = buscar_configuracao_canal(target_id)
    if not config or not config.get('id_canal_telegram'):
        await update.message.reply_text(f"⚠️ O usuário `{target_id}` não possui um canal configurado para exclusão.", parse_mode="Markdown")
        return

    try:
        id_canal_a_excluir = int(config['id_canal_telegram'])
        await update.message.reply_text(f"⏳ Excluindo o canal `{id_canal_a_excluir}` do usuário `{target_id}`... Por favor, aguarde.")
        
        sucesso_telethon = await excluir_canal_telegram(id_canal_a_excluir)

        if sucesso_telethon:
            # Limpa o banco de dados
            deletar_configuracao_canal(target_id)
            marcar_configuracao_completa(target_id, False)
            await update.message.reply_text(
                f"✅ Canal `{id_canal_a_excluir}` do usuário `{target_id}` foi excluído com sucesso do Telegram e do banco de dados.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Falha ao excluir o canal `{id_canal_a_excluir}` via Telethon. A configuração no banco de dados não foi alterada.",
                parse_mode="Markdown"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao excluir o canal: {e}")