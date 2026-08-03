"""Conector do programa Influenciador Magalu (Magazine Voce).

O programa de influenciadores nao emite token de API. A atribuicao acontece
pela vitrine oficial ``/magazine<slug>/`` e, nas paginas especiais, pelo
parametro ``showcase=magazine<slug>``. As APIs OAuth2 do Magalu Devs sao para
sellers/integradores e nao sao usadas aqui.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import unicodedata
from pathlib import Path
from typing import Any, Optional

from . import CredencialNaoConfigurada, MarketplaceConnector


PRODUCT_ID_RE = re.compile(r"/p/([^/?#]+)", re.I)
MAGALU_HOSTS = (
    "magazinevoce.com.br", "magazineluiza.com.br", "magalu.com",
)
SEED_OFFERS_PATH = Path(__file__).resolve().parents[1] / "data" / "magalu_seed_offers.json"


def _store_slug() -> str:
    return os.environ.get("MAGALU_STORE_SLUG", "").strip().lower()


def _store_key() -> str:
    slug = _store_slug()
    return slug if slug.startswith("magazine") else f"magazine{slug}"


def _is_magalu_host(host: str) -> bool:
    normalized = host.lower().split(":")[0]
    return any(
        normalized == allowed or normalized.endswith(f".{allowed}")
        for allowed in MAGALU_HOSTS
    )


class MagaluConnector(MarketplaceConnector):
    code = "magalu"

    def detect_url(self, url: str) -> bool:
        try:
            return _is_magalu_host(urllib.parse.urlparse(url).netloc)
        except ValueError:
            return False

    def normalize_url(self, url: str) -> str:
        if not self.detect_url(url):
            raise ValueError(f"URL nao e do Magalu: {url}")
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        seller_query = urllib.parse.urlencode(
            {"seller_id": query["seller_id"][0]}
        ) if query.get("seller_id") else ""
        return urllib.parse.urlunparse(parsed._replace(
            query=seller_query, fragment=""))

    def _affiliate_url(self, url: str) -> str:
        slug = _store_slug()
        if not slug:
            raise CredencialNaoConfigurada(
                "magalu: configure MAGALU_STORE_SLUG com o nome da vitrine"
            )
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path
        store_key = _store_key()

        if "especiais.magazineluiza.com.br" in host:
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            query["showcase"] = [store_key]
            return urllib.parse.urlunparse(parsed._replace(
                query=urllib.parse.urlencode(query, doseq=True), fragment=""))

        marker = f"/{store_key}/"
        if "magazinevoce.com.br" in host and marker in path.lower():
            normalized = urllib.parse.urlparse(self.normalize_url(url))
            return urllib.parse.urlunparse(parsed._replace(
                scheme="https", query=normalized.query, fragment=""))

        clean_path = path if path.startswith("/") else f"/{path}"
        affiliate_path = f"/{store_key}{clean_path}"
        affiliate_query = urllib.parse.urlparse(self.normalize_url(url)).query
        return urllib.parse.urlunparse((
            "https", "www.magazinevoce.com.br", affiliate_path,
            "", affiliate_query, "",
        ))

    def get_product(self, url: str) -> dict[str, Any]:
        canonical = self.normalize_url(url)
        product_id = PRODUCT_ID_RE.search(canonical)
        if not product_id:
            raise ValueError(
                "URL Magalu nao identifica um produto (/p/<id>); use uma "
                "pagina de produto da loja"
            )
        return {
            "external_product_id": product_id.group(1),
            "canonical_url": canonical,
            "title": None,
            "main_image_url": None,
            "current_price": None,
            "original_price": None,
            "discount_percent": None,
            "commission_percent": None,
            "sold_count": None,
            "currency": "BRL",
            "method": "MANUAL",
            "source_confidence": "UNKNOWN",
            "aviso": (
                "Link afiliado gerado pela vitrine oficial Magazine Voce; "
                "titulo, preco e imagem precisam de uma fonte oficial antes "
                "da publicacao automatica."
            ),
        }

    def generate_affiliate_link(self, product_url: str) -> dict[str, Any]:
        affiliate_url = self._affiliate_url(product_url)
        return {
            "affiliate_url": affiliate_url,
            "tracking_id": _store_key(),
            "generation_method": "OFFICIAL_STOREFRONT",
            "verification_status": "VERIFIED",
            "verification_evidence": (
                "URL usa a vitrine oficial Magazine Voce configurada para "
                f"{_store_key()}."
            ),
        }

    def verify_affiliate_link(self, affiliate_url: str) -> dict[str, Any]:
        try:
            generated = self._affiliate_url(affiliate_url)
        except (CredencialNaoConfigurada, ValueError):
            return {
                "verification_status": "INVALID",
                "verification_evidence": "URL ou vitrine Magalu invalida.",
            }
        parsed = urllib.parse.urlparse(generated)
        query = urllib.parse.parse_qs(parsed.query)
        store_key = _store_key()
        valid = (
            f"/{store_key}/" in parsed.path.lower()
            or query.get("showcase") == [store_key]
        )
        return {
            "verification_status": "VERIFIED" if valid else "INVALID",
            "verification_evidence": (
                "Vitrine oficial presente na URL."
                if valid else "Vitrine oficial ausente da URL."
            ),
        }

    @staticmethod
    def _normalized_terms(value: str) -> set[str]:
        plain = unicodedata.normalize("NFKD", value or "")
        plain = "".join(c for c in plain if not unicodedata.combining(c))
        return set(re.findall(r"[a-z0-9]+", plain.lower()))

    def _seed_offers(self) -> list[dict[str, Any]]:
        """Carrega o catálogo inicial auditável de páginas oficiais indexadas."""
        try:
            rows = json.loads(SEED_OFFERS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        return [dict(row) for row in rows if isinstance(row, dict)]

    def search_offers(self, query: str, *, page_no: int = 1) -> list[dict[str, Any]]:
        if page_no != 1:
            return []
        offers = self._seed_offers()
        wanted = self._normalized_terms(query)
        if not wanted or wanted & {"todos", "magalu", "ofertas"}:
            return offers
        return [offer for offer in offers if wanted & self._normalized_terms(
            f"{offer.get('title', '')} {offer.get('category', '')}")]

    def health_check(self) -> dict[str, Any]:
        slug = _store_slug()
        seed_count = len(self._seed_offers())
        return {
            "connector_type": "OFFICIAL_STOREFRONT",
            "credential_status": "ACTIVE" if slug else "NOT_CONFIGURED",
            "health_status": "OK" if slug else "DOWN",
            "detalhe": (
                f"Vitrine magazine{slug} configurada; token nao se aplica; "
                f"{seed_count} ofertas oficiais indexadas disponíveis."
                if slug else "Configure MAGALU_STORE_SLUG."
            ),
            "seed_offer_count": seed_count,
        }
