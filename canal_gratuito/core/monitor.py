from datetime import datetime, timedelta, timezone
from configuracoes import MODO_MONITORAMENTO

MODOS_MONITORAMENTO = {
    "MODO_LOUCO": {
        "min_clipes": [1, 2, 3],
        "intervalo_segundos": 150,
        "frequencia_monitoramento": 15,
    },
    "MODO_PADRAO": {
        "min_clipes": [2, 3, 4, 5],
        "intervalo_segundos": 90,
        "frequencia_monitoramento": 30,
    },
    "MODO_CIRURGICO": {
        "min_clipes": [3, 4, 5, 6],
        "intervalo_segundos": 45,
        "frequencia_monitoramento": 60,
    },
}

# 🔧 Extraído do modo ativo
config_modo = MODOS_MONITORAMENTO[MODO_MONITORAMENTO]
INTERVALO_SEGUNDOS = config_modo["intervalo_segundos"]
INTERVALO_MONITORAMENTO = config_modo["frequencia_monitoramento"]
VALORES_CLIPES_POR_VIEWERS = config_modo["min_clipes"]


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
        return VALORES_CLIPES_POR_VIEWERS[0]
    elif viewers <= 50000:
        return VALORES_CLIPES_POR_VIEWERS[1]
    elif viewers <= 100000:
        return VALORES_CLIPES_POR_VIEWERS[2]
    else:
        return VALORES_CLIPES_POR_VIEWERS[3]

def eh_clipe_ao_vivo_real(clip, twitch, user_id):
    stream = twitch.get_stream_info(user_id)
    if not stream:
        return False

    vod = twitch.get_latest_vod(user_id)
    if not vod:
        return False

    if str(clip.get("video_id")) != str(vod["id"]):
        return False

    vod_start = datetime.fromisoformat(vod["created_at"].replace("Z", "+00:00"))
    agora = datetime.now(timezone.utc)
    clip_created = datetime.fromisoformat(clip["created_at"].replace("Z", "+00:00"))

    return vod_start <= clip_created <= agora

def montar_descricao(streamer_nome, stream_status, minimo_clipes, intervalo_grupo):
    status_emoji = "🟢 ONLINE" if stream_status == "ONLINE" else "🔴 OFFLINE"
    return (
        f"O CLIPADOR ESTÁ ONLINE 😎\n"
        f"👀 @{streamer_nome} - {status_emoji}\n"
        f"🔥 CRITÉRIO - Grupo de {minimo_clipes} clipes em {intervalo_grupo}s\n\n"
        f"Criado por @euw3ll"
    )
