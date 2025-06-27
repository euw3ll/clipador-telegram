import asyncio
import time
from typing import TYPE_CHECKING
from datetime import datetime, timezone
import logging
from telegram import error as telegram_error

from core.database import (
    buscar_usuarios_ativos_configurados,
    registrar_grupo_enviado,
    verificar_grupo_ja_enviado
)
from canal_gratuito.core.twitch import TwitchAPI # Reutilizando a TwitchAPI
from canal_gratuito.core.monitor import ( # Reutilizando funções e o dicionário de modos
    agrupar_clipes_por_proximidade,
    get_time_minutes_ago,
    eh_clipe_ao_vivo_real,
    MODOS_MONITORAMENTO,
    minimo_clipes_por_viewers, # Importa a função dinâmica
)

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

    if not streamers_logins or not id_canal_telegram:
        logger.warning(f"🤖 [Monitor Cliente] Cliente {telegram_id} sem streamers ou ID de canal. Pulando monitoramento.")
        return

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
            if info:
                streamers_info.append(info)
        streamers_ids = {s["id"]: s["display_name"] for s in streamers_info}

        if not streamers_info:
            logger.warning(f"🤖 [Monitor Cliente] Nenhum streamer válido encontrado para {telegram_id}. Pulando monitoramento.")
            return

        # Correção: buscar clipes retroativos de INTERVALO_ANALISE_MINUTOS_CLIENTE minutos
        tempo_inicio = get_time_minutes_ago(minutes=INTERVALO_ANALISE_MINUTOS_CLIENTE)

        for streamer_id, display_name in streamers_ids.items():
            logger.debug(f"🎥 [Monitor Cliente {telegram_id}] Buscando clipes de @{display_name}...")

            clipes = twitch.get_recent_clips(streamer_id, started_at=tempo_inicio)
            logger.debug(f"🔎 [Monitor Cliente {telegram_id}] {len(clipes)} clipes encontrados para @{display_name} no período.")

            stream = twitch.get_stream_info(streamer_id)
            viewers = stream["viewer_count"] if stream else 0
            
            if modo_monitoramento == "MANUAL":
                # Usa as configurações manuais salvas no banco de dados
                minimo_clipes = config_cliente.get('manual_min_clips', 3) # Padrão de 3 se não definido
                intervalo_agrupamento = config_cliente.get('manual_interval_sec', 60) # Padrão de 60s se não definido
            elif modo_monitoramento == "AUTOMATICO":
                # Para o modo automático, o min_clipes é dinâmico baseado nos viewers
                minimo_clipes = minimo_clipes_por_viewers(viewers)
                intervalo_agrupamento = MODOS_MONITORAMENTO["AUTOMATICO"]["intervalo_segundos"]
            else:
                # Para outros modos, usa as configurações fixas
                config_modo = MODOS_MONITORAMENTO.get(modo_monitoramento, MODOS_MONITORAMENTO["MODO_PADRAO"])
                minimo_clipes = config_modo["min_clipes"]
                intervalo_agrupamento = config_modo["intervalo_segundos"]

            virais = agrupar_clipes_por_proximidade(clipes, intervalo_agrupamento, minimo_clipes)

            for grupo in virais:
                inicio = grupo["inicio"]
                fim = datetime.fromisoformat(grupo["fim"].replace("Z", "+00:00"))

                # Verifica se este grupo já foi enviado usando o banco de dados
                if verificar_grupo_ja_enviado(telegram_id, streamer_id, inicio, fim):
                    continue # Pula para o próximo grupo

                quantidade = len(grupo["clipes"])
                primeiro_clipe = grupo["clipes"][0]
                clipe_url = primeiro_clipe["url"]

                tipo_raw = "CLIPE AO VIVO" if eh_clipe_ao_vivo_real(primeiro_clipe, twitch, streamer_id) else "CLIPE DO VOD"
                tipo_formatado = f"\n🔴 <b>{tipo_raw}</b>" if tipo_raw == "CLIPE AO VIVO" else f"\n⏳ <b>{tipo_raw}</b>"

                mensagem = (
                    f"{tipo_formatado}\n"
                    f"📺 @{display_name}\n"
                    f"🕒 {inicio.strftime('%H:%M:%S')} - {fim.strftime('%H:%M:%S')}\n"
                    f"🔥 {quantidade} PESSOAS CLIPARAM\n\n"
                    f"{clipe_url}"
                )
                
                try:
                    # Enviar para o canal do cliente
                    await application.bot.send_message(chat_id=id_canal_telegram, text=mensagem, parse_mode="HTML")
                    # Registra o envio no banco de dados para evitar duplicatas
                    registrar_grupo_enviado(telegram_id, streamer_id, inicio, fim)
                except telegram_error.TimedOut:
                    logger.warning(
                        f"⏳ Timeout ao tentar enviar mensagem para o canal do cliente {telegram_id}. "
                        "Isso geralmente é um problema de rede temporário. A mensagem será reenviada no próximo ciclo."
                    )
                except telegram_error.TelegramError as e:
                    logger.error(f"❌ Erro de Telegram ao enviar mensagem para o canal do cliente {telegram_id}: {e}")

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

    while True:
        usuarios_ativos = buscar_usuarios_ativos_configurados()
        usuarios_ativos_ids = {u['telegram_id'] for u in usuarios_ativos}
        
        logger.debug(f"🔍 Encontrados {len(usuarios_ativos)} clientes ativos para monitorar.")
        
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
        logger.debug("-- Ciclo de gerenciamento de tarefas de monitoramento de clientes concluído. --")