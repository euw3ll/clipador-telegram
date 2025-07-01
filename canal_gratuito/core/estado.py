import json
import os
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CAMINHO_ESTADO = os.path.join("memoria", "estado.json")

def carregar_estado():
    """Carrega o estado do arquivo JSON."""
    os.makedirs(os.path.dirname(CAMINHO_ESTADO), exist_ok=True)
    if not os.path.exists(CAMINHO_ESTADO):
        return {"clipes_enviados": [], "streamers_monitorados": []}
    try:
        with open(CAMINHO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logger.warning("Arquivo estado.json não encontrado ou corrompido. Criando um novo.")
        return {"clipes_enviados": [], "streamers_monitorados": []}

def salvar_estado(estado: dict):
    """Salva o estado atual no arquivo JSON e remove clipes enviados há mais de 2 horas."""
    agora = datetime.now(timezone.utc)
    limite_tempo = agora - timedelta(hours=2)

    if "clipes_enviados" in estado and isinstance(estado["clipes_enviados"], list):
        clipes_recentes = []
        total_antes = len(estado["clipes_enviados"])

        for clipe in estado["clipes_enviados"]:
            try:
                if isinstance(clipe, dict) and "enviado_em" in clipe:
                    timestamp_clipe = datetime.fromisoformat(clipe["enviado_em"])
                    if timestamp_clipe >= limite_tempo:
                        clipes_recentes.append(clipe)
                else:
                    clipes_recentes.append(clipe)
            except (ValueError, TypeError):
                logger.warning(f"Timestamp inválido encontrado no estado.json: {clipe.get('enviado_em')}")
                clipes_recentes.append(clipe)
        
        removidos = total_antes - len(clipes_recentes)
        if removidos > 0:
            logger.info(f"Limpeza de estado.json: {removidos} clipes com mais de 2 horas foram removidos.")

        estado["clipes_enviados"] = clipes_recentes

    try:
        with open(CAMINHO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=4)
    except Exception as e:
        logger.error(f"Erro ao salvar o arquivo de estado: {e}", exc_info=True)

def registrar_clipe_enviado(clipe_id: str, streamer: str):
    """Registra um novo clipe como enviado e salva o estado (com limpeza)."""
    estado = carregar_estado()
    agora_iso = datetime.now(timezone.utc).isoformat()
    estado["clipes_enviados"].append({"id": clipe_id, "streamer": streamer, "enviado_em": agora_iso})
    salvar_estado(estado)

def verificar_clipe_ja_enviado(clipe_id: str) -> bool:
    """Verifica se um clipe já foi enviado lendo o estado atual."""
    estado = carregar_estado()
    return any(clipe.get("id") == clipe_id for clipe in estado.get("clipes_enviados", []))