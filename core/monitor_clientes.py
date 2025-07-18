import asyncio
import time
from typing import TYPE_CHECKING
from datetime import datetime, timezone, timedelta
import logging 
import httpx
from telegram import error as telegram_error

from core.database import (
    buscar_usuarios_ativos_configurados,
    registrar_grupo_enviado,
    verificar_grupo_ja_enviado,
    registrar_clipe_chefe_enviado,
    verificar_clipe_chefe_ja_enviado,
    obter_status_streamer,
    atualizar_status_streamer,
    obter_ou_criar_config_notificacao,
    buscar_usuarios_para_notificar_expiracao,
    atualizar_ultimo_aviso_expiracao,
    desativar_assinatura_por_email,
    buscar_usuario_por_id,
)
from canal_gratuito.core.twitch import TwitchAPI # Reutilizando a TwitchAPI
from canal_gratuito.core.monitor import ( # Reutilizando funções e o dicionário de modos
    agrupar_clipes_por_proximidade,
    get_time_minutes_ago,
    eh_clipe_ao_vivo_real,
    MODOS_MONITORAMENTO,
    minimo_clipes_por_viewers, # Importa a função dinâmica
)
from core.limpeza import executar_limpeza_completa

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from telegram.ext import Application
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def verificar_expiracoes_assinaturas(application: "Application"):
    """Verifica assinaturas próximas da expiração e envia lembretes."""
    logger.info("⏳ Verificando expiração de assinaturas...")
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup # Importação local
    usuarios_a_notificar = buscar_usuarios_para_notificar_expiracao()
    
    botao_renovar = InlineKeyboardButton("💸 Renovar Assinatura", callback_data="menu_2")
    keyboard = InlineKeyboardMarkup([[botao_renovar]])

    for usuario in usuarios_a_notificar:
        telegram_id = usuario['telegram_id']
        dias_restantes = usuario['dias_restantes']

        # NOVO: Buscar dados completos do usuário para saber o plano
        user_data = buscar_usuario_por_id(telegram_id)
        if not user_data:
            logger.warning(f"Usuário {telegram_id} para notificação de expiração não encontrado no DB. Pulando.")
            continue
        
        plano = user_data.get('plano_assinado')
        is_trial = plano == "Teste Gratuito"

        mensagem = ""
        dias_aviso = -1 # Valor sentinela

        # Lógica de mensagens para Teste Gratuito
        if is_trial:
            if dias_restantes <= 0:
                dias_aviso = 0
                mensagem = (
                    "🔴 *Seu período de teste gratuito terminou!* 🔴\n\n"
                    "Seu canal e suas configurações foram removidos. Para continuar usando o Clipador e criar um novo canal, "
                    "assine um de nossos planos."
                )
            elif dias_restantes == 1:
                dias_aviso = 1
                mensagem = (
                    "⚠️ *Seu teste gratuito termina em menos de 24 horas!* ⚠️\n\n"
                    "Não perca seu acesso! Assine agora para manter seu canal e continuar "
                    "recebendo os melhores clipes sem interrupção."
                )
            elif dias_restantes <= 3:
                dias_aviso = 3
                mensagem = (
                    "🔔 *Seu teste gratuito expira em 3 dias!* 🔔\n\n"
                    "Gostou do que viu? Assine um de nossos planos para garantir que seu canal continue ativo "
                    "após o período de teste."
                )
        # Lógica de mensagens para planos pagos (existente)
        else:
            if dias_restantes <= 0:
                dias_aviso = 0
                mensagem = (
                    "🔴 *Sua assinatura expirou!* 🔴\n\n"
                    "Seu acesso foi desativado. Para voltar a receber os melhores clipes, "
                    "renove sua assinatura agora mesmo."
                )
            elif dias_restantes == 1:
                dias_aviso = 1
                mensagem = (
                    "⚠️ *Atenção: Sua assinatura expira em 1 dia!* ⚠️\n\n"
                    "Não perca o acesso ao seu canal de clipes. Renove agora para continuar "
                    "recebendo os melhores momentos das lives sem interrupção."
                )
            elif dias_restantes <= 3:
                dias_aviso = 3
                mensagem = (
                    "🔔 *Lembrete: Sua assinatura expira em 3 dias!* 🔔\n\n"
                    "Garanta que seu canal continue ativo. Renove sua assinatura para não "
                    "perder nenhum clipe viral."
                )
            elif dias_restantes <= 7:
                dias_aviso = 7
                mensagem = (
                    "👋 Olá! Sua assinatura do Clipador expira em 7 dias.\n\n"
                    "Para garantir que você não perca o acesso, você já pode renovar seu plano."
                )
        
        if mensagem and dias_aviso != -1:
            try:
                await application.bot.send_message(chat_id=telegram_id, text=mensagem, parse_mode="Markdown", reply_markup=keyboard)
                logger.info(f"✅ Lembrete de expiração ({dias_aviso} dias) enviado para o usuário {telegram_id}.")
                atualizar_ultimo_aviso_expiracao(telegram_id, dias_aviso)

                # Se a assinatura expirou, envia um aviso no grupo e impede novos envios
                if dias_aviso == 0: # Removemos a lógica de desativação e exclusão
                    chat_id = user_data.get("id_canal_telegram")
                    if chat_id:
                        await application.bot.send_message(chat_id=chat_id, text=f"🔴 A assinatura do Clipador expirou. Não enviaremos mais clipes por enquanto. Renove para continuar!", parse_mode="Markdown")
                        logger.info(f"🔴 Assinatura do usuário {telegram_id} expirou. Notificação de expiração enviada ao grupo.")
                    else:
                        logger.warning(
                            f"Assinatura do usuário {telegram_id} expirou, mas o chat_id não foi encontrado. Não foi possível notificar o grupo."
                        )
            except telegram_error.TelegramError as e:
                logger.error(f"❌ Falha ao enviar lembrete de expiração para {telegram_id}: {e}")

