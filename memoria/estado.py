import json
import os
from datetime import datetime, timezone

ESTADO_PATH = "memoria/estado_bot.json"

def carregar_estado():
    if not os.path.exists(ESTADO_PATH):
        estado_inicial = {
            "ultima_execucao": None,
            "ultimo_envio_promocional": 0,
            "ultimo_envio_header": 0,
            "ultimo_envio_atualizacao_streamers": 0,
            "grupos_enviados": []
        }
        salvar_estado(estado_inicial)
        return estado_inicial

    with open(ESTADO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_estado(estado):
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

def atualizar_execucao(estado):
    estado["ultima_execucao"] = datetime.now(timezone.utc).isoformat()
    salvar_estado(estado)

def grupo_ja_enviado(grupo, grupos_enviados):
    inicio = grupo["inicio"].isoformat()
    fim = grupo["fim"].isoformat()
    return any(g["inicio"] == inicio and g["fim"] == fim for g in grupos_enviados)

def adicionar_grupo_enviado(grupo, estado):
    estado["grupos_enviados"].append({
        "inicio": grupo["inicio"].isoformat(),
        "fim": grupo["fim"].isoformat()
    })
    salvar_estado(estado)
