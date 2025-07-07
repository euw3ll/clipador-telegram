import os
import time
from datetime import datetime, timezone
import asyncio
from typing import TYPE_CHECKING

from memoria.estado import carregar_estado, salvar_estado
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.ambiente import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET # Importar as credenciais globais
from .core.twitch import TwitchAPI
from .core.monitor import ( # Importando as funções e constantes necessárias
    agrupar_clipes_por_proximidade,
    get_time_minutes_ago,
    minimo_clipes_por_viewers,
    eh_clipe_ao_vivo_real,
    INTERVALO_SEGUNDOS, # Usado no modo MANUAL
    INTERVALO_MONITORAMENTO,
    MINIMO_CLIPES, # Usado no modo MANUAL
    MODOS_MONITORAMENTO, # Usado para o modo AUTOMATICO
)
from configuracoes import (
    CANAL_GRATUITO_ID,
    INTERVALO_MENSAGEM_PROMOCIONAL,
    INTERVALO_MENSAGEM_HEADER,
    INTERVALO_ATUALIZACAO_STREAMERS,
    TIPO_LOG,
    ATUALIZAR_DESCRICAO,
    ENVIAR_CLIPES,
    USAR_VERIFICACAO_AO_VIVO,
    MODO_MONITORAMENTO_GRATUITO,
    QUANTIDADE_STREAMERS_TOP_BR,
    STREAMERS_ADICIONAIS_GRATUITO,
    INTERVALO_ANALISE_MINUTOS_GRATUITO,
)

TIMEOUT_REQUESTS = 20 # Segundos para timeout das requisições à Twitch

def limpar_terminal():
    os.system("cls" if os.name == "nt" else "clear")

if TYPE_CHECKING:
    from telegram.ext import Application

