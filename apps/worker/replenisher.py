"""Agente interno de reabastecimento da fila de ofertas.

O agente trabalha por reserva: quando a fila cai abaixo de ``min_items``,
reaproveita campanhas aprovadas ainda não publicadas e captura novas ofertas
do AliExpress pela API oficial até ``target_items``. O trabalho mais lento roda
fora do loop de publicação (o launcher fica em ``main.py``).

Links do Mercado Livre nunca são fabricados. Quando existe um bridge Hermes
configurado, o agente envia a ele as URLs candidatas e só aceita respostas que
declarem ter usado a ferramenta oficial. Sem bridge, registra a demanda para
Hermes e mantém a reserva com AliExpress, sem pedir intervenção ao usuário.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import math
import random
from typing import Any, Optional

import requests

import db
from editorial_profile import redistribute_by_editorial_mix
from offer_rules import (avoid_consecutive_categories, category_family,
                         redistribute_by_category_targets)
from pipeline import ciclo_automatico, validar_link_afiliado_ml


@dataclass(frozen=True)
class ReplenisherConfig:
    organization_id: str
    queue_id: str
    terms: tuple[str, ...]
    # Com posts a cada 5 minutos: dispara em 7h e volta a 8h. A hora de
    # margem cobre o tempo de consulta às APIs sem cair abaixo das 6h.
    min_items: int = 84
    target_items: int = 96
    max_new_per_cycle: int = 4
    min_score: float = 35.0
    interval_minutes: int = 5
    shopee_target_percent: int = 40
    aliexpress_target_percent: int = 10
    ml_target_percent: int = 30
    magalu_target_percent: int = 20
    enforce_source_mix: bool = False
    hermes_url: Optional[str] = None
    hermes_token: Optional[str] = None

    def validate(self) -> None:
        if not self.organization_id or not self.queue_id:
            raise ValueError("replenisher exige organization_id e queue_id")
        if not self.terms:
            raise ValueError("replenisher exige ao menos um termo AliExpress")
        if self.min_items < 1:
            raise ValueError("min_items deve ser positivo")
        if self.target_items <= self.min_items:
            raise ValueError("target_items deve ser maior que min_items")
        if self.max_new_per_cycle < 1:
            raise ValueError("max_new_per_cycle deve ser positivo")
        if self.interval_minutes < 1:
            raise ValueError("interval_minutes deve ser positivo")
        percentages = self.source_target_percentages()
        if any(not 0 <= value <= 100 for value in percentages.values()):
            raise ValueError("percentuais das fontes devem ficar entre 0 e 100")
        if sum(percentages.values()) != 100:
            raise ValueError("percentuais das fontes devem somar 100")

    def source_target_percentages(self) -> dict[str, int]:
        return {
            "shopee": self.shopee_target_percent,
            "aliexpress": self.aliexpress_target_percent,
            "mercadolivre": self.ml_target_percent,
            "magalu": self.magalu_target_percent,
        }


def _config_with_saved_mix(config: ReplenisherConfig) -> ReplenisherConfig:
    """Lê o mix salvo na fila; env vars continuam sendo fallback seguro."""
    if not config.enforce_source_mix:
        return config
    try:
        rows = (db._get().table("queues").select(
            "shopee_target_percent,aliexpress_target_percent,"
            "mercadolivre_target_percent,magalu_target_percent")
                .eq("id", config.queue_id)
                .eq("organization_id", config.organization_id)
                .limit(1).execute().data or [])
    except Exception:
        # Compatibilidade durante rollout: antes da migration, mantém o .env.
        return config
    if not rows:
        return config
    row = rows[0]
    try:
        saved = replace(
            config,
            shopee_target_percent=int(row["shopee_target_percent"]),
            aliexpress_target_percent=int(row["aliexpress_target_percent"]),
            ml_target_percent=int(row["mercadolivre_target_percent"]),
            magalu_target_percent=int(row["magalu_target_percent"]),
        )
        saved.validate()
        return saved
    except (KeyError, TypeError, ValueError):
        return config


def _config_with_saved_min_score(config: ReplenisherConfig) -> ReplenisherConfig:
    """Lê o corte de score definido no Laboratório de Captura (/campanhas);
    a env var (`min_score` do dataclass) continua sendo o fallback seguro
    enquanto a organização não configurar nada pela tela."""
    try:
        row = (db._get().table("discovery_settings").select("min_score")
               .eq("organization_id", config.organization_id)
               .maybe_single().execute().data)
    except Exception:
        # Compatibilidade durante rollout: antes da migration, mantém o .env.
        return config
    if not row or row.get("min_score") is None:
        return config
    try:
        return replace(config, min_score=float(row["min_score"]))
    except (TypeError, ValueError):
        return config


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _active_items(queue_id: str) -> list[dict[str, Any]]:
    response = (db._get().table("queue_items").select(
        "id,campaign_id,status,scheduled_at,"
        "campaign:campaigns(product:products(source_name))")
                .eq("queue_id", queue_id)
                .in_("status", ["PENDING", "DISPATCHED"]).execute())
    return response.data or []


def _source_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"shopee": 0, "aliexpress": 0, "mercadolivre": 0, "magalu": 0}
    for item in items:
        campaign = item.get("campaign") or {}
        if isinstance(campaign, list):
            campaign = campaign[0] if campaign else {}
        product = campaign.get("product") or {}
        if isinstance(product, list):
            product = product[0] if product else {}
        source = str(item.get("source_name") or product.get("source_name") or "")
        if source in counts:
            counts[source] += 1
    return counts


def _retire_excess_pending(config: ReplenisherConfig,
                           items: list[dict[str, Any]], *, now: datetime,
                           max_items: int) -> list[str]:
    """Abre espaço gradualmente, sem apagar campanhas já aprovadas.

    Somente vínculos PENDING distantes da próxima publicação são cancelados;
    campanha, produto, conteúdo e link continuam aprovados no inventário e
    podem voltar à fila quando a meta daquela fonte pedir.
    """
    counts = _source_counts(items)
    targets = {
        source: round(config.target_items * percent / 100)
        for source, percent in config.source_target_percentages().items()
    }
    excess = {
        source: max(0, counts.get(source, 0) - targets[source])
        for source in targets
    }
    cutoff = now + timedelta(minutes=config.interval_minutes * 2)
    candidates: list[tuple[datetime, dict[str, Any], str]] = []
    for item in items:
        if item.get("status") != "PENDING" or not item.get("scheduled_at"):
            continue
        scheduled_at = _parse_iso(str(item["scheduled_at"]))
        if scheduled_at <= cutoff:
            continue
        source_counts = _source_counts([item])
        source = next((name for name, count in source_counts.items() if count), "")
        if source and excess.get(source, 0) > 0:
            candidates.append((scheduled_at, item, source))
    candidates.sort(key=lambda row: row[0], reverse=True)
    retired: list[str] = []
    for _, item, source in candidates:
        if len(retired) >= max_items or excess[source] <= 0:
            continue
        (db._get().table("queue_items").update({"status": "CANCELLED"})
         .eq("id", item["id"]).eq("status", "PENDING").execute())
        retired.append(str(item["id"]))
        excess[source] -= 1
    return retired


def _next_schedule(queue_id: str, *, now: datetime,
                   interval_minutes: int) -> datetime:
    rows = (db._get().table("queue_items").select("scheduled_at")
            .eq("queue_id", queue_id)
            .in_("status", ["PENDING", "DISPATCHED"])
            .order("scheduled_at", desc=True).limit(1).execute().data or [])
    tail = _parse_iso(rows[0]["scheduled_at"]) if rows else now
    return max(now, tail) + timedelta(minutes=interval_minutes)


def _campaign_already_used(campaign_id: str) -> bool:
    queued = (db._get().table("queue_items").select("id")
              .eq("campaign_id", campaign_id).neq("status", "CANCELLED")
              .limit(1).execute().data or [])
    if queued:
        return True
    published = (db._get().table("publications").select("id")
                 .eq("campaign_id", campaign_id).neq("status", "CANCELLED")
                 .limit(1).execute().data or [])
    return bool(published)


def _approved_content_id(campaign_id: str) -> Optional[str]:
    rows = (db._get().table("contents").select("id")
            .eq("campaign_id", campaign_id).eq("status", "APPROVED")
            .order("created_at").limit(1).execute().data or [])
    return str(rows[0]["id"]) if rows else None


def _enqueue_campaigns(config: ReplenisherConfig,
                       campaign_ids: list[str], *, now: datetime) -> list[str]:
    """Enfileira sem duplicar e sempre depois da cauda já programada."""
    inserted: list[str] = []
    scheduled_at = _next_schedule(
        config.queue_id, now=now, interval_minutes=config.interval_minutes)
    for campaign_id in campaign_ids:
        if _campaign_already_used(campaign_id):
            continue
        content_id = _approved_content_id(campaign_id)
        if not content_id:
            continue
        db._get().table("queue_items").insert({
            "organization_id": config.organization_id,
            "queue_id": config.queue_id,
            "campaign_id": campaign_id,
            "content_id": content_id,
            "scheduled_at": scheduled_at.isoformat(),
        }).execute()
        inserted.append(campaign_id)
        scheduled_at += timedelta(minutes=config.interval_minutes)
    return inserted


def _randomized_items(items: list[dict[str, Any]], *,
                      rng: Optional[random.Random] = None,
                      target_percentages: Optional[dict[str, int]] = None
                      ) -> list[dict[str, Any]]:
    """Distribui qualquer número de fontes pela meta, ponderando o score."""
    generator = rng or random.SystemRandom()
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(str(item.get("source_name") or "unknown"), []).append(item)
    for source_name, group in groups.items():
        groups[source_name] = redistribute_by_editorial_mix(
            _weighted_score_order(group, rng=generator))
    if len(groups) == 1:
        return next(iter(groups.values()))
    if target_percentages is None:
        total = max(1, len(items))
        target_percentages = {
            source: round(len(group) * 100 / total)
            for source, group in groups.items()
        }
    target_total = max(1, sum(
        max(0, target_percentages.get(source, 0)) for source in groups))
    result: list[dict[str, Any]] = []
    used = {source: 0 for source in groups}
    while any(groups.values()):
        position = len(result) + 1
        available = [source for source, group in groups.items() if group]
        generator.shuffle(available)
        source = max(
            available,
            key=lambda name: (
                target_percentages.get(name, 0) * position / target_total
                - used[name]
            ),
        )
        result.append(groups[source].pop(0))
        used[source] += 1
    return result


def _weighted_score_order(items: list[dict[str, Any]], *,
                          rng: Optional[random.Random] = None
                          ) -> list[dict[str, Any]]:
    """Amostragem ponderada sem reposição pelo Topfy Score.

    O quadrado do score aumenta a preferência por boas ofertas, mas a chave
    exponencial mantém aleatoriedade: score alto não significa posição fixa.
    """
    generator = rng or random.SystemRandom()
    ranked: list[tuple[float, dict[str, Any]]] = []
    for item in items:
        score = max(1.0, float(item.get("score") or 1.0))
        weight = score * score
        draw = max(float(generator.random()), 1e-12)
        ranked.append((-math.log(draw) / weight, item))
    ranked.sort(key=lambda pair: pair[0])
    return [item for _, item in ranked]


def randomize_pending_schedule(config: ReplenisherConfig, *,
                               now: Optional[datetime] = None,
                               protect_slots: int = 2,
                               rng: Optional[random.Random] = None
                               ) -> dict[str, Any]:
    """Embaralha campanhas nos horários futuros sem mudar a cadência.

    Os próximos ``protect_slots`` intervalos ficam intocados para não competir
    com uma publicação que o worker já possa estar iniciando.
    """
    try:
        queue_rows = (db._get().table("queues")
                      .select("manual_order_locked")
                      .eq("id", config.queue_id)
                      .eq("organization_id", config.organization_id)
                      .limit(1).execute().data or [])
        if queue_rows and queue_rows[0].get("manual_order_locked") is True:
            return {"randomized": 0, "reason": "manual_order_locked"}
    except Exception:
        # Compatibilidade segura durante a aplicacao gradual da migration.
        pass

    moment = now or datetime.now(timezone.utc)
    rows = (db._get().table("queue_items")
            .select("id,campaign_id,scheduled_at")
            .eq("queue_id", config.queue_id).eq("status", "PENDING")
            .order("scheduled_at").execute().data or [])
    if len(rows) < 2:
        return {"randomized": 0, "reason": "insufficient_pending_items"}

    protected_count = min(max(0, protect_slots), len(rows))
    protected = rows[:protected_count]
    candidates = rows[protected_count:]

    campaign_ids = [str(row["campaign_id"]) for row in rows]
    campaigns = (db._get().table("campaigns").select("id,product_id")
                 .in_("id", campaign_ids).execute().data or [])
    product_ids = [str(row["product_id"]) for row in campaigns]
    products = (db._get().table("products")
                .select("id,source_name,score,title,category")
                .in_("id", product_ids).execute().data or [])
    campaign_products = {
        str(row["id"]): str(row["product_id"]) for row in campaigns}
    product_sources = {
        str(row["id"]): str(row["source_name"]) for row in products}
    product_scores = {
        str(row["id"]): float(row.get("score") or 1) for row in products}
    product_families = {
        str(row["id"]): category_family(row.get("category"), row.get("title"))
        for row in products}
    product_titles = {
        str(row["id"]): str(row.get("title") or "") for row in products}
    product_categories = {
        str(row["id"]): str(row.get("category") or "") for row in products}
    for row in rows:
        product_id = campaign_products.get(str(row["campaign_id"]), "")
        row["source_name"] = product_sources.get(product_id, "unknown")
        row["score"] = product_scores.get(product_id, 1.0)
        row["category_family"] = product_families.get(product_id)
        row["title"] = product_titles.get(product_id, "")
        row["category"] = product_categories.get(product_id, "")

    previous_family = (
        protected[-1].get("category_family") if protected else None)
    randomized_tail = avoid_consecutive_categories(
        _randomized_items(
            candidates, rng=rng,
            target_percentages=config.source_target_percentages()),
        previous_family=previous_family,
    )
    randomized = [*protected, *randomized_tail]
    # A fila antiga pode conter muitos horarios vencidos. Recria a cadencia
    # completa a partir de agora para que o horario mostrado no painel seja o
    # horario real planejado de publicacao.
    slots = [
        moment + timedelta(minutes=config.interval_minutes * (index + 1))
        for index in range(len(randomized))
    ]
    overdue = sum(
        1 for row in rows
        if row.get("scheduled_at") and _parse_iso(str(row["scheduled_at"])) <= moment
    )
    for row, scheduled_at in zip(randomized, slots):
        db._get().table("queue_items").update({
            "scheduled_at": scheduled_at.isoformat(),
        }).eq("id", row["id"]).eq("status", "PENDING").execute()
    return {"randomized": len(rows),
            "protected_slots": protected_count,
            "overdue_rescheduled": overdue,
            "next_scheduled_at": slots[0].isoformat(),
            "last_scheduled_at": slots[-1].isoformat()}


def force_redistribute_by_category(organization_id: str, queue_id: str, *,
                                   now: Optional[datetime] = None) -> dict[str, Any]:
    """Redistribui os itens PENDING da fila pelas metas de percentual por
    categoria definidas no Laboratório de Captura (/campanhas) — ação
    manual ("forçar aplicação e redistribuição"). Diferente de
    `randomize_pending_schedule`, roda mesmo com `manual_order_locked`
    (é um pedido explícito do usuário sobre categoria, não o embaralhamento
    automático por score/fonte), mas ainda protege o próximo intervalo de
    publicação pra não competir com um envio já em andamento."""
    moment = now or datetime.now(timezone.utc)
    try:
        queue_rows = (db._get().table("queues").select("interval_minutes")
                      .eq("id", queue_id).eq("organization_id", organization_id)
                      .limit(1).execute().data or [])
        interval_minutes = int(queue_rows[0]["interval_minutes"]) if queue_rows else 5
    except Exception:
        interval_minutes = 5
    cutoff = moment + timedelta(minutes=interval_minutes)

    rows = (db._get().table("queue_items")
            .select("id,campaign_id,scheduled_at")
            .eq("queue_id", queue_id).eq("organization_id", organization_id)
            .eq("status", "PENDING").gt("scheduled_at", cutoff.isoformat())
            .order("scheduled_at").execute().data or [])
    if len(rows) < 2:
        return {"redistributed": 0, "reason": "poucos_itens"}

    config = db.get_capture_lab_config(organization_id)
    targets = {key: row.get("target_percent")
              for key, row in config["categories"].items()
              if row.get("target_percent")}
    if not targets:
        return {"redistributed": 0, "reason": "sem_metas_definidas"}

    campaign_ids = [str(row["campaign_id"]) for row in rows]
    campaigns = (db._get().table("campaigns").select("id,product_id")
                 .in_("id", campaign_ids).execute().data or [])
    product_ids = [str(row["product_id"]) for row in campaigns]
    products = (db._get().table("products").select("id,title,category")
                .in_("id", product_ids).execute().data or [])
    campaign_products = {
        str(row["id"]): str(row["product_id"]) for row in campaigns}
    product_families = {
        str(row["id"]): category_family(row.get("category"), row.get("title"))
        for row in products}
    for row in rows:
        product_id = campaign_products.get(str(row["campaign_id"]), "")
        row["category_family"] = product_families.get(product_id)

    slots = [str(row["scheduled_at"]) for row in rows]
    redistributed = redistribute_by_category_targets(rows, targets)
    for row, scheduled_at in zip(redistributed, slots):
        db._get().table("queue_items").update({
            "scheduled_at": scheduled_at,
        }).eq("id", row["id"]).eq("status", "PENDING").execute()
    db.register_audit(
        organization_id, actor_type="worker",
        action="categoria_redistribuicao_forcada", entity_type="queue",
        entity_id=queue_id, metadata={"total": len(rows), "targets": targets})
    return {"redistributed": len(rows)}


def _ready_inventory(config: ReplenisherConfig, limit: int, *,
                     active_counts: Optional[dict[str, int]] = None
                     ) -> list[dict[str, Any]]:
    """Campanhas com link verificado+copy aprovada ainda fora da fila."""
    products = (db._get().table("products")
                .select("id,source_name,score,created_at,title,category")
                .eq("organization_id", config.organization_id)
                .eq("affiliate_link_status", "VERIFIED")
                .not_.is_("affiliate_link", "null").execute().data or [])
    by_product = {str(row["id"]): row for row in products}
    if not by_product:
        return []
    campaigns = (db._get().table("campaigns")
                 .select("id,product_id,status,created_at")
                 .eq("organization_id", config.organization_id)
                 .in_("product_id", list(by_product))
                 .in_("status", ["READY", "APPROVED", "SCHEDULED"])
                 .execute().data or [])
    inventory: list[dict[str, Any]] = []
    for campaign in campaigns:
        campaign_id = str(campaign["id"])
        if _campaign_already_used(campaign_id):
            continue
        if not _approved_content_id(campaign_id):
            continue
        product = by_product[str(campaign["product_id"])]
        inventory.append({
            "campaign_id": campaign_id,
            "source_name": product.get("source_name"),
            "score": float(product.get("score") or 0),
            "created_at": product.get("created_at") or "",
            "title": product.get("title") or "",
            "category": product.get("category") or "",
        })

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in inventory:
        source = str(item.get("source_name") or "unknown")
        groups.setdefault(source, []).append(item)
    for group in groups.values():
        group.sort(key=lambda x: (-x["score"], x["created_at"]))
        group[:] = redistribute_by_editorial_mix(group)
    counts = dict(active_counts or {})
    targets = config.source_target_percentages()
    result: list[dict[str, Any]] = []
    while len(result) < limit and any(groups.values()):
        projected_total = sum(counts.values()) + 1
        available = [source for source, group in groups.items() if group]
        if config.enforce_source_mix:
            available = [
                source for source in available
                if counts.get(source, 0) < round(
                    config.target_items * targets.get(source, 0) / 100)
            ]
        if not available:
            break
        source = max(
            available,
            key=lambda name: (
                targets.get(name, 0) * projected_total / 100
                - counts.get(name, 0)
            ),
        )
        result.append(groups[source].pop(0))
        counts[source] = counts.get(source, 0) + 1
    return result


def _ml_candidates(config: ReplenisherConfig, limit: int) -> list[dict[str, str]]:
    products = (db._get().table("products")
                .select("id,source_url,title")
                .eq("organization_id", config.organization_id)
                .eq("source_name", "mercadolivre").eq("status", "READY")
                .is_("affiliate_link", "null").order("created_at")
                .limit(max(limit * 3, limit)).execute().data or [])
    if not products:
        return []
    by_product = {str(row["id"]): row for row in products}
    campaigns = (db._get().table("campaigns")
                 .select("id,product_id,status")
                 .eq("organization_id", config.organization_id)
                 .eq("status", "READY").in_("product_id", list(by_product))
                 .execute().data or [])
    candidates: list[dict[str, str]] = []
    for campaign in campaigns:
        campaign_id = str(campaign["id"])
        if _campaign_already_used(campaign_id):
            continue
        product = by_product[str(campaign["product_id"])]
        candidates.append({
            "campaign_id": campaign_id,
            "source_url": str(product["source_url"]),
            "title": str(product.get("title") or ""),
        })
        if len(candidates) >= limit:
            break
    return candidates


def _request_hermes_links(config: ReplenisherConfig,
                          candidates: list[dict[str, str]]) -> int:
    if not candidates:
        return 0
    if not config.hermes_url:
        db.register_audit(
            config.organization_id, actor_type="worker",
            action="hermes_linkbuilder_reabastecimento_pendente",
            entity_type="queue", entity_id=config.queue_id,
            metadata={"campaign_ids": [x["campaign_id"] for x in candidates],
                      "total": len(candidates)})
        return 0

    headers = {"Content-Type": "application/json"}
    if config.hermes_token:
        headers["Authorization"] = f"Bearer {config.hermes_token}"
    response = requests.post(
        config.hermes_url,
        json={"organization_id": config.organization_id,
              "queue_id": config.queue_id, "campaigns": candidates},
        headers=headers, timeout=45)
    response.raise_for_status()
    links = response.json().get("links") or []
    allowed = {row["campaign_id"] for row in candidates}
    active_jobs = (db._get().table("jobs").select("payload")
                   .eq("organization_id", config.organization_id)
                   .eq("type", "mercadolivre.link.ready")
                   .in_("status", ["pending", "running"])
                   .execute().data or [])
    already_requested = {
        str((row.get("payload") or {}).get("campaign_id"))
        for row in active_jobs
    }
    jobs: list[dict[str, Any]] = []
    for result in links:
        campaign_id = str(result.get("campaign_id") or "")
        if (campaign_id not in allowed or campaign_id in already_requested or
                not result.get("official_tool_confirmed")):
            continue
        affiliate_url = validar_link_afiliado_ml(str(result.get("affiliate_url") or ""))
        jobs.append({
            "organization_id": config.organization_id,
            "type": "mercadolivre.link.ready",
            "payload": {
                "agent": "hermes",
                "queue_id": config.queue_id,
                "campaign_id": campaign_id,
                "auto_approve": True,
                "affiliate_url": affiliate_url,
                "official_tool_confirmed": True,
            },
        })
    if jobs:
        db._get().table("jobs").insert(jobs).execute()
    return len(jobs)


def replenish_once(config: ReplenisherConfig,
                   *, now: Optional[datetime] = None) -> dict[str, Any]:
    """Executa um ciclo idempotente e limitado de reabastecimento."""
    config.validate()
    config = _config_with_saved_mix(config)
    config = _config_with_saved_min_score(config)
    moment = now or datetime.now(timezone.utc)
    active_items = _active_items(config.queue_id)
    before = len(active_items)
    if before > config.min_items and not config.enforce_source_mix:
        return {"triggered": False, "before": before, "after": before,
                "reason": "reserve_ok"}

    retired: list[str] = []
    if config.enforce_source_mix and before > config.min_items:
        retired = _retire_excess_pending(
            config, active_items, now=moment,
            max_items=min(
                config.max_new_per_cycle, before - config.min_items))
        if retired:
            active_items = _active_items(config.queue_id)
            before = len(active_items)
    if before >= config.target_items:
        randomized = randomize_pending_schedule(config, now=moment)
        return {"triggered": False, "before": before, "after": before,
                "reason": "target_reached_mix_reordered",
                "randomized": randomized["randomized"]}

    gap = max(0, config.target_items - before)
    budget = min(gap, config.max_new_per_cycle)
    if budget == 0:
        return {"triggered": False, "before": before, "after": before,
                "reason": "target_reached"}

    active_counts = _source_counts(active_items)
    inventory = _ready_inventory(
        config, budget, active_counts=active_counts)
    queued = _enqueue_campaigns(
        config, [x["campaign_id"] for x in inventory], now=moment)
    queued_set = set(queued)
    for item in inventory:
        if item["campaign_id"] in queued_set:
            source = str(item.get("source_name") or "")
            if source in active_counts:
                active_counts[source] += 1
    remaining = budget - len(queued)

    captured: list[str] = []
    if remaining > 0:
        terms = list(config.terms)
        random.SystemRandom().shuffle(terms)
        quotas = {"shopee": 0, "aliexpress": 0, "magalu": 0}
        simulated_counts = dict(active_counts)
        targets = config.source_target_percentages()
        for _ in range(remaining):
            projected_total = sum(simulated_counts.values()) + 1
            source = max(
                quotas,
                key=lambda name: (
                    targets[name] * projected_total / 100
                    - simulated_counts.get(name, 0)
                ),
            )
            quotas[source] += 1
            simulated_counts[source] = simulated_counts.get(source, 0) + 1

        captured_candidates: list[dict[str, str]] = []
        for source in ("shopee", "aliexpress", "magalu"):
            quota = quotas[source]
            if quota <= 0:
                continue
            result = ciclo_automatico(
                config.organization_id, termos=terms,
                min_score=config.min_score, max_novos=quota,
                queue_id=None, source_name=source,
                min_discount_pct=10 if source == "shopee" else None)
            captured_candidates.extend({
                "campaign_id": str(item["campaign_id"]),
                "source_name": source,
            } for item in result.get("campanhas", []))
        captured = _enqueue_campaigns(
            config,
            [item["campaign_id"] for item in captured_candidates],
            now=moment,
        )
        captured_set = set(captured)
        for item in captured_candidates:
            if item["campaign_id"] in captured_set:
                active_counts[item["source_name"]] += 1

    ml_target = math.ceil(
        config.target_items * config.ml_target_percent / 100)
    ml_needed = min(
        config.max_new_per_cycle,
        max(0, ml_target - active_counts.get("mercadolivre", 0)))
    hermes_jobs = 0
    if ml_needed:
        try:
            hermes_jobs = _request_hermes_links(
                config, _ml_candidates(config, ml_needed))
        except Exception as exc:
            # Falha do bridge não desfaz o que já foi abastecido pela API.
            db.register_audit(
                config.organization_id, actor_type="worker",
                action="hermes_linkbuilder_bridge_falhou",
                entity_type="queue", entity_id=config.queue_id,
                metadata={"error": str(exc)[:300]})
    randomized = randomize_pending_schedule(config, now=moment)
    after = len(_active_items(config.queue_id))
    db.register_audit(
        config.organization_id, actor_type="worker",
        action="reabastecedor_executado", entity_type="queue",
        entity_id=config.queue_id,
        metadata={"before": before, "after": after,
                  "inventory_queued": len(queued),
                  "captured_queued": len(captured),
                  "hermes_jobs": hermes_jobs,
                  "randomized": randomized["randomized"],
                  "source_targets": config.source_target_percentages(),
                  "source_counts_before": _source_counts(active_items),
                  "queue_links_retired_for_mix": len(retired),
                  "target": config.target_items})
    return {"triggered": True, "before": before, "after": after,
            "inventory_queued": len(queued), "captured_queued": len(captured),
            "hermes_jobs": hermes_jobs,
            "queue_links_retired_for_mix": len(retired),
            "randomized": randomized["randomized"]}