# Intervalo de monitoramento para cada cliente (em segundos)
INTERVALO_MONITORAMENTO_CLIENTE = 60 # A cada 60 segundos, verifica novos clipes
INTERVALO_ANALISE_MINUTOS_CLIENTE = 5 # Janela de tempo para buscar clipes (últimos 5 minutos)

async def monitorar_cliente(config_cliente: dict, application: "Application"):
    """
    Lógica de monitoramento de clipes da Twitch para um único cliente.
    Usa as credenciais e streamers do config_cliente para buscar e enviar clipes.
    """
    telegram_id = config_cliente['telegram_id']
    twitch_client_id = config_cliente['twitch_client_id']
    twitch_client_secret = config_cliente['twitch_client_secret']
    # streamers_monitorados vem como string separada por vírgulas
    streamers_logins = [s.strip() for s in config_cliente['streamers_monitorados'].split(',') if s.strip()] if config_cliente['streamers_monitorados'] else []
    id_canal_telegram = config_cliente['id_canal_telegram']
    modo_monitoramento = config_cliente['modo_monitoramento']
    modo_parceiro = config_cliente.get('modo_parceiro', 'somente_bot')
    clipador_chefe_username = config_cliente.get('clipador_chefe_username')

    if not streamers_logins or not id_canal_telegram:
        logger.warning(f"🤖 [Monitor Cliente] Cliente {telegram_id} sem streamers ou ID de canal. Pulando monitoramento.")
        return
    requests_count = 0

    # Verificação das credenciais do cliente
    logger.info(f"🤖 [Monitor Cliente] Verificando credenciais para o usuário {telegram_id}.")
    logger.info(f"   - Client ID: {twitch_client_id}")
    logger.info(f"   - Client Secret: {twitch_client_secret[:4]}...{twitch_client_secret[-4:]}") # Mostra apenas parte do segredo

    # Cada cliente terá sua própria instância da TwitchAPI
    try:
        twitch = TwitchAPI(twitch_client_id, twitch_client_secret)
    except Exception as e:
        logger.error(f"❌ Falha ao inicializar TwitchAPI para o cliente {telegram_id}. As credenciais podem ser inválidas. Erro: {e}")
        # Opcional: Adicionar lógica para notificar o usuário ou marcar o canal com erro no DB.
        return # Pula o monitoramento para este cliente neste ciclo

    logger.info(f"🤖 [Monitor Cliente] Iniciando para o usuário {telegram_id} no canal {id_canal_telegram}.")
    logger.info(f"   - Streamers: {streamers_logins}, Modo: {modo_monitoramento}")

    try:
        # Obter IDs dos streamers
        # Validação da TwitchAPI
        logger.info(f"🤖 [Monitor Cliente] Buscando informações para {len(streamers_logins)} streamers do usuário {telegram_id}.")
        # Otimiza a busca de informações dos usuários em paralelo
        tasks = [twitch.get_user_info(login) for login in streamers_logins]
        user_infos = await asyncio.gather(*tasks)
        streamers_info = [info for info in user_infos if info] # Filtra os resultados nulos
        requests_count += len(streamers_logins)
        streamers_ids = {s["id"]: s["display_name"] for s in streamers_info}

        if not streamers_info:
            logger.warning(f"🤖 [Monitor Cliente] Nenhum streamer válido encontrado para {telegram_id}. Pulando monitoramento.")
            application.bot_data[f'client_{telegram_id}_requests'] = requests_count
            return

        # Correção: buscar clipes retroativos de INTERVALO_ANALISE_MINUTOS_CLIENTE minutos
        tempo_inicio = get_time_minutes_ago(minutes=INTERVALO_ANALISE_MINUTOS_CLIENTE)

        # Busca a configuração de notificação do cliente uma vez
        config_notificacao = obter_ou_criar_config_notificacao(telegram_id)
        notificar_online_status = config_notificacao.get('notificar_online', 1) == 1

        for streamer_id, display_name in streamers_ids.items():
            logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Buscando clipes de @{display_name}...")

            # --- LÓGICA DE NOTIFICAÇÃO "STREAMER ONLINE" ---
            # Busca o status da stream no início do loop para reutilização
            stream = await twitch.get_stream_info(streamer_id)
            requests_count += 1

            status_atual = 'online' if stream else 'offline'
            status_anterior = obter_status_streamer(telegram_id, streamer_id)

            # Se o status mudou, atualiza no banco de dados
            if status_atual != status_anterior:
                atualizar_status_streamer(telegram_id, streamer_id, status_atual)
                logger.info(f"🔄 [Status Change] @{display_name} mudou para {status_atual} para o cliente {telegram_id}.")

                # Se o streamer ficou online e as notificações estão ativas, envia o aviso
                if status_atual == 'online' and notificar_online_status:
                    try:
                        stream_title = stream.get('title', 'Sem título')
                        stream_game = stream.get('game_name', 'Não especificado')
                        stream_url = f"https://twitch.tv/{display_name}"
                        mensagem_online = (
                            f"🟢 <b>@{display_name} está AO VIVO!</b>\n\n"
                            f"📝 {stream_title}\n"
                            f"🎮 Jogando: {stream_game}\n\n"
                            f"{stream_url}"
                        )
                        await application.bot.send_message(chat_id=id_canal_telegram, text=mensagem_online, parse_mode="HTML")
                        logger.info(f"✅ [Notificação Online] Enviada para o canal do cliente {telegram_id} sobre @{display_name}.")
                    except telegram_error.TelegramError as e:
                        logger.error(f"❌ Erro de Telegram ao enviar notificação online para o canal do cliente {telegram_id}: {e}")

            clipes = await twitch.get_recent_clips(streamer_id, started_at=tempo_inicio)
            requests_count += 1
            logger.debug(f"🔎 [Monitor Cliente {telegram_id}] {len(clipes)} clipes encontrados para @{display_name} no período.")
            
            # --- LÓGICA DO CLIPADOR CHEFE ---
            if clipador_chefe_username and modo_parceiro in ['somente_chefe', 'chefe_e_bot']:
                for clipe in clipes:
                    creator_name = clipe.get('creator_name', '')
                    clipe_id = clipe.get('id')
                    
                    if creator_name.lower() == clipador_chefe_username.lower():
                        if not verificar_clipe_chefe_ja_enviado(telegram_id, clipe_id):
                            clipe_url = clipe["url"]
                            created_at_dt = datetime.fromisoformat(clipe["created_at"].replace("Z", "+00:00"))
                            
                            tipo_raw = "CLIPE AO VIVO" if await eh_clipe_ao_vivo_real(clipe, twitch, streamer_id) else "CLIPE DO VOD"
                            tipo_formatado = f"\n🔴 <b>{tipo_raw}</b>" if tipo_raw == "CLIPE AO VIVO" else f"\n⏳ <b>{tipo_raw}</b>"

                            mensagem_chefe = (
                                f"{tipo_formatado}\n"
                                f"📺 @{display_name}\n"
                                f"🕒 {created_at_dt.strftime('%d/%m/%Y %H:%M:%S')}\n"
                                f"✂️ <b>Clipado por: @{clipador_chefe_username}</b>\n\n"
                                f"{clipe_url}"
                            )
                            try:
                                await application.bot.send_message(chat_id=id_canal_telegram, text=mensagem_chefe, parse_mode="HTML")
                                registrar_clipe_chefe_enviado(telegram_id, clipe_id)
                                logger.info(f"✅ [Clipador Chefe] Clipe {clipe_id} de @{display_name} enviado para {telegram_id}.")
                            except telegram_error.TelegramError as e:
                                logger.error(f"❌ Erro de Telegram ao enviar clipe do chefe para o canal do cliente {telegram_id}: {e}")

            # --- LÓGICA DE DETECÇÃO AUTOMÁTICA ---
            # A lógica de detecção automática só roda se o modo parceiro permitir.
            if modo_parceiro in ['somente_bot', 'chefe_e_bot']:
                # A variável 'stream' já foi obtida no início do loop
                is_vod_session = not stream and clipes

                # Define o critério de agrupamento (pode ser um número ou uma função)
                criterio_agrupamento = None

                if modo_monitoramento == "MANUAL":
                    intervalo_agrupamento = config_cliente.get('manual_interval_sec', 60)
                    minimo_clipes_ao_vivo = config_cliente.get('manual_min_clips', 3)
                    if is_vod_session:
                        logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Streamer @{display_name} offline. Usando critério de VOD (Manual).")
                        criterio_agrupamento = config_cliente.get('manual_min_clips_vod') or minimo_clipes_ao_vivo
                    else:
                        criterio_agrupamento = minimo_clipes_ao_vivo
                    logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Critério para @{display_name}: {criterio_agrupamento} clipes em {intervalo_agrupamento}s.")
                
                elif modo_monitoramento == "AUTOMATICO":
                    config_modo = MODOS_MONITORAMENTO.get(modo_monitoramento, MODOS_MONITORAMENTO["MODO_PADRAO"])
                    intervalo_agrupamento = config_modo["intervalo_segundos"]
                    # O critério é a própria função, que usa o viewer_count do clipe. Funciona para live e VOD.
                    criterio_agrupamento = minimo_clipes_por_viewers
                    logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Critério para @{display_name}: Dinâmico (Automático) em {intervalo_agrupamento}s.")

                else: # Lógica para modos predefinidos (Automático, Padrão, etc.)
                    config_modo = MODOS_MONITORAMENTO.get(modo_monitoramento, MODOS_MONITORAMENTO["MODO_PADRAO"])
                    intervalo_agrupamento = config_modo["intervalo_segundos"]
                    criterio_agrupamento = config_modo.get("min_clipes", 3)
                    logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Critério para @{display_name}: {criterio_agrupamento} clipes em {intervalo_agrupamento}s.")

                virais = agrupar_clipes_por_proximidade(clipes, intervalo_agrupamento, criterio_agrupamento)

                for grupo in virais:
                    inicio = grupo["inicio"]
                    fim = datetime.fromisoformat(grupo["fim"].replace("Z", "+00:00"))

                    if verificar_grupo_ja_enviado(telegram_id, streamer_id, inicio, fim):
                        continue

                    quantidade = len(grupo["clipes"])
                    primeiro_clipe = grupo["clipes"][0]
                    clipe_url = primeiro_clipe["url"]

                    tipo_raw = "CLIPE AO VIVO" if await eh_clipe_ao_vivo_real(primeiro_clipe, twitch, streamer_id) else "CLIPE DO VOD"
                    tipo_formatado = f"\n🔴 <b>{tipo_raw}</b>" if tipo_raw == "CLIPE AO VIVO" else f"\n⏳ <b>{tipo_raw}</b>"

                    if quantidade == 1:
                        texto_clipadores = "🔥 1 PESSOA CLIPOU"
                    else:
                        texto_clipadores = f"🔥 {quantidade} PESSOAS CLIPARAM"

                    mensagem = (
                        f"{tipo_formatado}\n"
                        f"📺 @{display_name}\n"
                        f"🕒 {inicio.strftime('%H:%M:%S')} - {fim.strftime('%H:%M:%S')}\n"
                        f"{texto_clipadores}\n\n"
                        f"{clipe_url}"
                    )
                    
                    try:
                        await application.bot.send_message(chat_id=id_canal_telegram, text=mensagem, parse_mode="HTML")
                        registrar_grupo_enviado(telegram_id, streamer_id, inicio, fim)
                    except telegram_error.TimedOut:
                        logger.warning(f"⏳ Timeout ao tentar enviar mensagem para o canal do cliente {telegram_id}. A mensagem será reenviada no próximo ciclo.")
                    except telegram_error.TelegramError as e:
                        logger.error(f"❌ Erro de Telegram ao enviar mensagem para o canal do cliente {telegram_id}: {e}")

        application.bot_data[f'client_{telegram_id}_requests'] = requests_count

    except httpx.HTTPStatusError as e:
        if e.response and e.response.status_code in [401, 403]:
            logger.error(f"❌ Credenciais Twitch inválidas para o cliente {telegram_id}. Notificando...")
            mensagem_erro = (
                "⚠️ *Atenção: Suas credenciais da Twitch são inválidas ou expiraram!*\n\n"
                "O monitoramento para seu canal está pausado. Por favor, vá até o bot "
                f"(@{application.bot.username}) e use o menu de gerenciamento para "
                "reconfigurar suas credenciais da Twitch."
            )
            try:
                await application.bot.send_message(
                    chat_id=id_canal_telegram,
                    text=mensagem_erro,
                    parse_mode="Markdown"
                )
            except Exception as send_error:
                logger.error(f"❌ Falha ao enviar notificação de erro de credenciais para o canal {id_canal_telegram}: {send_error}")
        else:
            # Se for outro erro HTTP, apenas loga para ser investigado.
            logger.error(f"❌ Erro HTTP no monitoramento do cliente {telegram_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ Erro no monitoramento do cliente {telegram_id}: {e}", exc_info=True)


