"""Regras comerciais verificáveis compartilhadas pelo worker."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Iterable, Optional


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


TITLE_NOISE = {
    "novo", "nova", "original", "lacrado", "frete", "gratis", "envio",
    "rapido", "rapida", "promocao", "oferta", "com", "sem", "de", "da",
    "do", "das", "dos", "para", "e", "em", "no", "na",
}


def titles_similar(first: Any, second: Any, threshold: float = 0.6) -> bool:
    """Semelhança conservadora para comparar o mesmo produto entre anúncios."""
    a = {term for term in _normalized(first).split() if term not in TITLE_NOISE}
    b = {term for term in _normalized(second).split() if term not in TITLE_NOISE}
    return bool(a and b) and len(a & b) / len(a | b) >= threshold


# Famílias específicas vêm antes das genéricas. Isso aproxima categorias que
# lojas diferentes nomeiam de maneiras diferentes sem transformar todo o
# departamento "Eletrônicos" em uma única categoria.
CATEGORY_FAMILY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("carregadores", ("carregador", "charger", "charging station", "fonte usb")),
    ("power-banks", ("power bank", "bateria externa")),
    ("celulares", ("smartphone", "celular", "iphone", "telefone movel")),
    ("monitores", ("monitor", "monitores")),
    ("notebooks", ("notebook", "laptop", "macbook")),
    ("tablets", ("tablet", "ipad")),
    ("fones", ("fone", "headphone", "headset", "earphone", "earbuds")),
    ("smartwatches", ("smartwatch", "relogio inteligente")),
    ("televisores", ("smart tv", "televisor", "televisao")),
    ("consoles", ("playstation", "xbox", "nintendo switch", "console")),
    ("controles", ("controle gamer", "gamepad", "joystick")),
    ("teclados", ("teclado", "keyboard")),
    ("mouses", ("mouse",)),
    ("ssds", ("ssd", "solid state drive")),
    ("placas-mae", ("placa mae", "motherboard", "b550", "b450", "x99")),
    ("processadores", ("processador", "cpu", "ryzen", "xeon")),
    ("memorias", ("memoria ram", "ddr4", "ddr5", "sodimm")),
    ("placas-video", ("placa de video", "gpu", "rtx", "rx 580")),
    ("fontes-pc", ("fonte atx", "fonte sfx", "fonte 650w", "power supply")),
    ("refrigeracao-pc", ("water cooler", "air cooler", "kit fans", "fan argb")),
    ("gabinetes-pc", ("gabinete", "mini itx", "case pc")),
    ("air-fryers", ("air fryer", "fritadeira eletrica")),
    ("aspiradores", ("aspirador", "robot vacuum")),
)


def category_family(category: Any, title: Any = "") -> Optional[str]:
    """Família estreita para impedir dois produtos equivalentes seguidos."""
    combined = f"{_normalized(category)} {_normalized(title)}".strip()
    if not combined:
        return None
    padded = f" {combined} "
    for family, terms in CATEGORY_FAMILY_TERMS:
        if any(f" {_normalized(term)} " in padded for term in terms):
            return family
    normalized_category = _normalized(category)
    if not normalized_category:
        return None
    # A folha costuma ser o trecho mais específico do caminho da API.
    parts = [part.strip() for part in re.split(r"\s*>\s*", str(category)) if part.strip()]
    return f"api:{_normalized(parts[-1])}"


def is_blocked_by_word(
    title: Any, category: Any, blocklist: Iterable[dict[str, Any]],
) -> Optional[str]:
    """Palavra/frase bloqueada pela curadoria do Laboratório de Captura —
    testa contra título+categoria normalizados; ignora bloqueios
    temporários já expirados (nunca inventa expiração: só respeita o que
    veio de `expires_at`). Devolve o termo que bateu, ou None."""
    combined = f" {_normalized(title)} {_normalized(category)} ".strip()
    if not combined:
        return None
    padded = f" {combined} "
    now = datetime.now(timezone.utc)
    for entry in blocklist:
        expires_at = entry.get("expires_at")
        if expires_at:
            try:
                expira_em = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            except ValueError:
                expira_em = None
            if expira_em and expira_em <= now:
                continue
        termo = entry.get("term")
        if not termo:
            continue
        if f" {_normalized(termo)} " in padded:
            return termo
    return None


def category_lock_reason(config: Optional[dict[str, Any]]) -> Optional[str]:
    """Motivo de bloqueio vindo da curadoria do Laboratório de Captura
    (/campanhas) — categoria pausada manualmente ou travada por um tempo
    determinado. Sem linha configurada pra essa família, nunca bloqueia
    (ausência de configuração é liberação, não bloqueio)."""
    if not config:
        return None
    if not config.get("active", True):
        return "categoria pausada pela curadoria"
    locked_until = config.get("locked_until")
    if locked_until:
        try:
            travado_ate = datetime.fromisoformat(str(locked_until).replace("Z", "+00:00"))
        except ValueError:
            return None
        if travado_ate > datetime.now(timezone.utc):
            return f"categoria travada até {locked_until}"
    return None


def avoid_consecutive_categories(
    items: list[dict[str, Any]], *, previous_family: Optional[str] = None
) -> list[dict[str, Any]]:
    """Reordena sem perder itens; adia famílias repetidas sempre que possível."""
    remaining = list(items)
    result: list[dict[str, Any]] = []
    last = previous_family
    while remaining:
        index = next(
            (i for i, item in enumerate(remaining)
             if not item.get("category_family") or item.get("category_family") != last),
            0,
        )
        chosen = remaining.pop(index)
        result.append(chosen)
        last = chosen.get("category_family") or None
    return result


# Sentinela por identidade (nunca por string) pro bucket "sem meta" —
# family_key vem de texto digitado pelo usuário (/campanhas), então uma
# categoria real chamada "outros" não pode colidir com o bucket interno.
_SEM_META = object()


def redistribute_by_category_targets(
    items: list[dict[str, Any]], targets: dict[str, int],
) -> list[dict[str, Any]]:
    """Intercala itens pelas metas de percentual por categoria definidas na
    curadoria do Laboratório de Captura (/campanhas) — categorias sem meta
    somam num bucket que preenche o restante. Preserva todos os itens e a
    ordem interna de cada grupo; espera `item["category_family"]` já
    calculado (mesmo padrão de `avoid_consecutive_categories`)."""
    managed = {key: max(0, min(100, int(value)))
              for key, value in targets.items() if value}
    if not managed:
        return list(items)
    groups: dict[Any, list[dict[str, Any]]] = {}
    for item in items:
        family = item.get("category_family")
        key = family if family in managed else _SEM_META
        groups.setdefault(key, []).append(item)
    if len(groups) < 2:
        return list(items)

    desired: dict[Any, int] = dict(managed)
    desired[_SEM_META] = max(0, 100 - sum(managed.values()))
    target_total = max(1, sum(desired.get(key, 0) for key in groups))
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


def deal_highlight(
    *, current_price: Any, original_price: Any,
    historical_prices: Iterable[Any] = (), lookback_days: int = 30,
) -> Optional[dict[str, Any]]:
    """Retorna destaque somente com desconto real ou menor preço comprovado."""
    try:
        current = float(current_price)
    except (TypeError, ValueError):
        return None
    if current <= 0:
        return None

    try:
        original = float(original_price)
    except (TypeError, ValueError):
        original = 0.0
    if original > current:
        discount = (1 - current / original) * 100
        if discount > 50:
            return {
                "level": "MUST_SEE",
                "reason": "DISCOUNT_OVER_50",
                "discount_pct": round(discount, 2),
            }

    history: list[float] = []
    for value in historical_prices:
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            history.append(price)
    if history and current < min(history):
        return {
            "level": "MUST_SEE",
            "reason": "RECENT_LOW",
            "lookback_days": int(lookback_days),
            "previous_low": round(min(history), 2),
        }
    return None
