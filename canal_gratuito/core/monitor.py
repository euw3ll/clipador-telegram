from datetime import datetime, timedelta, timezone

def agrupar_clipes_por_proximidade(clipes, intervalo_segundos=30, minimo_clipes=3):
    clipes_ordenados = sorted(
        clipes,
        key=lambda c: datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
    )

    grupos = []
    usados = set()

    for i in range(len(clipes_ordenados)):
        clipe_base = clipes_ordenados[i]
        base_time = datetime.fromisoformat(clipe_base["created_at"].replace("Z", "+00:00"))

        grupo = [clipe_base]

        for j in range(i + 1, len(clipes_ordenados)):
            outro_clipe = clipes_ordenados[j]
            outro_time = datetime.fromisoformat(outro_clipe["created_at"].replace("Z", "+00:00"))
            delta = (outro_time - base_time).total_seconds()

            if delta <= intervalo_segundos:
                grupo.append(outro_clipe)
            else:
                break

        ids_grupo = {c["id"] for c in grupo}
        if len(grupo) >= minimo_clipes and not ids_grupo & usados:
            grupos.append({
                "inicio": base_time,
                "fim": base_time + timedelta(seconds=intervalo_segundos),
                "clipes": grupo
            })
            usados.update(ids_grupo)

    return grupos

def identificar_grupos_virais(grupos, minimo_clipes=3):
    return [grupo for grupo in grupos if len(grupo["clipes"]) >= minimo_clipes]

def get_time_minutes_ago(minutes=5):
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return dt.isoformat().replace("+00:00", "Z")

def minimo_clipes_por_viewers(viewers):
    if viewers <= 25000:
        return 2
    elif viewers <= 50000:
        return 3
    elif viewers <= 100000:
        return 4
    else:
        return 4

def eh_clipe_ao_vivo_real(clip, twitch, user_id):
    """
    Determina se um clipe pertence à live atual (CLIPE AO VIVO) ou a uma live anterior (CLIPE DO VOD).

    Regras:
    - Se o streamer estiver online.
    - Se o VOD mais recente for o mesmo do clipe.
    - Se o clipe tiver sido criado dentro da duração da live atual.

    Caso contrário, é considerado um clipe do VOD antigo.
    """
    stream = twitch.get_stream_info(user_id)
    if not stream:
        return False  # streamer offline, clipe nunca é "ao vivo"

    vod = twitch.get_latest_vod(user_id)
    if not vod:
        return False

    # O ID do VOD (video) precisa bater com o ID do clipe
    if str(clip.get("video_id")) != str(vod["id"]):
        return False

    # Tempo de início da transmissão (VOD)
    vod_start = datetime.fromisoformat(vod["created_at"].replace("Z", "+00:00"))

    # Tempo atual (agora) e do clipe
    agora = datetime.now(timezone.utc)
    clip_created = datetime.fromisoformat(clip["created_at"].replace("Z", "+00:00"))

    # Se o clipe foi criado dentro da duração da live atual, é AO VIVO
    return vod_start <= clip_created <= agora

def montar_descricao(streamer_nome, stream_status, minimo_clipes, intervalo_grupo):
    status_emoji = "🟢 ONLINE" if stream_status == "ONLINE" else "🔴 OFFLINE"
    return (
        f"O CLIPADOR ESTÁ ONLINE 😎\n"
        f"👀 @{streamer_nome} - {status_emoji}\n"
        f"🔥 CRITÉRIO - Grupo de {minimo_clipes} clipes em {intervalo_grupo}s\n\n"
        f"Criado por @euw3ll"
    )