async def main(application: "Application"):
    if TIPO_LOG == "DESENVOLVEDOR":
        print("🔌 Conectando à Twitch API...")

    twitch = TwitchAPI(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)

    if TIPO_LOG == "DESENVOLVEDOR":
        print("📂 Carregando estado do bot...")

    estado = carregar_estado()
    estado.setdefault("ultima_execucao", None)
    estado.setdefault("ultimo_envio_promocional", 0)
    estado.setdefault("ultimo_envio_header", 0)
    estado.setdefault("ultimo_envio_atualizacao_streamers", 0)
    estado.setdefault("grupos_enviados", [])
    estado.setdefault("ultima_descricao", "")

    try:
        while True:
            agora = time.time()
            total_ao_vivo = 0
            total_vod = 0
            grupo_enviado = False
            total_clipes = 0
            minimo_clipes_global = 0
            requests_count = 0

            # 🆕 ATUALIZAR A LISTA DE STREAMERS A CADA CICLO
            try:
                top_logins = await asyncio.wait_for(
                    twitch.get_top_streamers_brasil(quantidade=QUANTIDADE_STREAMERS_TOP_BR),
                    timeout=TIMEOUT_REQUESTS
                )
            except asyncio.TimeoutError:
                print(f"⚠️ Timeout ao buscar top streamers do Brasil. Pulando ciclo de atualização.")
                top_logins = []
            requests_count += 1

            # Combina a lista de top streamers com a lista de streamers adicionais, sem duplicatas
            # Mantém a ordem: adicionais primeiro, depois os tops.
            combined_logins = []
            seen_logins = set()

            for login in STREAMERS_ADICIONAIS_GRATUITO:
                login_lower = login.lower()
                if login_lower not in seen_logins:
                    combined_logins.append(login)
                    seen_logins.add(login_lower)

            for login in top_logins:
                login_lower = login.lower()
                if login_lower not in seen_logins:
                    combined_logins.append(login)
                    seen_logins.add(login_lower)

            async def get_user_info_with_timeout(login):
                try:
                    return await asyncio.wait_for(twitch.get_user_info(login), timeout=TIMEOUT_REQUESTS)
                except asyncio.TimeoutError:
                    print(f"⚠️ Timeout ao buscar informações de @{login}. Pulando.")
                    return None

            # Busca as informações dos usuários para a lista combinada
            # Otimiza a busca de informações dos usuários em paralelo
            tasks = [get_user_info_with_timeout(login) for login in combined_logins]
            user_infos = await asyncio.gather(*tasks)
            streamers_a_monitorar = [info for info in user_infos if info] # Filtra os resultados nulos
            requests_count += len(combined_logins) # Conta as chamadas de get_user_info

            # Salva os streamers monitorados para o comando de stats
            application.bot_data['free_channel_streamers'] = [s['display_name'] for s in streamers_a_monitorar]
            if not streamers_a_monitorar:
                print("❌ Nenhum streamer encontrado no momento.")
                time.sleep(INTERVALO_MONITORAMENTO)
                continue

            if TIPO_LOG == "DESENVOLVEDOR":
                print("🔄 Lista de streamers atualizada:", ", ".join([s["display_name"] for s in streamers_a_monitorar]))

            # Correção: buscar clipes retroativos de 5 minutos
            tempo_inicio = get_time_minutes_ago(minutes=INTERVAL    O_ANALISE_MINUTOS_GRATUITO)

            for streamer in streamers_a_monitorar:
                user_id = streamer["id"]
                display_name = streamer["display_name"]

                if TIPO_LOG == "DESENVOLVEDOR":
                    print(f"🎥 Buscando clipes de @{display_name}...")

                try:
                    clipes = await asyncio.wait_for(
                        twitch.get_recent_clips(user_id, started_at=tempo_inicio),
                        timeout=TIMEOUT_REQUESTS
                    )
                except asyncio.TimeoutError:
                    print(f"⚠️ Timeout ao buscar clipes de @{display_name}. Pulando este streamer no ciclo.")
                    clipes = []
                requests_count += 1
                total_clipes += len(clipes)
                clipes_novos = []
                for c in clipes:
                    c_time = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                    repetido = any(
                        datetime.fromisoformat(grupo["inicio"]) <= c_time <= datetime.fromisoformat(grupo["fim"])
                        for grupo in estado["grupos_enviados"]
                    )
                    if not repetido:
                        clipes_novos.append(c)

                if TIPO_LOG == "DESENVOLVEDOR":
                    print(f"🔎 {len(clipes_novos)} clipes novos encontrados.")

                if MODO_MONITORAMENTO_GRATUITO == 'AUTOMATICO':
                    stream = None
                    try:
                        stream = await asyncio.wait_for(
                            twitch.get_stream_info(user_id),
                            timeout=TIMEOUT_REQUESTS
                        )
                    except asyncio.TimeoutError:
                        print(f"⚠️ Timeout ao buscar status da stream de @{display_name}. Assumindo offline.")
                    requests_count += 1
                    viewers = stream["viewer_count"] if stream else 0
                    minimo_clipes = minimo_clipes_por_viewers(viewers)
                    intervalo_agrupamento = MODOS_MONITORAMENTO["AUTOMATICO"]["intervalo_segundos"]
                else:  # MODO_MONITORAMENTO_GRATUITO == 'MANUAL'
                    minimo_clipes = MINIMO_CLIPES
                    intervalo_agrupamento = INTERVALO_SEGUNDOS

                minimo_clipes_global = max(minimo_clipes_global, minimo_clipes)

                virais = agrupar_clipes_por_proximidade(clipes_novos, intervalo_agrupamento, minimo_clipes)

                for grupo in virais:
                    # Se este for o primeiro clipe do ciclo, envia as mensagens de status/promoção ANTES.
                    if not grupo_enviado:
                        if INTERVALO_MENSAGEM_PROMOCIONAL > 0 and agora - estado["ultimo_envio_promocional"] >= INTERVALO_MENSAGEM_PROMOCIONAL:
                            mensagem_promo = "<b>🤑 Transforme clipes em dinheiro!</b>\nCom o Clipador, você tem acesso aos melhores clipes em tempo real, prontos para você monetizar.\n\nGaranta agora 👉 @ClipadorBot"
                            await application.bot.send_message(chat_id=CANAL_GRATUITO_ID, text=mensagem_promo, parse_mode="HTML")
                            estado["ultimo_envio_promocional"] = agora

                        if INTERVALO_ATUALIZACAO_STREAMERS > 0 and agora - estado["ultimo_envio_atualizacao_streamers"] >= INTERVALO_ATUALIZACAO_STREAMERS:
                            mensagem_update = f"Estamos acompanhando em tempo real os <b>{len(streamers_a_monitorar)} streamers mais assistidos do Brasil</b> no momento.\n\n📺 Fique ligado e aproveite os melhores clipes! 🎯"
                            await application.bot.send_message(chat_id=CANAL_GRATUITO_ID, text=mensagem_update, parse_mode="HTML")
                            estado["ultimo_envio_atualizacao_streamers"] = agora

                    inicio = grupo["inicio"]
                    fim = datetime.fromisoformat(grupo["fim"].replace("Z", "+00:00"))
                    quantidade = len(grupo["clipes"])
                    primeiro_clipe = grupo["clipes"][0]
                    clipe_url = primeiro_clipe["url"]

                    is_live = False
                    if USAR_VERIFICACAO_AO_VIVO:
                        try:
                            is_live = await asyncio.wait_for(
                                eh_clipe_ao_vivo_real(primeiro_clipe, twitch, user_id),
                                timeout=TIMEOUT_REQUESTS
                            )
                        except asyncio.TimeoutError:
                            print(f"⚠️ Timeout ao verificar se o clipe de @{display_name} é ao vivo. Assumindo VOD.")
                            is_live = False
                    tipo_raw = "CLIPE AO VIVO" if is_live else "CLIPE DO VOD"
                    tipo_formatado = f"\n🔴 <b>{tipo_raw}</b>" if tipo_raw == "CLIPE AO VIVO" else f"\n⏳ <b>{tipo_raw}</b>"

                    mensagem = (
                        f"{tipo_formatado}\n"
                        f"📺 @{display_name}\n"
                        f"🕒 {inicio.strftime('%H:%M:%S')} - {fim.strftime('%H:%M:%S')}\n"
                        f"🔥 {quantidade} PESSOAS CLIPARAM\n\n"
                        f"{clipe_url}"
                    )

                    try:
                        slug = clipe_url.split("/")[-1]
                        download_url = f"https://clipr.xyz/{slug}"
                    except Exception:
                        download_url = clipe_url

                    if ENVIAR_CLIPES:
                        botoes = [[InlineKeyboardButton("📥 BAIXAR CLIPE", url=download_url)]]
                        await application.bot.send_message(
                            chat_id=CANAL_GRATUITO_ID,
                            text=mensagem,
                            reply_markup=InlineKeyboardMarkup(botoes),
                            parse_mode="HTML"
                        )

                    estado["grupos_enviados"].append({
                        "inicio": inicio.isoformat(),
                        "fim": fim.isoformat()
                    })

                    if tipo_raw == "CLIPE AO VIVO":
                        total_ao_vivo += 1
                    else:
                        total_vod += 1

                    grupo_enviado = True

            # ATUALIZAÇÃO DA DESCRIÇÃO (MOVIDO PARA FORA DO LOOP DE STREAMERS)
            if ATUALIZAR_DESCRICAO:
                try:
                    logins_monitorados = [s["login"] for s in streamers_a_monitorar]
                    cabecalho = (
                        f"O CLIPADOR ESTÁ ONLINE 😎\n"
                        f"👀 Monitorando {len(streamers_a_monitorar)} streamers agora 👇"
                    )
                    lista = "\n" + "\n".join([f"• @{login}" for login in logins_monitorados]) if logins_monitorados else ""

                    if MODO_MONITORAMENTO_GRATUITO == 'MANUAL':
                        criterio = f"\n🔥 Critério: Grupo de {MINIMO_CLIPES} clipes em {INTERVALO_SEGUNDOS}s"
                    else: # AUTOMATICO
                        criterio = f"\n🔥 Critério: Automático (sensibilidade atual: {minimo_clipes_global} clipes)"

                    descricao_nova = f"{cabecalho}{lista}{criterio}"

                    if len(descricao_nova) > 255:
                        descricao_nova = descricao_nova[:252] + "..."

                    if descricao_nova != estado.get("ultima_descricao"):
                        await application.bot.set_chat_description(chat_id=CANAL_GRATUITO_ID, description=descricao_nova)
                        estado["ultima_descricao"] = descricao_nova
                        print("✅ Descrição do canal atualizada com sucesso.")
                except Exception as e:
                    if "Chat description is not modified" not in str(e):
                        print(f"⚠️ Erro ao atualizar descrição: {e}")
            total_enviados = total_ao_vivo + total_vod

            if TIPO_LOG == "PADRAO":
                limpar_terminal()
                print(f"🎯 Monitorando {len(streamers_a_monitorar)} streamers")
                print("-" * 50)
                print(f"🎥 {total_clipes} clipe(s) encontrados nos últimos {INTERVALO_ANALISE_MINUTOS_GRATUITO} minutos.")
                if total_enviados == 0:
                    print("❌ Nenhum grupo viral identificado.")
                else:
                    print(f"✅ {total_enviados} grupo(s) enviado(s): {total_ao_vivo} AO VIVO / {total_vod} VOD")
                print("-" * 50)
                print(f"🧠 MODO DE MONITORAMENTO: {MODO_MONITORAMENTO_GRATUITO}")
                if MODO_MONITORAMENTO_GRATUITO == 'MANUAL':
                    print(f"🔥 CRITÉRIO: Grupo de {MINIMO_CLIPES} clipes em {INTERVALO_SEGUNDOS}s")
                else:
                    # No modo automático, o critério muda a cada streamer, então mostramos o mais exigente do ciclo
                    print(f"🔥 CRITÉRIO: Automático (sensibilidade atual: {minimo_clipes_global} clipes)")
                print(f"⏰ ÚLTIMA VERIFICAÇÃO: {datetime.now().strftime('%H:%M:%S')}")
            elif TIPO_LOG == "DESENVOLVEDOR":
                print(f"📼 Grupos enviados: {total_enviados}")

            estado["ultima_execucao"] = datetime.now(timezone.utc).isoformat()
            salvar_estado(estado)
            # Salva o total de requisições do ciclo
            application.bot_data['free_channel_requests'] = requests_count
            await asyncio.sleep(INTERVALO_MONITORAMENTO)

    except asyncio.CancelledError:
        try:
            descricao_offline = "O CLIPADOR ESTÁ OFFLINE 😭"
            await application.bot.set_chat_description(chat_id=CANAL_GRATUITO_ID, description=descricao_offline)
            print("\n🛑 Monitor do canal gratuito encerrado.")
        except Exception as e:
            print(f"⚠️ Erro ao atualizar descrição OFFLINE no monitor gratuito: {e}")
        salvar_estado(estado)
        raise # Re-raise CancelledError para que a tarefa seja finalizada corretamente
    except Exception as e:
        print(f"❌ Erro inesperado no monitor do canal gratuito: {e}")
        salvar_estado(estado)
