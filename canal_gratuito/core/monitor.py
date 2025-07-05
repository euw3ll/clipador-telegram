from datetime import datetime, timedelta, timezone
from typing import Callable, Union

# Modos antigos (mantidos apenas para uso futuro nos canais privados)
MODOS_MONITORAMENTO = {
    "MODO_LOUCO": {"min_clipes": 2, "intervalo_segundos": 150},
    "MODO_PADRAO": {"min_clipes": 3, "intervalo_segundos": 90},
    "MODO_CIRURGICO": {"min_clipes": 5, "intervalo_segundos": 60},
    # MODO_AUTOMATICO usará o padrão
    "AUTOMATICO": {"min_clipes": 3, "intervalo_segundos": 90},
}

# Critério fixo para o canal gratuito
INTERVALO_SEGUNDOS = 120
INTERVALO_MONITORAMENTO = 30
MINIMO_CLIPES = 3

def agrupar_clipes_por_proximidade(
    clipes,
    intervalo_segundos: int,
    criterio_min_clipes: Union[int, Callable[[int], int]]
):
    clipes_ordenados = sorted(
        clipes,
        key=lambda c: datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
    )

    grupos = []
    usados = set()

    for i, clipe_base in enumerate(clipes_ordenados):
        if clipe_base["id"] in usados:
            continue

        base_time = datetime.fromisoformat(clipe_base["created_at"].replace("Z", "+00:00"))
        grupo = [clipe_base]
        usados_temp = {clipe_base["id"]}

        for j in range(i + 1, len(clipes_ordenados)):
            outro_clipe = clipes_ordenados[j]
            outro_time = datetime.fromisoformat(outro_clipe["created_at"].replace("Z", "+00:00"))
            delta = (outro_time - base_time).total_seconds()

            if delta <= intervalo_segundos and outro_clipe["id"] not in usados:
                grupo.append(outro_clipe)
                usados_temp.add(outro_clipe["id"])
            else:
                break

        # Obtém o valor mínimo de clipes para este grupo
        # Se o critério for uma função, chama a função passando os viewers e usa o resultado.
        # Se for um inteiro, usa o valor diretamente.
        minimo_para_este_grupo = criterio_min_clipes(clipe_base.get('viewer_count', 0)) if callable(criterio_min_clipes) else criterio_min_clipes


        if len(grupo) >= minimo_para_este_grupo:
            grupos.append({
                "inicio": base_time,
                "fim": grupo[-1]["created_at"],
                "clipes": grupo
            })
            usados.update(usados_temp)

    return grupos

def get_time_minutes_ago(minutes=5):
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return dt.isoformat().replace("+00:00", "Z")

def minimo_clipes_por_viewers(viewers: int) -> int:
    """
    Define a quantidade mínima de clipes necessários com base na contagem de espectadores.
    Quanto maior a audiência, mais exigente o critério se torna.
    """
    if viewers < 1000:
        return 2  # Para streamers menores, 2 clipes já é um bom sinal
    elif viewers < 5000:
        return 3  # Para streamers médios, o padrão
    elif viewers < 15000:
        return 4  # Para streamers grandes, precisa de mais gente clipando
    else: # 15k+ viewers
        return 5  # Para gigantes, o evento precisa ser muito forte

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