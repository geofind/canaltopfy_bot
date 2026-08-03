"""Descoberta supervisionada de ofertas por APIs oficiais.

Mercado Livre: captura anúncios MLB pela API do Programa de Desenvolvedores.
O Portal de Afiliados não possui endpoint público documentado para gerar links;
por isso as oportunidades ficam privadas e aguardam um link criado pelas
ferramentas oficiais da conta antes de aprovação/publicação.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import db
from connectors.mercadolivre import MercadoLivreConnector


def _product_row(organization_id: str, oferta: dict[str, Any]) -> dict[str, Any]:
    return {
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


def capturar_ofertas_mercadolivre(
    organization_id: str,
    *,
    termos: list[str],
    min_discount_pct: float = 5.0,
    max_novos: int = 10,
    max_por_termo: int = 10,
) -> dict[str, Any]:
    """Captura oportunidades MLB sem publicar nem gerar link artificial.

    Cria produto + campanha privada em READY. A campanha não recebe conteúdo,
    aprovação ou item de fila enquanto o link afiliado oficial não existir.
    """
    token = db.get_ml_access_token(organization_id)
    conector = MercadoLivreConnector(access_token=token)
    criados: list[dict[str, Any]] = []
    vistos: set[str] = set()

    for termo in (t.strip() for t in termos if t.strip()):
        for oferta in conector.search_offers(termo)[:max_por_termo]:
            if len(criados) >= max_novos:
                break
            external_id = oferta.get("external_product_id")
            desconto = oferta.get("discount_percent")
            if (not external_id or external_id in vistos or desconto is None or
                    float(desconto) < min_discount_pct or not oferta.get("title") or
                    not oferta.get("canonical_url")):
                continue
            vistos.add(external_id)

            existente = (db._get().table("products").select("id")
                         .eq("organization_id", organization_id)
                         .eq("source_name", "mercadolivre")
                         .eq("external_id", external_id).limit(1)
                         .execute().data)
            if existente:
                continue

            produto = _product_row(organization_id, oferta)
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
                    "external_id": external_id,
                    "discount_pct": desconto,
                    "affiliate_link": "PENDING_OFFICIAL_TOOL",
                    "query": termo,
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
    }
