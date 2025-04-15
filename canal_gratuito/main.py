import os
import time

from datetime import datetime, timezone

from memoria.estado import carregar_estado, salvar_estado
from .core.twitch import TwitchAPI
from .core.monitor import (
    agrupar_clipes_por_proximidade,
    identificar_grupos_virais,
    get_time_minutes_ago,
    minimo_clipes_por_viewers,
    eh_clipe_ao_vivo_real,
    INTERVALO_SEGUNDOS,
    INTERVALO_MONITORAMENTO,
)
from .core.telegram import (
    enviar_mensagem,
    atualizar_descricao_telegram,
    enviar_mensagem_promocional,
    enviar_header_streamers,
    enviar_mensagem_atualizacao_streamers,
    atualizar_descricao_telegram_offline,
)
from configuracoes import (
    INTERVALO_MENSAGEM_PROMOCIONAL,
    INTERVALO_MENSAGEM_HEADER,
    INTERVALO_ATUALIZACAO_STREAMERS,
    TIPO_LOG,
    ATUALIZAR_DESCRICAO,
    ENVIAR_CLIPES,
    USAR_VERIFICACAO_AO_VIVO,
    MODO_MONITORAMENTO,
)

# =================== CONFIGURAÇÕES DO main.py =================== #
QUANTIDADE_STREAMERS = 5            # Quantos streamers do topo do Brasil monitorar
INTERVALO_ANALISE_MINUTOS = 10      # Janela de tempo para buscar clipes
TEMPO_CONSIDERADO_OFFLINE = 1200    # Em segundos (20min) para buscar clipes retroativos
# ================================================================= #

