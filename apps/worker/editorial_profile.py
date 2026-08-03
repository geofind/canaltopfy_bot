"""Perfil editorial de descoberta inspirado em curadorias tech observadas.

Não altera o Topfy Score nem aprova produto sozinho. Apenas ordena candidatos
para que o orçamento limitado do ciclo avalie primeiro ofertas com maior
afinidade editorial. Link, preço, score e deduplicação continuam obrigatórios.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


PROFILE_KEY = "tech_curator_v2"


# Mescla editorial dos tres canais de referencia. Os percentuais orientam a
# ordem da fila conforme o inventario disponivel; nao substituem score, mix de
# marketplaces ou validacoes comerciais.
TECH_EDITORIAL_TARGETS: dict[str, int] = {
    "cupons": 10,
    "componentes_pc": 20,
    "games_controles": 20,
    "monitores_tvs": 14,
    "notebooks": 14,
    "perifericos": 9,
    "audio": 8,
    "celulares": 4,
    "outros_tech": 1,
}


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


# Prioridade máxima por sinal, não soma: títulos longos não ganham vantagem
# apenas por repetirem várias palavras comerciais.
EDITORIAL_SIGNALS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("pc_gpu", 5, ("placa de video", "gpu", "rtx 50", "rx 580")),
    ("pc_motherboard", 5, ("placa mae", "b550", "b450", "x99")),
    ("pc_cpu", 5, ("processador ryzen", "ryzen 5", "ryzen 7", "xeon e5")),
    ("pc_memory_storage", 5, (
        "memoria ram", "ddr4", "ddr5", "ssd nvme", "ssd sata")),
    ("pc_build", 4, (
        "gabinete", "mini itx", "water cooler", "air cooler",
        "kit fans", "fan argb", "fonte 650w", "fonte atx", "fonte sfx")),
    ("gaming_controls", 5, (
        "hall effect", "controle gamer", "gamepad", "gamesir", "8bitdo",
        "machenike")),
    ("gaming_consoles", 4, (
        "console portatil", "playstation 5", "nintendo switch")),
    ("gaming_notebooks", 5, (
        "notebook gamer", "notebook asus tuf", "notebook lenovo loq",
        "acer nitro", "rtx 4050", "rtx 5050")),
    ("displays", 5, (
        "monitor gamer", "144hz", "165hz", "180hz", "240hz",
        "qhd 180hz", "qhd 200hz", "dual mode", "smart tv", "qled")),
    ("enthusiast_peripherals", 4, (
        "teclado mecanico", "mouse gamer", "attack shark", "mchose",
        "redragon", "delux m900", "webcam fifine")),
    ("enthusiast_audio", 4, (
        "headset gamer", "headset sem fio", "headphone planar",
        "microfone dinamico", "fifine am8", "corsair hs80",
        "jbl quantum", "hifiman")),
)


def editorial_bucket(title: Any, category: Any = "") -> str:
    """Classifica uma oferta em um dos pilares da mescla editorial."""
    combined = f" {_normalized(title)} {_normalized(category)} "

    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("cupons", ("cupom", "coupon", "voucher")),
        ("notebooks", ("notebook", "laptop", "macbook")),
        ("monitores_tvs", (
            "monitor", "smart tv", "televisor", "televisao", "oled")),
        ("games_controles", (
            "controle gamer", "controle sem fio", "gamepad", "joystick",
            "gamesir", "8bitdo", "flydigi", "playstation", "xbox",
            "nintendo switch", "console", "volante gamer")),
        ("celulares", ("smartphone", "celular", "iphone", "galaxy")),
        ("audio", (
            "headset", "headphone", "fone", "earbuds", "microfone",
            "caixa de som")),
        ("perifericos", (
            "mouse", "teclado", "keyboard", "webcam", "mousepad")),
        ("componentes_pc", (
            "placa de video", "gpu", "placa mae", "motherboard",
            "processador", "cpu", "ryzen", "xeon", "memoria ram",
            "ddr4", "ddr5", "ssd", "nvme", "gabinete", "mini itx",
            "water cooler", "air cooler", "fan argb", "fonte atx",
            "fonte sfx")),
    )
    for bucket, terms in rules:
        if any(f" {_normalized(term)} " in combined for term in terms):
            return bucket
    return "outros_tech"


def redistribute_by_editorial_mix(
    items: list[dict[str, Any]],
    targets: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Intercala pilares pela meta, preservando itens e sua ordem interna."""
    desired = targets or TECH_EDITORIAL_TARGETS
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        bucket = editorial_bucket(item.get("title"), item.get("category"))
        groups.setdefault(bucket, []).append(item)
    if len(groups) < 2:
        return list(items)

    target_total = max(1, sum(max(0, desired.get(key, 0)) for key in groups))
    used = {key: 0 for key in groups}
    result: list[dict[str, Any]] = []
    while any(groups.values()):
        position = len(result) + 1
        available = [key for key, group in groups.items() if group]
        bucket = max(
            available,
            key=lambda key: (
                desired.get(key, 0) * position / target_total - used[key],
                desired.get(key, 0),
            ),
        )
        result.append(groups[bucket].pop(0))
        used[bucket] += 1
    return result


def editorial_affinity(title: Any, category: Any = "") -> dict[str, Any]:
    """Devolve prioridade editorial explicável entre zero e cinco."""
    combined = f" {_normalized(title)} {_normalized(category)} "
    matches = [
        (key, priority)
        for key, priority, terms in EDITORIAL_SIGNALS
        if any(f" {_normalized(term)} " in combined for term in terms)
    ]
    return {
        "profile": PROFILE_KEY,
        "priority": max((priority for _, priority in matches), default=0),
        "signals": [key for key, _ in matches],
    }


def sort_by_editorial_affinity(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prioriza afinidade, depois desconto e vendas, preservando o conjunto."""
    decorated = []
    for position, candidate in enumerate(candidates):
        affinity = editorial_affinity(
            candidate.get("title"), candidate.get("category"))
        try:
            discount = float(candidate.get("discount_percent") or 0)
        except (TypeError, ValueError):
            discount = 0.0
        try:
            sold = int(candidate.get("sold_count") or 0)
        except (TypeError, ValueError):
            sold = 0
        decorated.append((
            -int(affinity["priority"]), -discount, -sold, position, candidate))
    decorated.sort(key=lambda row: row[:4])
    return [row[-1] for row in decorated]
