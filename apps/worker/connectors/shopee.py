"""Conector da Shopee Affiliate Open API Brasil.

Usa somente o endpoint GraphQL oficial do programa de afiliados. A assinatura
é SHA-256 sobre ``app_id + timestamp + payload_exato + secret``; o mesmo payload
assinado é enviado no corpo para evitar divergências de serialização.

Nunca usa cookies, sessão do navegador, endpoints privados ou scraping.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

from . import CredencialNaoConfigurada, MarketplaceConnector

DEFAULT_ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
PRODUCT_ID_RE = re.compile(
    r"(?:-i\.\d+\.|/product/\d+/)(\d{6,20})(?:\D|$)")
SHOPEE_HOSTS = ("shopee.com.br", "s.shopee.com.br", "shope.ee")


class ShopeeAPIError(RuntimeError):
    """Erro seguro da API, sem incluir credenciais ou header de autorização."""


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _credentials() -> Optional[tuple[str, str]]:
    # SHOPPE_* é aceito como compatibilidade com o .env já usado pelo projeto.
    app_id = _first_env("SHOPEE_AFFILIATE_APP_ID", "SHOPPE_APP_KEY")
    secret = _first_env("SHOPEE_AFFILIATE_SECRET", "SHOPPE_APP_SECRET")
    if not app_id or not secret:
        return None
    return app_id, secret


def _endpoint() -> str:
    return _first_env("SHOPEE_AFFILIATE_ENDPOINT") or DEFAULT_ENDPOINT


def _sub_ids() -> list[str]:
    raw = _first_env("SHOPEE_AFFILIATE_SUB_IDS") or "canaltopfy,telegram"
    return [item.strip() for item in raw.split(",") if item.strip()][:5]


def _authorization(app_id: str, secret: str, payload: str,
                   timestamp: int) -> str:
    factor = f"{app_id}{timestamp}{payload}{secret}"
    signature = hashlib.sha256(factor.encode("utf-8")).hexdigest()
    return (
        f"SHA256 Credential={app_id}, Timestamp={timestamp}, "
        f"Signature={signature}"
    )


def _graphql(query: str, *, timestamp: Optional[int] = None,
             max_attempts: int = 3) -> dict[str, Any]:
    credentials = _credentials()
    if credentials is None:
        raise CredencialNaoConfigurada(
            "shopee: configure SHOPEE_AFFILIATE_APP_ID/SECRET ou os aliases "
            "SHOPPE_APP_KEY/SECRET no .env"
        )
    app_id, secret = credentials
    payload = json.dumps({"query": query}, ensure_ascii=False,
                         separators=(",", ":"))
    current_timestamp = int(time.time()) if timestamp is None else timestamp
    last_error: Optional[Exception] = None
    for attempt in range(max(1, max_attempts)):
        # O timestamp é recalculado nos retries para a assinatura continuar
        # válida mesmo após backoff; em testes determinísticos ele é fixo.
        signed_at = (current_timestamp if timestamp is not None
                     else int(time.time()))
        request = urllib.request.Request(
            _endpoint(), data=payload.encode("utf-8"), method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": _authorization(
                    app_id, secret, payload, signed_at),
                "User-Agent": "TopfyAffiliateOS/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < max_attempts:
                time.sleep(2 ** attempt)
                continue
            raise ShopeeAPIError(
                f"Shopee Affiliate API respondeu HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < max_attempts:
                time.sleep(2 ** attempt)
                continue
            raise ShopeeAPIError(
                "Shopee Affiliate API inacessível após tentativas") from exc

        errors = result.get("errors") or []
        if errors:
            first = errors[0] if isinstance(errors[0], dict) else {}
            code = (first.get("extensions") or {}).get("code")
            message = first.get("message") or "erro GraphQL sem mensagem"
            if str(code) == "10030" and attempt + 1 < max_attempts:
                time.sleep(2 ** attempt)
                continue
            raise ShopeeAPIError(
                f"Shopee Affiliate API recusou a chamada ({code}): {message}")
        data = result.get("data")
        if not isinstance(data, dict):
            raise ShopeeAPIError("Shopee Affiliate API respondeu sem objeto data")
        return data
    raise ShopeeAPIError(
        "Shopee Affiliate API inacessível após tentativas") from last_error


def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _percentage(value: Any, *, fraction: bool = False) -> Optional[float]:
    number = _number(value)
    if number is None:
        return None
    return round(number * 100 if fraction else number, 2)


def _original_price(price: Any, discount: Any) -> Optional[float]:
    try:
        price_decimal = Decimal(str(price))
        discount_decimal = Decimal(str(discount))
        if not 0 < discount_decimal < 100:
            return None
        result = price_decimal / (Decimal("1") - discount_decimal / Decimal("100"))
        return float(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError, ZeroDivisionError):
        return None


def _parse_offer(raw: dict[str, Any]) -> dict[str, Any]:
    price = _number(raw.get("priceMin"))
    discount = _percentage(raw.get("priceDiscountRate"))
    original_price = _original_price(price, discount)
    rating = _number(raw.get("ratingStar"))
    category_ids = raw.get("productCatIds") or []
    product_link = raw.get("productLink")
    return {
        "external_product_id": str(raw["itemId"]) if raw.get("itemId") is not None else None,
        "canonical_url": product_link,
        "title": raw.get("productName"),
        "main_image_url": raw.get("imageUrl"),
        "category": ">".join(str(item) for item in category_ids) or None,
        "seller_id": str(raw["shopId"]) if raw.get("shopId") is not None else None,
        "seller_name": raw.get("shopName"),
        "current_price": price,
        "original_price": original_price,
        "discount_percent": discount,
        "commission_percent": _percentage(raw.get("commissionRate"), fraction=True),
        "commission_amount": _number(raw.get("commission")),
        "sold_count": int(_number(raw.get("sales")) or 0),
        "rating_star": rating,
        "positive_feedback_percent": round(rating * 20, 2) if rating is not None else None,
        "currency": "BRL",
        "affiliate_url": raw.get("offerLink"),
        "affiliate_link_status": "VERIFIED" if raw.get("offerLink") else "NOT_AVAILABLE",
        "method": "API",
        "source_confidence": "VERIFIED",
        "price_source": "shopee_product_offer_v2",
    }


def _product_offer_query(*, keyword: str = "", item_id: Optional[str] = None,
                         page: int = 1, limit: int = 20) -> str:
    arguments = [f"page:{max(1, page)}", f"limit:{min(50, max(1, limit))}"]
    if keyword:
        arguments.append(f"keyword:{json.dumps(keyword, ensure_ascii=False)}")
        arguments.append("sortType:5")
    if item_id:
        if not str(item_id).isdigit():
            raise ValueError("item_id Shopee deve conter somente números")
        arguments.append(f"itemId:{item_id}")
    return """query {
  productOfferV2(%s) {
    nodes {
      itemId commissionRate sellerCommissionRate shopeeCommissionRate
      commission sales priceMax priceMin productCatIds ratingStar
      priceDiscountRate imageUrl productName shopId shopName shopType
      productLink offerLink periodStartTime periodEndTime
    }
    pageInfo { page limit hasNextPage }
  }
}""" % ",".join(arguments)


def _campaign_offer_query(*, keyword: str = "cupom", page: int = 1,
                          limit: int = 20) -> str:
    arguments = [f"page:{max(1, page)}", f"limit:{min(50, max(1, limit))}"]
    if keyword:
        arguments.append(f"keyword:{json.dumps(keyword, ensure_ascii=False)}")
    arguments.append("sortType:1")
    return """query {
  shopeeOfferV2(%s) {
    nodes {
      commissionRate imageUrl offerLink originalLink offerName offerType
      categoryId collectionId periodStartTime periodEndTime
    }
    pageInfo { page limit hasNextPage }
  }
}""" % ",".join(arguments)


def _parse_campaign_offer(raw: dict[str, Any]) -> dict[str, Any]:
    offer_type = int(_number(raw.get("offerType")) or 0)
    collection_id = raw.get("collectionId")
    category_id = raw.get("categoryId")
    external_id = (
        f"collection:{collection_id}" if collection_id is not None
        else f"category:{category_id}" if category_id is not None
        else None
    )
    return {
        "external_product_id": external_id,
        "canonical_url": raw.get("originalLink") or raw.get("offerLink"),
        "title": raw.get("offerName"),
        "main_image_url": raw.get("imageUrl"),
        "category": "Cupons > Shopee",
        "commission_percent": _percentage(
            raw.get("commissionRate"), fraction=True),
        "affiliate_url": raw.get("offerLink"),
        "affiliate_link_status": (
            "VERIFIED" if raw.get("offerLink") else "NOT_AVAILABLE"),
        "period_start_time": raw.get("periodStartTime"),
        "period_end_time": raw.get("periodEndTime"),
        "offer_type": offer_type,
        "method": "API",
        "source_confidence": "VERIFIED",
        "price_source": "shopee_offer_v2",
    }


class ShopeeConnector(MarketplaceConnector):
    code = "shopee"

    def detect_url(self, url: str) -> bool:
        host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
        return any(host == valid or host.endswith(f".{valid}")
                   for valid in SHOPEE_HOSTS)

    def normalize_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))

    def _external_id(self, url: str) -> Optional[str]:
        match = PRODUCT_ID_RE.search(url)
        return match.group(1) if match else None

    def search_offers(self, query: str, *, page_no: int = 1) -> list[dict[str, Any]]:
        data = _graphql(_product_offer_query(keyword=query, page=page_no, limit=20))
        connection = data.get("productOfferV2") or {}
        offers = connection.get("nodes") or []
        return [_parse_offer(item) for item in offers if isinstance(item, dict)]

    def search_campaign_offers(
        self, query: str = "cupom", *, page_no: int = 1,
    ) -> list[dict[str, Any]]:
        """Campanhas oficiais com offerLink afiliado da propria conta."""
        data = _graphql(_campaign_offer_query(
            keyword=query, page=page_no, limit=50))
        offers = (data.get("shopeeOfferV2") or {}).get("nodes") or []
        return [
            _parse_campaign_offer(item)
            for item in offers if isinstance(item, dict)
        ]

    def get_product(self, url: str) -> dict[str, Any]:
        if not self.detect_url(url):
            raise ValueError(f"URL não é da Shopee: {url}")
        item_id = self._external_id(url)
        if not item_id:
            raise ValueError("Não foi possível extrair o item_id da URL Shopee")
        if _credentials() is None:
            return {
                "external_product_id": item_id,
                "canonical_url": self.normalize_url(url),
                "method": "MANUAL",
                "source_confidence": "UNKNOWN",
                "aviso": "Credenciais da Shopee Affiliate API não configuradas.",
            }
        data = _graphql(_product_offer_query(item_id=item_id, limit=1))
        nodes = (data.get("productOfferV2") or {}).get("nodes") or []
        if not nodes:
            return {
                "external_product_id": item_id,
                "canonical_url": self.normalize_url(url),
                "method": "API",
                "source_confidence": "NOT_AVAILABLE",
                "aviso": "Produto não retornado entre as ofertas elegíveis da conta.",
            }
        return _parse_offer(nodes[0])

    def generate_affiliate_link(self, product_url: str) -> dict[str, Any]:
        if not self.detect_url(product_url):
            raise ValueError(f"URL não é da Shopee: {product_url}")
        origin = self.normalize_url(product_url)
        sub_ids = json.dumps(_sub_ids(), ensure_ascii=False, separators=(",", ":"))
        query = """mutation {
  generateShortLink(input:{originUrl:%s,subIds:%s}) { shortLink }
}""" % (json.dumps(origin, ensure_ascii=False), sub_ids)
        data = _graphql(query)
        short_link = (data.get("generateShortLink") or {}).get("shortLink")
        if not short_link:
            return {
                "affiliate_url": None,
                "generation_method": "API",
                "verification_status": "NOT_AVAILABLE",
                "erro": "Shopee respondeu sem shortLink para o produto.",
            }
        return {
            "affiliate_url": short_link,
            "tracking_id": ",".join(_sub_ids()),
            "generation_method": "API",
            "verification_status": "VERIFIED",
            "verification_evidence": (
                "Link retornado pela mutation generateShortLink da Shopee "
                "Affiliate Open API com as credenciais desta conta."
            ),
        }

    def verify_affiliate_link(self, affiliate_url: str) -> dict[str, Any]:
        if not self.detect_url(affiliate_url):
            return {
                "verification_status": "INVALID",
                "verification_evidence": "Domínio não pertence à Shopee.",
            }
        return {
            "verification_status": "UNKNOWN",
            "verification_evidence": (
                "O domínio é da Shopee, mas a atribuição só é confirmada pela "
                "geração na API ou pelo relatório de conversões."
            ),
        }

    def health_check(self) -> dict[str, Any]:
        if _credentials() is None:
            return {
                "connector_type": "API",
                "credential_status": "NOT_CONFIGURED",
                "health_status": "DOWN",
                "detalhe": "App ID e Secret da Shopee não configurados.",
            }
        try:
            offers = self.search_offers("smartphone")[:1]
        except ShopeeAPIError as exc:
            return {
                "connector_type": "API",
                "credential_status": "ERROR",
                "health_status": "DEGRADED",
                "detalhe": str(exc),
            }
        return {
            "connector_type": "API",
            "credential_status": "ACTIVE",
            "health_status": "OK",
            "detalhe": f"productOfferV2 autenticado; {len(offers)} oferta de prova.",
        }