async def iniciar_monitoramento_clientes(application: "Application"):
    """
    Busca todos os clientes ativos e com configuração completa e inicia
    uma tarefa de monitoramento para cada um.
    Este loop principal garante que novos clientes sejam adicionados ao monitoramento
    e que clientes inativos sejam removidos.
    """
    logger.info("📡 Iniciando serviço de monitoramento para clientes...")
    
    # Dicionário para manter as tarefas de monitoramento ativas por telegram_id
    tarefas_ativas = {}
    
    # Controles de tempo para rotinas periódicas
    ultima_limpeza = datetime.now()
    INTERVALO_LIMPEZA_HORAS = 24
    ultima_verificacao_expiracao = datetime.now()
    INTERVALO_VERIFICACAO_EXPIRACAO_HORAS = 4 # A cada 4 horas

    while True:
        # --- Rotina de Verificação de Expirações ---
        if datetime.now() - ultima_verificacao_expiracao > timedelta(hours=INTERVALO_VERIFICACAO_EXPIRACAO_HORAS):
            logger.info("Disparando rotina de verificação de expirações...")
            try:
                await verificar_expiracoes_assinaturas(application)
            except Exception as e:
                logger.error(f"Erro inesperado na rotina de verificação de expirações: {e}", exc_info=True)
            ultima_verificacao_expiracao = datetime.now()

        # --- Rotina de Limpeza Periódica ---
        if datetime.now() - ultima_limpeza > timedelta(hours=INTERVALO_LIMPEZA_HORAS):
            logger.info("Disparando rotina de limpeza em background...")
            # Executa a função síncrona de limpeza em uma thread separada para não bloquear o loop de eventos
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, executar_limpeza_completa)
            ultima_limpeza = datetime.now()

        usuarios_ativos = buscar_usuarios_ativos_configurados()
        usuarios_ativos_ids = {u['telegram_id'] for u in usuarios_ativos}
        
        logger.info(f"🔍 Encontrados {len(usuarios_ativos)} clientes ativos para monitorar.")
        
        # Iniciar/manter tarefas para usuários ativos
        for usuario in usuarios_ativos:
            user_id = usuario['telegram_id']
            if user_id not in tarefas_ativas or tarefas_ativas[user_id].done():
                # Se a tarefa não existe ou terminou, cria uma nova
                logger.info(f"🔄 Criando/Reiniciando tarefa de monitoramento para o cliente {user_id}.")
                tarefas_ativas[user_id] = asyncio.create_task(monitorar_cliente(usuario, application))
        
        # Cancelar tarefas de usuários que não estão mais ativos/configurados
        for user_id in list(tarefas_ativas.keys()):
            if user_id not in usuarios_ativos_ids:
                logger.info(f"🛑 Cancelando tarefa de monitoramento para cliente {user_id} (inativo/removido).")
                tarefas_ativas[user_id].cancel()
                await tarefas_ativas[user_id] # Aguarda o cancelamento
                del tarefas_ativas[user_id]
        
        # Aguarda um pouco antes de verificar novamente
        await asyncio.sleep(INTERVALO_MONITORAMENTO_CLIENTE)
        logger.debug("-- Ciclo de gerenciamento de tarefas de monitoramento concluído. --")