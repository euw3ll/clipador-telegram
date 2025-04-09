from datetime import datetime, timedelta

def agrupar_clipes_por_proximidade(clipes, intervalo_segundos=30, minimo_clipes=3):
    # Ordena os clipes por data de criação
    clipes_ordenados = sorted(
        clipes,
        key=lambda c: datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
    )

    grupos = []
    usados = set()  # IDs dos clipes já agrupados

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
                break  # Passou da janela

        # Evita duplicidade e respeita o mínimo de clipes
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
    # Já validado no agrupamento, mas mantido por compatibilidade
    return [grupo for grupo in grupos if len(grupo["clipes"]) >= minimo_clipes]