def limpar_terminal():
    os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    if TIPO_LOG == "DESENVOLVEDOR":
        print("🔌 Conectando à Twitch API...")

    twitch = TwitchAPI()
    logins = twitch.get_top_streamers_brasil(quantidade=QUANTIDADE_STREAMERS)
    top_streamers = [twitch.get_user_info(login) for login in logins if twitch.get_user_info(login)]

    if not top_streamers:
        print("❌ Nenhum streamer encontrado.")
        exit()

    if TIPO_LOG == "DESENVOLVEDOR":
        print("✅ Streamers conectados:", ", ".join([s["display_name"] for s in top_streamers]))
        print("📂 Carregando estado do bot...")

    estado = carregar_estado()
    estado.setdefault("ultima_execucao", None)
    estado.setdefault("ultimo_envio_promocional", 0)
    estado.setdefault("ultimo_envio_header", 0)
    estado.setdefault("ultimo_envio_atualizacao_streamers", 0)
    estado.setdefault("grupos_enviados", [])

    ultima_execucao = estado["ultima_execucao"]
    if ultima_execucao:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(ultima_execucao)
        if delta.total_seconds() > TEMPO_CONSIDERADO_OFFLINE:
            started_at = get_time_minutes_ago(INTERVALO_ANALISE_MINUTOS)
        else:
            started_at = (
                datetime.fromisoformat(ultima_execucao)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
    else:
        started_at = get_time_minutes_ago(INTERVALO_ANALISE_MINUTOS)

    try:
        while True:
            agora = time.time()
            total_ao_vivo = 0
            total_vod = 0
            grupo_enviado = False
            total_clipes = 0
            minimo_clipes_global = 0

            for streamer in top_streamers:
                user_id = streamer["id"]
                display_name = streamer["display_name"]

                if TIPO_LOG == "DESENVOLVEDOR":
                    print(f"🎥 Buscando clipes de @{display_name}...")

                clipes = twitch.get_recent_clips(user_id, started_at)
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

                grupos = agrupar_clipes_por_proximidade(clipes_novos, intervalo_segundos=INTERVALO_SEGUNDOS)
                stream = twitch.get_stream_info(user_id)
                viewers = stream["viewer_count"] if stream else 0
                minimo_clipes = minimo_clipes_por_viewers(viewers)
                minimo_clipes_global = max(minimo_clipes_global, minimo_clipes)
                virais = identificar_grupos_virais(grupos, minimo_clipes=minimo_clipes)

                for grupo in virais:
                    inicio = grupo["inicio"]
                    fim = datetime.fromisoformat(grupo["fim"].replace("Z", "+00:00"))
                    quantidade = len(grupo["clipes"])
                    primeiro_clipe = grupo["clipes"][0]
                    clipe_url = primeiro_clipe["url"]

                    tipo_raw = (
                        "CLIPE AO VIVO"
                        if USAR_VERIFICACAO_AO_VIVO and eh_clipe_ao_vivo_real(primeiro_clipe, twitch, user_id)
                        else "CLIPE DO VOD"
                    )
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
                        enviar_mensagem(mensagem, botao_url=download_url, botao_texto="📥 BAIXAR CLIPE")

                    estado["grupos_enviados"].append({
                        "inicio": inicio.isoformat(),
                        "fim": fim.isoformat()
                    })

                    if tipo_raw == "CLIPE AO VIVO":
                        total_ao_vivo += 1
                    else:
                        total_vod += 1

                    grupo_enviado = True

                if ATUALIZAR_DESCRICAO:
                    stream_status = twitch.get_stream_status(user_id)
                    try:
                        atualizar_descricao_telegram(minimo_clipes, INTERVALO_SEGUNDOS, QUANTIDADE_STREAMERS)
                    except Exception as e:
                        print(f"⚠️ Erro ao atualizar descrição: {e}")

            if grupo_enviado:
                if INTERVALO_MENSAGEM_PROMOCIONAL > 0 and agora - estado["ultimo_envio_promocional"] >= INTERVALO_MENSAGEM_PROMOCIONAL:
                    enviar_mensagem_promocional()
                    estado["ultimo_envio_promocional"] = agora

                if INTERVALO_MENSAGEM_HEADER > 0 and agora - estado["ultimo_envio_header"] >= INTERVALO_MENSAGEM_HEADER:
                    enviar_header_streamers([s["display_name"] for s in top_streamers])
                    estado["ultimo_envio_header"] = agora

                if INTERVALO_ATUALIZACAO_STREAMERS > 0 and agora - estado["ultimo_envio_atualizacao_streamers"] >= INTERVALO_ATUALIZACAO_STREAMERS:
                    enviar_mensagem_atualizacao_streamers(qtd=len(top_streamers))
                    estado["ultimo_envio_atualizacao_streamers"] = agora

            total_enviados = total_ao_vivo + total_vod

            if TIPO_LOG == "PADRAO":
                limpar_terminal()
                print(f"🎯 Monitorando os {len(top_streamers)} streamers com mais viewers do Brasil")
                print("-" * 50)
                print(f"🎥 {total_clipes} clipe(s) encontrados nos últimos {INTERVALO_ANALISE_MINUTOS} minutos.")
                if total_enviados == 0:
                    print("❌ Nenhum grupo viral identificado.")
                else:
                    print(f"✅ {total_enviados} grupo(s) enviado(s): {total_ao_vivo} AO VIVO / {total_vod} VOD")
                print("-" * 50)
                print(f"🧠 MODO DE MONITORAMENTO: {MODO_MONITORAMENTO}")
                print(f"🔥 CRITÉRIO: Grupo de {minimo_clipes_global} clipes em {INTERVALO_SEGUNDOS}s")
                print(f"⏰ ÚLTIMA VERIFICAÇÃO: {datetime.now().strftime('%H:%M:%S')}")
            elif TIPO_LOG == "DESENVOLVEDOR":
                print(f"📼 Grupos enviados: {total_enviados}")

            estado["ultima_execucao"] = datetime.now(timezone.utc).isoformat()
            salvar_estado(estado)
            time.sleep(INTERVALO_MONITORAMENTO)

    except KeyboardInterrupt:
        try:
            atualizar_descricao_telegram_offline()
            print("\n🛑 Clipador encerrado.")
        except Exception as e:
            print(f"⚠️ Erro ao atualizar descrição OFFLINE: {e}")
        salvar_estado(estado)

