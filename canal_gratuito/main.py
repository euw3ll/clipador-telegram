import os
import time
from datetime import datetime, timezone

from memoria.estado import carregar_estado, salvar_estado

from .core.twitch import TwitchAPI
from .core.monitor import (
    agrupar_clipes_por_proximidade,
    identificar_grupos_virais,
    get_time_minutes_ago,
    montar_descricao,
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
)
from configuracoes import (
    STREAMER,
    INTERVALO_ATUALIZAR_DESCRICAO,
    INTERVALO_MENSAGEM_PROMOCIONAL,
    INTERVALO_MENSAGEM_HEADER,
    INTERVALO_ATUALIZACAO_STREAMERS,
    TIPO_LOG,
    ATUALIZAR_DESCRICAO,
    ENVIAR_CLIPES,
    USAR_VERIFICACAO_AO_VIVO,
)


def limpar_terminal():
    os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    if TIPO_LOG == "DESENVOLVEDOR":
        print("🔌 Conectando à Twitch API...")

    twitch = TwitchAPI()
    user_info = twitch.get_user_info(STREAMER)

    if not user_info:
        print("❌ Streamer não encontrado.")
        exit()

    user_id = user_info["id"]

    if TIPO_LOG == "DESENVOLVEDOR":
        print(f"✅ Conectado! Monitorando @{user_info['display_name']}")
        print("📂 Carregando estado do bot...")

    estado = carregar_estado()

    estado.setdefault("ultima_execucao", None)
    estado.setdefault("ultimo_envio_promocional", 0)
    estado.setdefault("ultimo_envio_header", 0)
    estado.setdefault("ultimo_envio_atualizacao_streamers", 0)
    estado.setdefault("descricao", 0)
    estado.setdefault("grupos_enviados", [])

    ultima_execucao = estado["ultima_execucao"]
    tempo_offline = 600
    if ultima_execucao:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(ultima_execucao)
        if delta.total_seconds() > tempo_offline:
            started_at = get_time_minutes_ago(5)
        else:
            started_at = (
                datetime.fromisoformat(ultima_execucao)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
    else:
        started_at = get_time_minutes_ago(5)

    try:
        while True:
            agora = time.time()

            # Monitoramento de clipes
            if TIPO_LOG == "DESENVOLVEDOR":
                print("🎥 Buscando clipes recentes...")

            clipes = twitch.get_recent_clips(user_id, started_at)
            clipes_novos = [c for c in clipes if all(
                not (grupo["inicio"] <= c["created_at"] <= grupo["fim"])
                for grupo in estado["grupos_enviados"]
            )]

            if TIPO_LOG == "DESENVOLVEDOR":
                print(f"🔎 {len(clipes_novos)} clipe(s) novo(s) após filtro de repetidos.")

            # Enviar mensagens automáticas (somente se houver clipes novos)
            if clipes_novos:
                if INTERVALO_MENSAGEM_PROMOCIONAL > 0 and agora - estado["ultimo_envio_promocional"] >= INTERVALO_MENSAGEM_PROMOCIONAL:
                    if TIPO_LOG == "DESENVOLVEDOR":
                        print("💬 Enviando mensagem promocional...")
                    enviar_mensagem_promocional()
                    estado["ultimo_envio_promocional"] = agora

                if INTERVALO_MENSAGEM_HEADER > 0 and agora - estado["ultimo_envio_header"] >= INTERVALO_MENSAGEM_HEADER:
                    if TIPO_LOG == "DESENVOLVEDOR":
                        print("📢 Enviando banner de streamers...")
                    enviar_header_streamers([STREAMER])
                    estado["ultimo_envio_header"] = agora

                if INTERVALO_ATUALIZACAO_STREAMERS > 0 and agora - estado["ultimo_envio_atualizacao_streamers"] >= INTERVALO_ATUALIZACAO_STREAMERS:
                    if TIPO_LOG == "DESENVOLVEDOR":
                        print("🔄 Enviando mensagem de atualização de streamers...")
                    enviar_mensagem_atualizacao_streamers()
                    estado["ultimo_envio_atualizacao_streamers"] = agora

            # Atualizar descrição do canal
            if ATUALIZAR_DESCRICAO and agora - estado["descricao"] >= INTERVALO_ATUALIZAR_DESCRICAO:
                if TIPO_LOG == "DESENVOLVEDOR":
                    print("📝 Atualizando descrição do canal...")
                stream_status = twitch.get_stream_status(user_id)
                stream = twitch.get_stream_info(user_id)
                viewers = stream["viewer_count"] if stream else 0
                minimo_clipes = minimo_clipes_por_viewers(viewers)

                try:
                    atualizar_descricao_telegram(
                        user_info["display_name"], stream_status, viewers,
                        minimo_clipes, INTERVALO_SEGUNDOS
                    )
                except Exception as e:
                    print(f"⚠️ Erro ao atualizar descrição: {e}")

                estado["descricao"] = agora

            # Processar grupos virais
            grupos = agrupar_clipes_por_proximidade(clipes_novos, intervalo_segundos=INTERVALO_SEGUNDOS)
            stream = twitch.get_stream_info(user_id)
            viewers = stream["viewer_count"] if stream else 0
            minimo_clipes = minimo_clipes_por_viewers(viewers)
            virais = identificar_grupos_virais(grupos, minimo_clipes=minimo_clipes)

            ao_vivo_enviados = 0
            vod_enviados = 0

            if TIPO_LOG == "PADRAO":
                limpar_terminal()
                print(f"🎯 Monitorando: 📺 @{user_info['display_name']}")
                print("-" * 50)
                print(f"🎥 {len(clipes)} clipe(s) encontrados nos últimos 5 minutos.")
            elif TIPO_LOG == "DESENVOLVEDOR":
                print(f"\n🧠 Grupos virais detectados: {len(virais)}")

            for grupo in virais:
                inicio = grupo["inicio"]
                fim = grupo["fim"]
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
                    f"📺 @{user_info['display_name']}\n"
                    f"🕒 {inicio.strftime('%H:%M:%S')} - {fim.strftime('%H:%M:%S')}\n"
                    f"🔥 {quantidade} PESSOAS CLIPARAM\n\n"
                    f"{clipe_url}"
                )

                try:
                    slug = clipe_url.split("/")[-1]
                    download_url = f"https://clipr.xyz/{slug}"
                except Exception as e:
                    if TIPO_LOG == "DESENVOLVEDOR":
                        print(f"❌ Erro ao gerar link de download: {e}")
                    download_url = clipe_url

                if ENVIAR_CLIPES:
                    if TIPO_LOG == "DESENVOLVEDOR":
                        print(f"📤 Enviando clipe: {slug}")
                    enviar_mensagem(mensagem, botao_url=download_url, botao_texto="📥 BAIXAR CLIPE")

                estado["grupos_enviados"].append({
                    "inicio": inicio.isoformat(),
                    "fim": fim.isoformat()
                })

                if tipo_raw == "CLIPE AO VIVO":
                    ao_vivo_enviados += 1
                else:
                    vod_enviados += 1

            total_enviados = ao_vivo_enviados + vod_enviados
            if TIPO_LOG in ("PADRAO", "DESENVOLVEDOR"):
                if total_enviados == 0:
                    print("❌ Nenhum grupo viral identificado.")
                else:
                    print(f"✅ {total_enviados} grupo(s) enviado(s): {ao_vivo_enviados} AO VIVO / {vod_enviados} VOD")

            estado["ultima_execucao"] = datetime.now(timezone.utc).isoformat()
            salvar_estado(estado)
            if TIPO_LOG == "DESENVOLVEDOR":
                print("💾 Estado salvo com sucesso.\n")

            time.sleep(INTERVALO_MONITORAMENTO)

    except KeyboardInterrupt:
        salvar_estado(estado)
        pass
