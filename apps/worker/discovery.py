"""Descoberta supervisionada de ofertas por APIs oficiais.

Mercado Livre: captura anúncios MLB pela API do Programa de Desenvolvedores.
O Portal de Afiliados não possui endpoint público documentado para gerar links;
por isso as oportunidades ficam privadas e aguardam um link criado pelas
ferramentas oficiais da conta antes de aprovação/publicação.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import db
from connectors.mercadolivre import MercadoLivreConnector
from editorial_profile import editorial_affinity, sort_by_editorial_affinity
from offer_rules import (category_family, category_lock_reason, deal_highlight,
                         is_blocked_by_word, titles_similar)


def _product_row(organization_id: str, oferta: dict[str, Any]) -> dict[str, Any]:
    row = {
        "organization_id": organization_id,
        "status": "READY",
        "source_name": "mercadolivre",
        "source_url": oferta["canonical_url"],
        "external_id": oferta["external_product_id"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "method": "API",
        "title": oferta["title"],
        "image_url": oferta.get("main_image_url"),
        "original_price_brl": oferta.get("original_price"),
        "discounted_price_brl": oferta.get("current_price"),
        "currency": oferta.get("currency") or "BRL",
        "discount_pct": oferta.get("discount_percent"),
        "affiliate_link": None,
        "affiliate_link_status": "UNKNOWN",
        "seller": oferta.get("seller_name"),
        "category": oferta.get("category"),
        "sales_count": oferta.get("sold_count"),
        "confidence": oferta.get("source_confidence") or "UNKNOWN",
    }
    destaque = oferta.get("deal_highlight")
    if destaque:
        row["card_config"] = {"deal_highlight": destaque}
    return row


def _recent_similar_prices(organization_id: str, title: str,
                           *, days: int = 30) -> list[float]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        rows = (db._get().table("products")
                .select("title,discounted_price_brl")
                .eq("organization_id", organization_id)
                .eq("source_name", "mercadolivre")
                .gte("collected_at", since).execute().data or [])
    except (RuntimeError, AttributeError):
        return []
    return [float(row["discounted_price_brl"]) for row in rows
            if row.get("discounted_price_brl") is not None
            and titles_similar(title, row.get("title"))]


def capturar_ofertas_mercadolivre(
    organization_id: str,
    *,
    termos: list[str],
    min_discount_pct: float = 5.0,
    max_novos: int = 10,
    max_por_termo: int = 10,
    trend_limit: int = 0,
    highlight_categories: list[str] | None = None,
    highlight_limit: int = 0,
    max_price_checks: int = 20,
) -> dict[str, Any]:
    """Captura oportunidades MLB sem publicar nem gerar link artificial.

    Cria produto + campanha privada em READY. A campanha não recebe conteúdo,
    aprovação ou item de fila enquanto o link afiliado oficial não existir.
    Respeita a curadoria manual do Laboratório de Captura (/campanhas):
    palavras bloqueadas e categorias pausadas/travadas por tempo
    determinado — mesmas regras aplicadas ao ciclo automático de
    AliExpress/Shopee (`pipeline.ciclo_automatico`).
    """
    capture_config = db.get_capture_lab_config(organization_id)
    token = db.get_ml_access_token(organization_id)
    conector = MercadoLivreConnector(access_token=token)
    criados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    price_checks = 0
    candidatos = 0
    termos_tendencia = conector.get_trending_terms(
        category_ids=highlight_categories,
        limit=max(0, trend_limit),
    ) if trend_limit > 0 else []

    termos_efetivos: list[tuple[str, str]] = []
    termos_vistos: set[str] = set()
    for termo, fonte in [
        *((t, "search") for t in termos),
        *((t, "trends") for t in termos_tendencia),
    ]:
        termo = termo.strip()
        chave = termo.casefold()
        if termo and chave not in termos_vistos:
            termos_vistos.add(chave)
            termos_efetivos.append((termo, fonte))

    categorias = highlight_categories or []

    def iter_lotes():
        if categorias and highlight_limit > 0:
            yield ("highlights", conector.search_highlights(
                categorias, limit=highlight_limit))
        for termo, fonte in termos_efetivos:
            ofertas = conector.search_offers(termo)[:max_por_termo]
            for oferta in ofertas:
                oferta.setdefault("discovery_source", fonte)
                oferta["discovery_query"] = termo
            yield (termo, sort_by_editorial_affinity(ofertas))

    for origem, ofertas in iter_lotes():
        for oferta in ofertas:
            if len(criados) >= max_novos:
                break
            external_id = oferta.get("external_product_id")
            if not external_id or external_id in vistos:
                continue
            vistos.add(external_id)
            candidatos += 1
            if price_checks < max(0, max_price_checks):
                oferta = conector.enrich_offer_price(oferta)
                price_checks += 1
            desconto = oferta.get("discount_percent")
            if (desconto is None or
                    float(desconto) < min_discount_pct or not oferta.get("title") or
                    not oferta.get("canonical_url")):
                continue

            titulo = str(oferta.get("title") or "")
            categoria = oferta.get("category")
            termo_bloqueado = is_blocked_by_word(
                titulo, categoria, capture_config["blocklist"])
            if termo_bloqueado:
                db.register_audit(
                    organization_id, actor_type="worker",
                    action="mercadolivre_bloqueado_por_palavra",
                    entity_type="product", entity_id=str(external_id),
                    metadata={"title": titulo, "termo": termo_bloqueado})
                continue

            familia = category_family(categoria, titulo)
            motivo_categoria = category_lock_reason(
                capture_config["categories"].get(familia) if familia else None)
            if motivo_categoria:
                db.register_audit(
                    organization_id, actor_type="worker",
                    action="mercadolivre_categoria_bloqueada",
                    entity_type="product", entity_id=str(external_id),
                    metadata={"title": titulo, "category": categoria,
                              "family": familia, "motivo": motivo_categoria})
                continue

            destaque = deal_highlight(
                current_price=oferta.get("current_price"),
                original_price=oferta.get("original_price"),
                historical_prices=_recent_similar_prices(
                    organization_id, str(oferta.get("title") or "")),
            )
            if destaque:
                oferta["deal_highlight"] = destaque

            existente = (db._get().table("products").select("id")
                         .eq("organization_id", organization_id)
                         .eq("source_name", "mercadolivre")
                         .eq("external_id", external_id).limit(1)
                         .execute().data)
            if existente:
                continue

            produto = _product_row(organization_id, oferta)
            afinidade_editorial = editorial_affinity(
                oferta.get("title"), oferta.get("category"))
            if afinidade_editorial["priority"]:
                produto["card_config"] = {
                    **(produto.get("card_config") or {}),
                    "editorial_profile": afinidade_editorial,
                }
            produto_resp = db._get().table("products").insert(produto).execute()
            product_id = produto_resp.data[0]["id"]
            campaign_id = str(uuid.uuid4())
            db._get().table("campaigns").insert({
                "id": campaign_id,
                "organization_id": organization_id,
                "product_id": product_id,
                "status": "READY",
                "platform": "telegram",
                "mode": "simulated",
                "title": produto["title"],
                "slug": f"ml-{str(external_id).lower()}-{campaign_id[:8]}",
                "public_page": False,
            }).execute()
            db.register_audit(
                organization_id,
                actor_type="worker",
                action="mercadolivre_oferta_descoberta",
                entity_type="campaign",
                entity_id=campaign_id,
                metadata={
                    "title": titulo,
                    "category": categoria,
                    "external_id": external_id,
                    "discount_pct": desconto,
                    "affiliate_link": "PENDING_OFFICIAL_TOOL",
                    "query": oferta.get("discovery_query") or origem,
                    "discovery_source": oferta.get("discovery_source") or origem,
                    "price_source": oferta.get("price_source") or "search_fallback",
                    "current_price": oferta.get("current_price"),
                    "deal_highlight": destaque,
                    "highlight_rank": oferta.get("highlight_rank"),
                },
            )
            criados.append({
                "campaign_id": campaign_id,
                "product_id": product_id,
                "external_id": external_id,
                "title": produto["title"],
                "discount_pct": desconto,
            })
        if len(criados) >= max_novos:
            break

    return {
        "total": len(criados),
        "campanhas": criados,
        "affiliate_links": "PENDING_OFFICIAL_TOOL",
        "candidates_checked": candidatos,
        "price_checks": price_checks,
        "trending_terms": termos_tendencia,
    }
