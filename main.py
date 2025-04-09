try:
    while True:

        import time
        from datetime import datetime, timedelta, timezone
        from urllib.parse import quote

        from app.twitch import TwitchAPI
        from app.monitor import agrupar_clipes_por_proximidade, identificar_grupos_virais
        from app.telegram import enviar_mensagem, atualizar_descricao_telegram

        # Configurações
        INTERVALO_SEGUNDOS = 30
        INTERVALO_MONITORAMENTO = 90
        INTERVALO_ATUALIZAR_DESCRICAO = 300  # 5 minutos
        MAX_CLIPES_EXIGIDOS = 6  # teto máximo mesmo em lives grandes
        DELAY_TOLERANCIA_SEGUNDOS = 20 * 60  # 20 minutos

        def get_time_minutes_ago(minutes=5):
            dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            return dt.isoformat().replace("+00:00", "Z")

        def montar_descricao(streamer_nome, stream_status, minimo_clipes, intervalo_grupo):
            status_emoji = "🟢 ONLINE" if stream_status == "ONLINE" else "🔴 OFFLINE"
            return (
                f"O CLIPADOR ESTÁ ONLINE 😎\n"
                f"👀 @{streamer_nome} - {status_emoji}\n"
                f"🔥 CRITÉRIO - Grupo de {minimo_clipes} clipes em {intervalo_grupo}s\n\n"
                f"Criado por @euw3ll"
            )

        def minimo_clipes_por_viewers(viewers):
            if viewers <= 5000:
                return 2
            elif viewers <= 30000:
                return 3
            elif viewers <= 70000:
                return 4
            else:
                return 4

        def eh_clipe_ao_vivo_real(clip, twitch, user_id):
            stream = twitch.get_stream_info(user_id)
            if not stream:
                return False  # streamer offline = nunca é ao vivo

            vod = twitch.get_latest_vod(user_id)
            if not vod:
                return False

            vod_id = vod["id"]
            clip_video_id = clip.get("video_id")
            if str(vod_id) != str(clip_video_id):
                return False

            vod_start = datetime.fromisoformat(vod["created_at"].replace("Z", "+00:00"))
            clip_created = datetime.fromisoformat(clip["created_at"].replace("Z", "+00:00"))
            delta = (clip_created - vod_start).total_seconds()

            return delta <= 180  # 3 minutos de tolerância máxima

        if __name__ == "__main__":
            twitch = TwitchAPI()
            username = "loud_coringa"
            user_info = twitch.get_user_info(username)
            enviados = set()

            if not user_info:
                print("❌ Streamer não encontrado.")
                exit()

            print(f"🎯 Monitorando: 📺 @{user_info['display_name']}")
            print("-" * 50)

            user_id = user_info["id"]
            ultima_atualizacao_descricao = 0

            while True:
                agora = time.time()
                if agora - ultima_atualizacao_descricao >= INTERVALO_ATUALIZAR_DESCRICAO:
                    stream_status = twitch.get_stream_status(user_id)
                    stream = twitch.get_stream_info(user_id)
                    viewers = stream["viewer_count"] if stream else 0
                    minimo_clipes = min(minimo_clipes_por_viewers(viewers), MAX_CLIPES_EXIGIDOS)

                    descricao = montar_descricao(
                        user_info['display_name'],
                        stream_status,
                        minimo_clipes,
                        INTERVALO_SEGUNDOS
                    )
                    atualizar_descricao_telegram(descricao)
                    ultima_atualizacao_descricao = agora

                started_at = get_time_minutes_ago(5)
                clipes = twitch.get_recent_clips(user_id, started_at)
                print(f"\n🎥 {len(clipes)} clipe(s) encontrados nos últimos 5 minutos.")

                clipes_novos = [c for c in clipes if c["id"] not in enviados]
                grupos = agrupar_clipes_por_proximidade(clipes_novos, intervalo_segundos=INTERVALO_SEGUNDOS)

                stream = twitch.get_stream_info(user_id)
                viewers = stream["viewer_count"] if stream else 0
                minimo_clipes = min(minimo_clipes_por_viewers(viewers), MAX_CLIPES_EXIGIDOS)

                virais = identificar_grupos_virais(grupos, minimo_clipes=minimo_clipes)

                ao_vivo_enviados = 0
                vod_enviados = 0

                for grupo in virais:
                    inicio = grupo["inicio"].strftime("%H:%M:%S")
                    fim = grupo["fim"].strftime("%H:%M:%S")
                    quantidade = len(grupo["clipes"])
                    primeiro_clipe = grupo["clipes"][0]
                    clipe_url = primeiro_clipe["url"]

                    tipo_raw = "CLIPE AO VIVO" if eh_clipe_ao_vivo_real(primeiro_clipe, twitch, user_id) else "CLIPE DO VOD"
                    tipo_formatado = f"🎬 <b>{tipo_raw}</b>" if tipo_raw == "CLIPE AO VIVO" else f"⏳ <b>{tipo_raw}</b>"

                    if tipo_raw == "CLIPE AO VIVO":
                        ao_vivo_enviados += 1
                    else:
                        vod_enviados += 1

                    mensagem = (
                        f"{tipo_formatado}\n"
                        f"📺 @{user_info['display_name']}\n"
                        f"🕒 {inicio} - {fim}\n"
                        f"🔥 {quantidade} PESSOAS CLIPARAM\n\n"
                        f"{clipe_url}"
                    )

                    try:
                        slug = clipe_url.split("/")[-1]
                        download_url = f"https://clipr.xyz/{slug}"
                    except Exception as e:
                        print(f"❌ Erro ao gerar link de download: {e}")
                        download_url = clipe_url  # fallback pro link normal do clipe

                    enviar_mensagem(mensagem, botao_url=download_url, botao_texto="📥 BAIXAR CLIPE")

                    for clip in grupo["clipes"]:
                        enviados.add(clip["id"])

                total_enviados = ao_vivo_enviados + vod_enviados
                if total_enviados == 0:
                    print("❌ Nenhum grupo viral identificado.")
                else:
                    print(f"✅ {total_enviados} grupo(s) enviados: {ao_vivo_enviados} AO VIVO / {vod_enviados} VOD")

                time.sleep(INTERVALO_MONITORAMENTO)

except KeyboardInterrupt:
    print("\n🛑 Clipador encerrado.")
    exit()