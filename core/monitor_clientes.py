import asyncio
import time
from typing import TYPE_CHECKING
from datetime import datetime, timezone, timedelta
import logging
from telegram import error as telegram_error

from core.database import (
    buscar_usuarios_ativos_configurados,
    registrar_grupo_enviado,
    verificar_grupo_ja_enviado,
    registrar_clipe_chefe_enviado,
    verificar_clipe_chefe_ja_enviado,
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
        logger.info(f"🤖 [Monitor Cliente] Obtendo informações do token para o usuário {telegram_id}.")
        logger.info(f"   - Token: {twitch.token[:20]}...") # Mostra apenas parte do token

        streamers_info = []
        for login in streamers_logins:
            info = twitch.get_user_info(login)
            requests_count += 1
            if info:
                streamers_info.append(info)
        streamers_ids = {s["id"]: s["display_name"] for s in streamers_info}

        if not streamers_info:
            logger.warning(f"🤖 [Monitor Cliente] Nenhum streamer válido encontrado para {telegram_id}. Pulando monitoramento.")
            application.bot_data[f'client_{telegram_id}_requests'] = requests_count
            return

        # Correção: buscar clipes retroativos de INTERVALO_ANALISE_MINUTOS_CLIENTE minutos
        tempo_inicio = get_time_minutes_ago(minutes=INTERVALO_ANALISE_MINUTOS_CLIENTE)

        for streamer_id, display_name in streamers_ids.items():
            logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Buscando clipes de @{display_name}...")

            clipes = twitch.get_recent_clips(streamer_id, started_at=tempo_inicio)
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
                            
                            tipo_raw = "CLIPE AO VIVO" if eh_clipe_ao_vivo_real(clipe, twitch, streamer_id) else "CLIPE DO VOD"
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
                stream = twitch.get_stream_info(streamer_id)
                requests_count += 1

                # Se não há stream (offline) e há clipes, são de VOD. O critério é mais flexível.
                is_vod_session = not stream and clipes

                if is_vod_session:
                    logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Streamer @{display_name} offline. Usando critério de VOD.")
                    minimo_clipes = 1  # Clipes de VOD são sempre relevantes
                    # Usa o intervalo do modo padrão para agrupar clipes de VOD
                    intervalo_agrupamento = MODOS_MONITORAMENTO["MODO_PADRAO"]["intervalo_segundos"]
                else: # Se está ao vivo ou não há clipes, usa a lógica padrão
                    viewers = stream["viewer_count"] if stream else 0

                    if modo_monitoramento == "MANUAL":
                        minimo_clipes = config_cliente.get('manual_min_clips', 3)
                        intervalo_agrupamento = config_cliente.get('manual_interval_sec', 60)
                    else: # Lógica para modos predefinidos (Automático, Padrão, etc.)
                        config_modo = MODOS_MONITORAMENTO.get(modo_monitoramento, MODOS_MONITORAMENTO["MODO_PADRAO"])
                        intervalo_agrupamento = config_modo["intervalo_segundos"]

                        if modo_monitoramento == "AUTOMATICO":
                            minimo_clipes = minimo_clipes_por_viewers(viewers)
                        else:
                            # Para outros modos (Louco, Padrão, Cirúrgico), usa o valor fixo do modo
                            minimo_clipes = config_modo.get("min_clipes", 3) # Fallback para 3

                logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Critério para @{display_name}: {minimo_clipes} clipes em {intervalo_agrupamento}s.")
                virais = agrupar_clipes_por_proximidade(clipes, intervalo_agrupamento, minimo_clipes)

                for grupo in virais:
                    inicio = grupo["inicio"]
                    fim = datetime.fromisoformat(grupo["fim"].replace("Z", "+00:00"))

                    if verificar_grupo_ja_enviado(telegram_id, streamer_id, inicio, fim):
                        continue

                    quantidade = len(grupo["clipes"])
                    primeiro_clipe = grupo["clipes"][0]
                    clipe_url = primeiro_clipe["url"]

                    tipo_raw = "CLIPE AO VIVO" if eh_clipe_ao_vivo_real(primeiro_clipe, twitch, streamer_id) else "CLIPE DO VOD"
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
    
    # Controle de tempo para a rotina de limpeza periódica
    ultima_limpeza = datetime.now()
    INTERVALO_LIMPEZA_HORAS = 24

    while True:
        # --- Rotina de Limpeza Periódica (executada em background) ---
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