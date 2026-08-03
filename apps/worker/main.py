"""Topfy Affiliate OS — worker: consome a fila de jobs do Postgres.

Rodar: python -m main (com .env carregado — usar python-dotenv ou
variáveis de ambiente do processo).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

import db
from coupon_discovery import capture_shopee_coupons
from discovery import capturar_ofertas_mercadolivre
from pipeline import (import_product, generate_affiliate_link, compute_score,
                      generate_copies, montar_copy_text, publish_to_telegram,
                      enviar_mensagem_grupo, regenerate_copies, dispatch_queues,
                      ciclo_automatico, normalizar_product_row,
                      completar_link_mercadolivre_assistido)
from replenisher import ReplenisherConfig, force_redistribute_by_category, replenish_once

POLL_INTERVAL_SECONDS = 5
WORKER_HEARTBEAT_INTERVAL_SECONDS = 300

# Modo 100% automático (capturar -> aprovar -> publicar sem revisão
# humana) — OPT-IN, desligado por padrão. Só roda se as 3 env vars
# abaixo estiverem configuradas; sem elas, comportamento do worker é
# idêntico ao de sempre (nada muda pra quem não ligou isso).
AUTO_PIPELINE_ENABLED = os.environ.get("AUTO_PIPELINE_ENABLED", "").lower() in ("1", "true", "yes")
AUTO_PIPELINE_ORG_ID = os.environ.get("AUTO_PIPELINE_ORG_ID", "")
AUTO_PIPELINE_TERMOS = [t.strip() for t in
                       os.environ.get("AUTO_PIPELINE_TERMOS", "").split(",") if t.strip()]
AUTO_PIPELINE_QUEUE_ID = os.environ.get("AUTO_PIPELINE_QUEUE_ID", "") or None
AUTO_PIPELINE_MIN_SCORE = float(os.environ.get("AUTO_PIPELINE_MIN_SCORE", "60"))
AUTO_PIPELINE_MAX_NOVOS = int(os.environ.get("AUTO_PIPELINE_MAX_NOVOS", "5"))
AUTO_PIPELINE_INTERVAL_MINUTES = int(os.environ.get("AUTO_PIPELINE_INTERVAL_MINUTES", "30"))

# Shopee usa um ciclo próprio para permitir canário e rollback sem alterar o
# motor AliExpress que já está em produção. Só entra na fila quando habilitado.
SHOPEE_DISCOVERY_ENABLED = os.environ.get(
    "SHOPEE_DISCOVERY_ENABLED", "").lower() in ("1", "true", "yes")
SHOPEE_DISCOVERY_ORG_ID = os.environ.get(
    "SHOPEE_DISCOVERY_ORG_ID", "") or AUTO_PIPELINE_ORG_ID
SHOPEE_DISCOVERY_TERMOS = [
    value.strip() for value in os.environ.get(
        "SHOPEE_DISCOVERY_TERMOS", "").split(",") if value.strip()
]
SHOPEE_DISCOVERY_MIN_SCORE = float(os.environ.get(
    "SHOPEE_DISCOVERY_MIN_SCORE", os.environ.get("AUTO_PIPELINE_MIN_SCORE", "60")))
SHOPEE_DISCOVERY_MIN_DISCOUNT = float(os.environ.get(
    "SHOPEE_DISCOVERY_MIN_DISCOUNT", "10"))
SHOPEE_DISCOVERY_MAX_NOVOS = int(os.environ.get(
    "SHOPEE_DISCOVERY_MAX_NOVOS", "10"))
SHOPEE_DISCOVERY_INTERVAL_MINUTES = int(os.environ.get(
    "SHOPEE_DISCOVERY_INTERVAL_MINUTES", "5"))
SHOPEE_DISCOVERY_TERMS_PER_CYCLE = int(os.environ.get(
    "SHOPEE_DISCOVERY_TERMS_PER_CYCLE", "3"))
SHOPEE_DISCOVERY_QUEUE_ID = os.environ.get(
    "SHOPEE_DISCOVERY_QUEUE_ID", "") or AUTO_PIPELINE_QUEUE_ID

# Campanhas/cupons oficiais da Shopee Affiliate API. O offerLink retornado
# pertence a esta conta; nunca reaproveita links observados em outros canais.
SHOPEE_COUPON_DISCOVERY_ENABLED = os.environ.get(
    "SHOPEE_COUPON_DISCOVERY_ENABLED", "").lower() in ("1", "true", "yes")
SHOPEE_COUPON_DISCOVERY_ORG_ID = os.environ.get(
    "SHOPEE_COUPON_DISCOVERY_ORG_ID", "") or SHOPEE_DISCOVERY_ORG_ID
SHOPEE_COUPON_DISCOVERY_INTERVAL_MINUTES = int(os.environ.get(
    "SHOPEE_COUPON_DISCOVERY_INTERVAL_MINUTES", "15"))
SHOPEE_COUPON_DISCOVERY_MAX_NEW = int(os.environ.get(
    "SHOPEE_COUPON_DISCOVERY_MAX_NEW", "3"))

# Agente de reserva: mantém horas de ofertas prontas sem bloquear o loop que
# publica no Telegram. É independente do AUTO_PIPELINE legado.
REPLENISHER_ENABLED = os.environ.get(
    "REPLENISHER_ENABLED", "").lower() in ("1", "true", "yes")
REPLENISHER_ORG_ID = os.environ.get(
    "REPLENISHER_ORG_ID", "") or AUTO_PIPELINE_ORG_ID
REPLENISHER_QUEUE_ID = os.environ.get(
    "REPLENISHER_QUEUE_ID", "") or AUTO_PIPELINE_QUEUE_ID
REPLENISHER_TERMS = tuple(
    value.strip() for value in os.environ.get(
        "REPLENISHER_TERMS", os.environ.get("AUTO_PIPELINE_TERMOS", "")
    ).split(",") if value.strip())
REPLENISHER_MIN_ITEMS = int(os.environ.get("REPLENISHER_MIN_ITEMS", "84"))
REPLENISHER_TARGET_ITEMS = int(os.environ.get("REPLENISHER_TARGET_ITEMS", "96"))
REPLENISHER_MAX_NEW_PER_CYCLE = int(os.environ.get(
    "REPLENISHER_MAX_NEW_PER_CYCLE", "4"))
REPLENISHER_MIN_SCORE = float(os.environ.get("REPLENISHER_MIN_SCORE", "35"))
REPLENISHER_INTERVAL_MINUTES = int(os.environ.get(
    "REPLENISHER_INTERVAL_MINUTES", "5"))
REPLENISHER_ML_TARGET_PERCENT = int(os.environ.get(
    "REPLENISHER_ML_TARGET_PERCENT", "30"))
REPLENISHER_SHOPEE_TARGET_PERCENT = int(os.environ.get(
    "REPLENISHER_SHOPEE_TARGET_PERCENT", "40"))
REPLENISHER_ALIEXPRESS_TARGET_PERCENT = int(os.environ.get(
    "REPLENISHER_ALIEXPRESS_TARGET_PERCENT", "10"))
REPLENISHER_MAGALU_TARGET_PERCENT = int(os.environ.get(
    "REPLENISHER_MAGALU_TARGET_PERCENT", "20"))
HERMES_LINK_AGENT_URL = os.environ.get("HERMES_LINK_AGENT_URL", "") or None
HERMES_LINK_AGENT_TOKEN = os.environ.get("HERMES_LINK_AGENT_TOKEN", "") or None

_ultimo_ciclo_automatico: Optional[datetime] = None
_ultimo_ciclo_shopee: Optional[datetime] = None
_ultimo_ciclo_cupons_shopee: Optional[datetime] = None
_indice_termo_shopee = 0
_ultimo_ciclo_reabastecedor: Optional[datetime] = None
_reabastecedor_thread: Optional[threading.Thread] = None


def _executar_reabastecedor(config: ReplenisherConfig) -> None:
    try:
        resultado = replenish_once(config)
        if resultado.get("triggered"):
            print(
                "[worker] reabastecedor: "
                f"{resultado['before']} -> {resultado['after']} item(ns); "
                f"inventario={resultado['inventory_queued']}, "
                f"novos={resultado['captured_queued']}, "
                f"hermes={resultado['hermes_jobs']}")
    except Exception as exc:
        # Agente auxiliar nunca derruba nem pausa o publicador.
        print(f"[worker] erro no reabastecedor: {exc}", file=sys.stderr)


def rodar_reabastecedor_se_configurado(*,
                                       now: Optional[datetime] = None) -> None:
    """Dispara no máximo um ciclo em background a cada intervalo."""
    global _ultimo_ciclo_reabastecedor, _reabastecedor_thread
    if not (REPLENISHER_ENABLED and REPLENISHER_ORG_ID and
            REPLENISHER_QUEUE_ID and REPLENISHER_TERMS):
        return
    if _reabastecedor_thread is not None and _reabastecedor_thread.is_alive():
        return
    agora = now or datetime.now(timezone.utc)
    if (_ultimo_ciclo_reabastecedor is not None and
            (agora - _ultimo_ciclo_reabastecedor).total_seconds() <
            REPLENISHER_INTERVAL_MINUTES * 60):
        return
    termos_reabastecedor = list(REPLENISHER_TERMS)
    for fonte in ("aliexpress", "shopee", "magalu"):
        termos_reabastecedor = _termos_com_banco(
            REPLENISHER_ORG_ID, fonte, termos_reabastecedor)
    config = ReplenisherConfig(
        organization_id=REPLENISHER_ORG_ID,
        queue_id=REPLENISHER_QUEUE_ID,
        terms=tuple(termos_reabastecedor),
        min_items=REPLENISHER_MIN_ITEMS,
        target_items=REPLENISHER_TARGET_ITEMS,
        max_new_per_cycle=REPLENISHER_MAX_NEW_PER_CYCLE,
        min_score=REPLENISHER_MIN_SCORE,
        interval_minutes=5,
        ml_target_percent=REPLENISHER_ML_TARGET_PERCENT,
        shopee_target_percent=REPLENISHER_SHOPEE_TARGET_PERCENT,
        aliexpress_target_percent=REPLENISHER_ALIEXPRESS_TARGET_PERCENT,
        magalu_target_percent=REPLENISHER_MAGALU_TARGET_PERCENT,
        enforce_source_mix=True,
        hermes_url=HERMES_LINK_AGENT_URL,
        hermes_token=HERMES_LINK_AGENT_TOKEN,
    )
    config.validate()
    _ultimo_ciclo_reabastecedor = agora
    _reabastecedor_thread = threading.Thread(
        target=_executar_reabastecedor, args=(config,),
        name="topfy-replenisher", daemon=True)
    _reabastecedor_thread.start()

# Descoberta Mercado Livre via API oficial: captura oportunidades, mas nunca
# publica sem o link gerado pelas ferramentas oficiais do programa afiliado.
ML_DISCOVERY_ENABLED = os.environ.get("ML_DISCOVERY_ENABLED", "").lower() in ("1", "true", "yes")
ML_DISCOVERY_ORG_ID = os.environ.get("ML_DISCOVERY_ORG_ID", "") or AUTO_PIPELINE_ORG_ID
ML_DISCOVERY_TERMOS = [t.strip() for t in
                      os.environ.get("ML_DISCOVERY_TERMOS", "").split(",") if t.strip()]
ML_DISCOVERY_MIN_DISCOUNT = float(os.environ.get("ML_DISCOVERY_MIN_DISCOUNT", "5"))
ML_DISCOVERY_MAX_NOVOS = int(os.environ.get("ML_DISCOVERY_MAX_NOVOS", "10"))
ML_DISCOVERY_INTERVAL_MINUTES = int(os.environ.get("ML_DISCOVERY_INTERVAL_MINUTES", "60"))
ML_DISCOVERY_TERMS_PER_CYCLE = int(os.environ.get(
    "ML_DISCOVERY_TERMS_PER_CYCLE", "2"))
ML_DISCOVERY_TRENDS_ENABLED = os.environ.get(
    "ML_DISCOVERY_TRENDS_ENABLED", "").lower() in ("1", "true", "yes")
ML_DISCOVERY_TREND_LIMIT = int(os.environ.get("ML_DISCOVERY_TREND_LIMIT", "3"))
ML_DISCOVERY_TREND_REFRESH_MINUTES = int(os.environ.get(
    "ML_DISCOVERY_TREND_REFRESH_MINUTES", "360"))
ML_DISCOVERY_HIGHLIGHT_CATEGORIES = [
    value.strip().upper() for value in
    os.environ.get("ML_DISCOVERY_HIGHLIGHT_CATEGORIES", "").split(",")
    if value.strip()
]
ML_DISCOVERY_HIGHLIGHT_LIMIT = int(os.environ.get(
    "ML_DISCOVERY_HIGHLIGHT_LIMIT", "5"))
ML_DISCOVERY_HIGHLIGHT_CATEGORIES_PER_CYCLE = int(os.environ.get(
    "ML_DISCOVERY_HIGHLIGHT_CATEGORIES_PER_CYCLE", "8"))
ML_DISCOVERY_HIGHLIGHT_REFRESH_MINUTES = int(os.environ.get(
    "ML_DISCOVERY_HIGHLIGHT_REFRESH_MINUTES", "60"))
ML_DISCOVERY_MAX_PRICE_CHECKS = int(os.environ.get(
    "ML_DISCOVERY_MAX_PRICE_CHECKS", "20"))

_ultima_descoberta_ml: Optional[datetime] = None
_ultima_tendencia_ml: Optional[datetime] = None
_ultimo_highlight_ml: Optional[datetime] = None
_indice_termo_ml = 0
_indice_categoria_ml = 0
_ultimo_heartbeat: Optional[datetime] = None


def registrar_heartbeat_se_necessario(*, now: Optional[datetime] = None) -> None:
    """Publica telemetria real para o dashboard administrativo a cada 5 min."""
    global _ultimo_heartbeat
    agora = now or datetime.now(timezone.utc)
    organization_id = REPLENISHER_ORG_ID or ML_DISCOVERY_ORG_ID or AUTO_PIPELINE_ORG_ID
    if not organization_id:
        return
    if (_ultimo_heartbeat is not None and
            (agora - _ultimo_heartbeat).total_seconds() <
            WORKER_HEARTBEAT_INTERVAL_SECONDS):
        return
    metadata = {
        "pid": os.getpid(),
        "poll_seconds": POLL_INTERVAL_SECONDS,
        "captured_at": agora.isoformat(),
        "replenisher_enabled": REPLENISHER_ENABLED,
        "search_terms": list(REPLENISHER_TERMS),
        "search_terms_count": len(REPLENISHER_TERMS),
        "queue_min_items": REPLENISHER_MIN_ITEMS,
        "queue_target_items": REPLENISHER_TARGET_ITEMS,
        "queue_interval_minutes": REPLENISHER_INTERVAL_MINUTES,
        "min_score": REPLENISHER_MIN_SCORE,
        "aliexpress_api_configured": bool(
            os.environ.get("ALIEXPRESS_APP_KEY")
            and os.environ.get("ALIEXPRESS_APP_SECRET")
        ),
        "aliexpress_tracking_configured": bool(
            os.environ.get("ALIEXPRESS_TRACKING_ID")
        ),
        "aliexpress_terms_shuffled": True,
        "shopee_api_configured": bool(
            (os.environ.get("SHOPEE_AFFILIATE_APP_ID") or
             os.environ.get("SHOPPE_APP_KEY"))
            and (os.environ.get("SHOPEE_AFFILIATE_SECRET") or
                 os.environ.get("SHOPPE_APP_SECRET"))
        ),
        "shopee_discovery_enabled": SHOPEE_DISCOVERY_ENABLED,
        "shopee_coupon_discovery_enabled": SHOPEE_COUPON_DISCOVERY_ENABLED,
        "magalu_storefront_configured": bool(os.environ.get("MAGALU_STORE_SLUG")),
        "magalu_store_slug": os.environ.get("MAGALU_STORE_SLUG", ""),
        "magalu_coupons_url": os.environ.get("MAGALU_COUPONS_URL", ""),
        "shopee_search_terms": list(SHOPEE_DISCOVERY_TERMOS),
        "shopee_terms_per_cycle": SHOPEE_DISCOVERY_TERMS_PER_CYCLE,
        "shopee_cycle_minutes": SHOPEE_DISCOVERY_INTERVAL_MINUTES,
        "ml_discovery_enabled": ML_DISCOVERY_ENABLED,
        "ml_search_terms": list(ML_DISCOVERY_TERMOS),
        "ml_search_terms_count": len(ML_DISCOVERY_TERMOS),
        "ml_terms_per_cycle": ML_DISCOVERY_TERMS_PER_CYCLE,
        "ml_cycle_minutes": ML_DISCOVERY_INTERVAL_MINUTES,
        "ml_categories": list(ML_DISCOVERY_HIGHLIGHT_CATEGORIES),
        "ml_categories_count": len(ML_DISCOVERY_HIGHLIGHT_CATEGORIES),
        "ml_categories_per_cycle": ML_DISCOVERY_HIGHLIGHT_CATEGORIES_PER_CYCLE,
        "ml_target_percent": REPLENISHER_ML_TARGET_PERCENT,
        "shopee_target_percent": REPLENISHER_SHOPEE_TARGET_PERCENT,
        "aliexpress_target_percent": REPLENISHER_ALIEXPRESS_TARGET_PERCENT,
        "magalu_target_percent": REPLENISHER_MAGALU_TARGET_PERCENT,
        "real_discount_required": True,
        "deduplication_enabled": True,
        "category_diversity_enabled": True,
        "verified_coupons_only": True,
        "coupon_capture_target_percent": 10,
    }
    db.register_audit(
        organization_id, actor_type="worker", action="worker_heartbeat",
        entity_type="worker", entity_id=str(os.getpid()), metadata=metadata)
    _ultimo_heartbeat = agora


def _termos_com_banco(organization_id: str, source_name: str,
                      termos_env: list[str]) -> list[str]:
    """Termos configurados via env var + os cadastrados pela tela em
    /campanhas (Laboratório de Captura) pra essa fonte — só soma, nunca
    substitui, então quem não usou a tela continua exatamente igual."""
    vistos = {termo.casefold() for termo in termos_env}
    extras = [termo for termo in db.get_discovery_keywords(organization_id, source_name)
             if termo.casefold() not in vistos]
    return [*termos_env, *extras]


def rodar_ciclo_automatico_se_configurado(*, now: Optional[datetime] = None) -> None:
    """Roda o modo 100% automático no próprio ritmo (AUTO_PIPELINE_
    INTERVAL_MINUTES, não a cada poll de 5s) — chamado a cada volta do
    run_forever. Sem AUTO_PIPELINE_ENABLED/ORG_ID/TERMOS configurados,
    não faz nada (opt-in real, sem default)."""
    global _ultimo_ciclo_automatico
    if not (AUTO_PIPELINE_ENABLED and AUTO_PIPELINE_ORG_ID and AUTO_PIPELINE_TERMOS):
        return
    agora = now or datetime.now(timezone.utc)
    if (_ultimo_ciclo_automatico is not None and
            (agora - _ultimo_ciclo_automatico).total_seconds() <
            AUTO_PIPELINE_INTERVAL_MINUTES * 60):
        return
    _ultimo_ciclo_automatico = agora
    termos = _termos_com_banco(
        AUTO_PIPELINE_ORG_ID, "aliexpress", AUTO_PIPELINE_TERMOS)
    try:
        resultado = ciclo_automatico(
            AUTO_PIPELINE_ORG_ID, termos=termos,
            min_score=AUTO_PIPELINE_MIN_SCORE,
            max_novos=AUTO_PIPELINE_MAX_NOVOS,
            queue_id=AUTO_PIPELINE_QUEUE_ID)
        if resultado["total"]:
            print(f"[worker] modo automatico: {resultado['total']} "
                  f"campanha(s) capturada(s) e aprovada(s) sozinha(s)")
    except Exception as exc:  # nunca derruba o loop principal
        print(f"[worker] erro no ciclo automatico: {exc}", file=sys.stderr)


def rodar_descoberta_shopee_se_configurada(*,
                                           now: Optional[datetime] = None) -> None:
    """Captura, pontua e enfileira Shopee somente quando o opt-in está ativo."""
    global _ultimo_ciclo_shopee, _indice_termo_shopee
    if not (SHOPEE_DISCOVERY_ENABLED and SHOPEE_DISCOVERY_ORG_ID and
            SHOPEE_DISCOVERY_TERMOS and SHOPEE_DISCOVERY_QUEUE_ID):
        return
    agora = now or datetime.now(timezone.utc)
    if (_ultimo_ciclo_shopee is not None and
            (agora - _ultimo_ciclo_shopee).total_seconds() <
            SHOPEE_DISCOVERY_INTERVAL_MINUTES * 60):
        return
    termos_disponiveis = _termos_com_banco(
        SHOPEE_DISCOVERY_ORG_ID, "shopee", SHOPEE_DISCOVERY_TERMOS)
    quantidade = min(max(1, SHOPEE_DISCOVERY_TERMS_PER_CYCLE),
                     len(termos_disponiveis))
    termos = [
        termos_disponiveis[
            (_indice_termo_shopee + deslocamento) % len(termos_disponiveis)]
        for deslocamento in range(quantidade)
    ]
    _indice_termo_shopee = (
        _indice_termo_shopee + quantidade) % len(termos_disponiveis)
    _ultimo_ciclo_shopee = agora
    try:
        resultado = ciclo_automatico(
            SHOPEE_DISCOVERY_ORG_ID,
            termos=termos,
            min_score=SHOPEE_DISCOVERY_MIN_SCORE,
            max_novos=SHOPEE_DISCOVERY_MAX_NOVOS,
            queue_id=SHOPEE_DISCOVERY_QUEUE_ID,
            source_name="shopee",
            min_discount_pct=SHOPEE_DISCOVERY_MIN_DISCOUNT,
        )
        print(
            f"[worker] Shopee: ciclo ok; {resultado['total']} "
            "campanha(s) verificada(s) adicionada(s) à fila"
        )
    except Exception as exc:
        print(f"[worker] erro na descoberta Shopee: {exc}", file=sys.stderr)


def rodar_cupons_shopee_se_configurado(*,
                                       now: Optional[datetime] = None) -> None:
    """Descobre campanhas oficiais e prepara copy sem copiar outro canal."""
    global _ultimo_ciclo_cupons_shopee
    if not (SHOPEE_COUPON_DISCOVERY_ENABLED and
            SHOPEE_COUPON_DISCOVERY_ORG_ID):
        return
    agora = now or datetime.now(timezone.utc)
    if (_ultimo_ciclo_cupons_shopee is not None and
            (agora - _ultimo_ciclo_cupons_shopee).total_seconds() <
            SHOPEE_COUPON_DISCOVERY_INTERVAL_MINUTES * 60):
        return
    _ultimo_ciclo_cupons_shopee = agora
    try:
        resultado = capture_shopee_coupons(
            SHOPEE_COUPON_DISCOVERY_ORG_ID,
            max_new=SHOPEE_COUPON_DISCOVERY_MAX_NEW,
            now=agora,
        )
        print(
            "[worker] cupons Shopee: "
            f"{resultado['found']} encontrado(s), "
            f"{resultado['created']} novo(s)"
        )
    except Exception as exc:
        print(f"[worker] erro nos cupons Shopee: {exc}", file=sys.stderr)


def rodar_descoberta_ml_se_configurada(*, now: Optional[datetime] = None) -> None:
    """Executa a descoberta MLB no intervalo configurado, sem publicação."""
    global _ultima_descoberta_ml, _ultima_tendencia_ml, _ultimo_highlight_ml
    global _indice_termo_ml, _indice_categoria_ml
    tem_fonte = (ML_DISCOVERY_TERMOS or ML_DISCOVERY_TRENDS_ENABLED or
                 ML_DISCOVERY_HIGHLIGHT_CATEGORIES)
    if not (ML_DISCOVERY_ENABLED and ML_DISCOVERY_ORG_ID and tem_fonte):
        return
    agora = now or datetime.now(timezone.utc)
    if (_ultima_descoberta_ml is not None and
            (agora - _ultima_descoberta_ml).total_seconds() <
            ML_DISCOVERY_INTERVAL_MINUTES * 60):
        return
    _ultima_descoberta_ml = agora
    consultar_tendencias = bool(
        ML_DISCOVERY_TRENDS_ENABLED and
        (_ultima_tendencia_ml is None or
         (agora - _ultima_tendencia_ml).total_seconds() >=
         ML_DISCOVERY_TREND_REFRESH_MINUTES * 60)
    )
    consultar_highlights = bool(
        ML_DISCOVERY_HIGHLIGHT_CATEGORIES and
        (_ultimo_highlight_ml is None or
         (agora - _ultimo_highlight_ml).total_seconds() >=
         ML_DISCOVERY_HIGHLIGHT_REFRESH_MINUTES * 60)
    )
    if consultar_tendencias:
        _ultima_tendencia_ml = agora
    if consultar_highlights:
        _ultimo_highlight_ml = agora
    if not (ML_DISCOVERY_TERMOS or consultar_tendencias or consultar_highlights):
        return
    termos_ciclo: list[str] = []
    termos_disponiveis = _termos_com_banco(
        ML_DISCOVERY_ORG_ID, "mercadolivre", ML_DISCOVERY_TERMOS)
    if termos_disponiveis:
        quantidade = min(
            max(1, ML_DISCOVERY_TERMS_PER_CYCLE), len(termos_disponiveis))
        termos_ciclo = [
            termos_disponiveis[(_indice_termo_ml + deslocamento) %
                               len(termos_disponiveis)]
            for deslocamento in range(quantidade)
        ]
        _indice_termo_ml = (_indice_termo_ml + quantidade) % len(
            termos_disponiveis)
    categorias_ciclo: list[str] = []
    if (ML_DISCOVERY_HIGHLIGHT_CATEGORIES and
            (consultar_tendencias or consultar_highlights)):
        quantidade_categorias = min(
            max(1, ML_DISCOVERY_HIGHLIGHT_CATEGORIES_PER_CYCLE),
            len(ML_DISCOVERY_HIGHLIGHT_CATEGORIES))
        categorias_ciclo = [
            ML_DISCOVERY_HIGHLIGHT_CATEGORIES[
                (_indice_categoria_ml + deslocamento) %
                len(ML_DISCOVERY_HIGHLIGHT_CATEGORIES)]
            for deslocamento in range(quantidade_categorias)
        ]
        _indice_categoria_ml = (
            _indice_categoria_ml + quantidade_categorias
        ) % len(ML_DISCOVERY_HIGHLIGHT_CATEGORIES)
    try:
        resultado = capturar_ofertas_mercadolivre(
            ML_DISCOVERY_ORG_ID,
            termos=termos_ciclo,
            min_discount_pct=ML_DISCOVERY_MIN_DISCOUNT,
            max_novos=ML_DISCOVERY_MAX_NOVOS,
            trend_limit=(ML_DISCOVERY_TREND_LIMIT
                         if consultar_tendencias else 0),
            highlight_categories=categorias_ciclo,
            highlight_limit=(ML_DISCOVERY_HIGHLIGHT_LIMIT
                             if consultar_highlights else 0),
            max_price_checks=ML_DISCOVERY_MAX_PRICE_CHECKS,
        )
        print(
            f"[worker] Mercado Livre: ciclo ok; "
            f"{resultado['total']} nova(s), "
            f"{resultado.get('candidates_checked', 0)} candidata(s), "
            f"{resultado.get('price_checks', 0)} preco(s) consultado(s); "
            "novas ofertas aguardam link oficial"
        )
    except Exception as exc:
        print(f"[worker] erro na descoberta Mercado Livre: {exc}",
              file=sys.stderr)


def process_job(job: dict[str, Any]) -> None:
    payload = job.get("payload") or {}
    tipo = job.get("type", "")
    org = job.get("organization_id")

    if tipo == "product.import":
        product_id = payload.get("product_id")
        campaign_id = payload.get("campaign_id")
        if not product_id or not campaign_id:
            raise ValueError(
                "job product.import sem product_id/campaign_id — precisa "
                "ser criado por createCampaignFromUrl (web)")

        row = import_product(payload["source_name"], payload["url"],
                             organization_id=org)
        db._get().table("products").update(row).eq("id", product_id).execute()
        db.register_audit(org, actor_type="worker", action="produto_importado",
                          entity_type="product", entity_id=str(product_id),
                          metadata={"source_name": payload["source_name"]})

        link = generate_affiliate_link(payload["source_name"], payload["url"])
        db._get().table("products").update({
            "affiliate_link": link.get("affiliate_url"),
            "affiliate_link_status": link.get("verification_status", "UNKNOWN"),
        }).eq("id", product_id).execute()

        product_row = normalizar_product_row(db.get_product(str(product_id)))
        score = compute_score(product_row, link)
        db._get().table("products").update({
            "score": score["score_total"],
            "score_breakdown": {
                k: v for k, v in score.items()
                if k not in ("score_total", "reason_summary", "warnings", "bloqueios")
            },
            "status": "READY",
        }).eq("id", product_id).execute()

        db._get().table("campaigns").update({
            "status": "READY",
            "title": product_row.get("title"),
        }).eq("id", campaign_id).execute()
        db.register_audit(org, actor_type="worker", action="campanha_atualizada",
                          entity_type="campaign", entity_id=str(campaign_id))

        copias = generate_copies(product_row)
        for copia in copias:
            validation_errors = copia.pop("validation_errors", None)
            db._get().table("contents").insert({
                "campaign_id": campaign_id,
                "version": 1,
                "status": "DRAFT" if validation_errors else "PENDING_REVIEW",
                "provider": copia.pop("provider", "fallback"),
                "model": copia.pop("model", None),
                "copy_text": montar_copy_text(copia),
                "hooks": [],
                "compliance": {"validation_errors": validation_errors or []},
            }).execute()
        db.update_campaign(campaign_id, {"status": "CONTENT_GENERATING"})
        db.register_audit(org, actor_type="worker", action="copies_geradas",
                          entity_type="campaign", entity_id=str(campaign_id),
                          metadata={"total": len(copias)})

    elif tipo == "publication.telegram":
        resultado = publish_to_telegram(
            payload["campaign_id"], payload["content_id"],
            payload.get("chat_id", ""), payload.get("group_id"))
        db.register_audit(org, actor_type="worker", action="publicacao_telegram",
                          entity_type="publication",
                          entity_id=str(resultado["publication_id"]),
                          metadata=resultado)

    elif tipo == "telegram.send":
        group_id = payload.get("group_id")
        text = payload.get("text", "")
        if not group_id or not text:
            raise ValueError(
                "job telegram.send precisa de group_id e text no payload")
        resultado = enviar_mensagem_grupo(group_id, text)
        db.register_audit(org, actor_type="user", action="telegram_mensagem_livre",
                          entity_type="channel_group", entity_id=str(group_id),
                          metadata=resultado)

    elif tipo == "content.regenerate":
        campaign_id = payload.get("campaign_id")
        if not campaign_id:
            raise ValueError("job content.regenerate sem campaign_id")
        resultado = regenerate_copies(campaign_id)
        db.register_audit(org, actor_type="user", action="copies_regeneradas",
                          entity_type="campaign", entity_id=str(campaign_id),
                          metadata=resultado)

    elif tipo == "mercadolivre.link.ready":
        campaign_id = payload.get("campaign_id")
        affiliate_url = payload.get("affiliate_url")
        if not campaign_id or not affiliate_url:
            raise ValueError(
                "job mercadolivre.link.ready precisa de campaign_id e affiliate_url")
        completar_link_mercadolivre_assistido(
            campaign_id,
            affiliate_url,
            official_tool_confirmed=bool(payload.get("official_tool_confirmed")),
            auto_approve=bool(payload.get("auto_approve")),
            queue_id=payload.get("queue_id") or None,
        )

    elif tipo == "discovery.redistribute_categories":
        queue_id = payload.get("queue_id")
        if not org or not queue_id:
            raise ValueError(
                "job discovery.redistribute_categories precisa de organization_id e queue_id")
        resultado = force_redistribute_by_category(org, queue_id)
        db.register_audit(org, actor_type="user",
                          action="categoria_redistribuicao_forcada_via_job",
                          entity_type="queue", entity_id=str(queue_id),
                          metadata=resultado)

    else:
        raise ValueError(f"tipo de job desconhecido: {tipo}")


def run_forever() -> None:
    while True:
        try:
            registrar_heartbeat_se_necessario()
        except Exception as exc:
            print(f"[worker] erro ao registrar heartbeat: {exc}", file=sys.stderr)
        try:
            despachados = dispatch_queues()
            if despachados:
                print(f"[worker] filas: {len(despachados)} item(ns) despachado(s)")
        except Exception as exc:  # filas: nunca derruba o loop
            print(f"[worker] erro ao despachar filas: {exc}", file=sys.stderr)
        rodar_descoberta_ml_se_configurada()
        rodar_ciclo_automatico_se_configurado()
        rodar_descoberta_shopee_se_configurada()
        rodar_cupons_shopee_se_configurado()
        rodar_reabastecedor_se_configurado()
        try:
            job = db.get_next_job()
        except Exception as exc:  # rede/credencial — continua tentando
            print(f"[worker] erro ao buscar job: {exc}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            process_job(job)
            db.finish_job(job["id"], ok=True)
            print(f"[worker] job {job['id']} ({job['type']}) concluído")
        except Exception as exc:
            db.finish_job(job["id"], ok=False, error=str(exc))
            print(f"[worker] job {job['id']} ({job['type']}) FALHOU: {exc}",
                  file=sys.stderr)


def run_once(max_jobs: int = 1) -> list[dict[str, Any]]:
    """Processa até max_jobs da fila e volta — útil para testes/cron."""
    processados = []
    for _ in range(max_jobs):
        job = db.get_next_job()
        if not job:
            break
        try:
            process_job(job)
            db.finish_job(job["id"], ok=True)
            processados.append({"id": job["id"], "type": job["type"], "ok": True})
        except Exception as exc:
            db.finish_job(job["id"], ok=False, error=str(exc))
            processados.append({"id": job["id"], "type": job["type"], "ok": False,
                                "error": str(exc)})
    return processados


if __name__ == "__main__":
    run_forever()
