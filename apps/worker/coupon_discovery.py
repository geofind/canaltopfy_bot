"""Descoberta segura de cupons/campanhas em fontes oficiais.

O canal de referencia serve apenas para calibrar formato e cobertura. Nenhum
codigo, texto ou link de terceiro entra no banco. Nesta primeira versao, a
fonte automatica e ``shopeeOfferV2`` da Affiliate Open API: o ``offerLink`` ja
e gerado para as credenciais da conta Topfy.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import db
from connectors.shopee import ShopeeConnector
from content import DISCLAIMER_PADRAO
from pipeline import approve_campaign, montar_copy_text


COUPON_TERMS = re.compile(
    r"\b(cupom|coupon|voucher|desconto|discount|off|frete gratis|cashback)\b",
    re.IGNORECASE,
)
CODE_PATTERNS = (
    re.compile(r"\b(?:codigo|cupom)\s*[:\-]\s*([A-Z0-9]{4,20})\b", re.I),
    re.compile(r"\buse\s+([A-Z][A-Z0-9]{3,19})\b", re.I),
)


def _unix_to_iso(value: Any) -> Optional[str]:
    if value in (None, "", 0, "0"):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _active_now(offer: dict[str, Any], now: datetime) -> bool:
    current = int(now.timestamp())
    try:
        starts = int(offer.get("period_start_time") or 0)
        ends = int(offer.get("period_end_time") or 0)
    except (TypeError, ValueError):
        return False
    return (not starts or starts <= current) and (not ends or current <= ends)


def extract_verified_code(title: Any) -> Optional[str]:
    """Extrai apenas quando o proprio nome oficial declara codigo/cupom."""
    text = str(title or "")
    for pattern in CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).upper()
    return None


def coupon_copy(offer: dict[str, Any]) -> dict[str, str]:
    """Copy escaneavel inspirada no padrao observado, com identidade Topfy."""
    source = str(offer.get("source_name") or "shopee").upper()
    title = str(offer.get("title") or f"Cupom {source}").strip()
    code = offer.get("coupon_code")
    lines = [f"🎟 {title}"]
    if code:
        lines.append(f"🏷 CÓDIGO: {code}")
    else:
        lines.append("✅ Resgate direto pelo link oficial")
    if offer.get("app_only"):
        lines.append("📱 Válido somente no APP")
    lines.append("⏳ Pode esgotar ou mudar sem aviso — confira antes de pagar.")
    return {
        "headline": f"🔥 CUPOM {source} DISPONÍVEL",
        "body": "\n".join(lines),
        "cta": "🔗 Resgatar com o link Topfy",
        "disclaimer": DISCLAIMER_PADRAO,
    }


def _already_imported(organization_id: str, source_url: str,
                      external_id: Optional[str]) -> bool:
    query = (db._get().table("products").select("id")
             .eq("organization_id", organization_id))
    if external_id:
        query = query.eq("external_id", external_id)
    else:
        query = query.eq("source_url", source_url)
    return bool(query.limit(1).execute().data)


def _create_coupon_campaign(organization_id: str,
                            offer: dict[str, Any]) -> dict[str, str]:
    campaign_id = str(uuid.uuid4())
    source_url = str(offer.get("canonical_url") or offer["affiliate_url"])
    coupon_code = extract_verified_code(offer.get("title"))
    card_config = {
        "coupon_offer": {
            "coupon_code": coupon_code,
            "verification_method": "shopee_offer_v2",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "valid_from": _unix_to_iso(offer.get("period_start_time")),
            "valid_until": _unix_to_iso(offer.get("period_end_time")),
            "app_only": bool(offer.get("app_only")),
            "offer_type": offer.get("offer_type"),
        },
    }
    product = (db._get().table("products").insert({
        "organization_id": organization_id,
        "status": "READY",
        "source_name": "shopee",
        "source_url": source_url,
        "external_id": offer.get("external_product_id"),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "method": "API",
        "title": str(offer.get("title") or "Cupom Shopee"),
        "description": "Campanha oficial capturada pela Shopee Affiliate Open API.",
        "image_url": offer.get("main_image_url"),
        "affiliate_link": offer["affiliate_url"],
        "affiliate_link_status": "VERIFIED",
        "category": "Cupons > Shopee",
        "confidence": "VERIFIED",
        "commission_pct": offer.get("commission_percent"),
        "score": 70,
        "score_breakdown": {"coupon_source": "shopee_offer_v2"},
        "score_updated_at": datetime.now(timezone.utc).isoformat(),
        "card_config": card_config,
    }).execute().data or [])[0]
    db._get().table("campaigns").insert({
        "id": campaign_id,
        "organization_id": organization_id,
        "product_id": product["id"],
        "status": "READY",
        "platform": "telegram",
        "mode": "simulated",
        "title": offer.get("title") or "Cupom Shopee",
        "slug": campaign_id,
    }).execute()
    copy = coupon_copy({
        **offer, "source_name": "shopee", "coupon_code": coupon_code})
    content = (db._get().table("contents").insert({
        "campaign_id": campaign_id,
        "version": 1,
        "status": "PENDING_REVIEW",
        "provider": "fallback",
        "copy_text": montar_copy_text(copy),
        "hooks": [],
        "compliance": {
            "validation_errors": [],
            "coupon_source": "shopee_offer_v2",
            "verified_code": bool(coupon_code),
        },
    }).execute().data or [])[0]
    approve_campaign(campaign_id, [str(content["id"])], actor_type="worker")
    return {"campaign_id": campaign_id, "product_id": str(product["id"])}


def capture_shopee_coupons(
    organization_id: str, *, max_new: int = 3,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    connector = ShopeeConnector()
    # Consulta a lista inteira: o endpoint pode usar nomes de campanha em
    # ingles mesmo na conta BR, entao filtrar "cupom" no servidor perderia
    # campanhas. A classificacao conservadora acontece localmente abaixo.
    offers = connector.search_campaign_offers("")
    candidates = [
        offer for offer in offers
        if offer.get("affiliate_url")
        and offer.get("affiliate_link_status") == "VERIFIED"
        and COUPON_TERMS.search(str(offer.get("title") or ""))
        and _active_now(offer, moment)
    ]
    created: list[dict[str, str]] = []
    for offer in candidates:
        source_url = str(offer.get("canonical_url") or offer["affiliate_url"])
        if _already_imported(
                organization_id, source_url, offer.get("external_product_id")):
            continue
        created.append(_create_coupon_campaign(organization_id, offer))
        if len(created) >= max(1, max_new):
            break
        time.sleep(0)
    db.register_audit(
        organization_id, actor_type="worker",
        action="coupon_discovery_shopee",
        entity_type="coupon_campaign", entity_id="shopee_offer_v2",
        metadata={"found": len(candidates), "created": len(created)},
    )
    return {"found": len(candidates), "created": len(created),
            "campaigns": created}
