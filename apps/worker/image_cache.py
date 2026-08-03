"""Cache local de imagens (fundação preventiva).

Hoje nada grava arquivo aqui — Telegram baixa a foto pra memória e descarta
(publishers/telegram.py) e o card /og/card é gerado on-the-fly pelo Next.js,
sem persistir nada. Este módulo só existe pra já ter um lugar único e uma
rotina de limpeza prontos pro dia em que alguma etapa passar a guardar
imagem localmente — sem isso, cada ponto novo inventaria seu próprio cache.

Limpeza é sempre manual (botão em /sistema) — nunca automática; nunca apaga
nada fora de `CACHE_DIR`.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

CACHE_DIR = Path(os.environ.get("IMAGE_CACHE_DIR") or
                 Path(__file__).resolve().parent / ".cache" / "images")


def save(name: str, content: bytes) -> Path:
    """Grava bytes no cache local; cria o diretório se preciso.

    `name` nunca é usado como caminho — só o nome de arquivo (`Path(name).name`)
    é aceito, pra um `name` com "../" ou separador não escapar de CACHE_DIR."""
    nome_seguro = Path(name).name
    if not nome_seguro or nome_seguro in {".", ".."}:
        raise ValueError(f"nome de arquivo inválido para o cache: {name!r}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    destino = CACHE_DIR / nome_seguro
    destino.write_bytes(content)
    return destino


def usage() -> dict[str, Any]:
    """Quantos arquivos e bytes o cache local ocupa agora."""
    if not CACHE_DIR.exists():
        return {"files": 0, "bytes": 0}
    arquivos = [item for item in CACHE_DIR.rglob("*") if item.is_file()]
    return {
        "files": len(arquivos),
        "bytes": sum(item.stat().st_size for item in arquivos),
    }


def disk_usage(path: str = ".") -> dict[str, int]:
    """Espaço em disco do volume onde o worker roda (host inteiro, não só
    o cache) — pra ver se a máquina está ficando sem espaço."""
    total, used, free = shutil.disk_usage(path)
    return {"total_bytes": total, "used_bytes": used, "free_bytes": free}


def cleanup_all() -> dict[str, Any]:
    """Apaga tudo em CACHE_DIR — ação manual (botão em /sistema), nunca
    chamada por um agendador. Devolve quantos arquivos/bytes liberou."""
    if not CACHE_DIR.exists():
        return {"removed": 0, "freed_bytes": 0}
    arquivos = [item for item in CACHE_DIR.rglob("*") if item.is_file()]
    freed = sum(item.stat().st_size for item in arquivos)
    for item in arquivos:
        item.unlink(missing_ok=True)
    return {"removed": len(arquivos), "freed_bytes": freed}
