"""Topfy Affiliate OS — conector Amazon (importação manual).

A Amazon descontinuou a PA-API (15/05/2026) e a nova Creators API exige
elegibilidade (10 vendas qualificadas nos últimos 30 dias) — por isso este
conector é ESTRITAMENTE manual:

- Lê só o que dá da URL/redirect (amzn.to -> página canônica de produto):
  ASIN e canonical_url. Nunca raspa a página em busca de preço/título;
- Nunca inventa preço, avaliação, comissão ou link de afiliado;
- o link amzn.to que o usuário cola JÁ é o link de afiliado dele:
  generate_affiliate_link devolve a própria URL (amzn.to ou URL com a tag)
  com verification_status='UNKNOWN' — nunca 'VERIFIED' sem relatório de
  clique/conversão do painel da Amazon;
- URLs de categoria/lista (browse node `?node=`, busca `/s`, vitrines) são
  rejeitadas com erro claro: não existe um produto único para campanha.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from . import CredencialNaoConfigurada, MarketplaceConnector

# ID do produto da Amazon (ASIN): 10 caracteres alfanuméricos.
# (sem classes consecutivas do re 3.14 para a ASIN em si — só uma classe)
ASIN_RE = re.compile(r"/(?:dp|gp/(?:a/)?product|gp/aws/product)/([A-Z0-9]{10})")
ASIN_PARAM_RE = re.compile(r"[?&](?:productId|asin)=([A-Z0-9]{10})")

AMAZON_HOSTS = ("amazon.", "amzn.to", "amzn.com")
AMAZON_HOSTS = ("amazon.", "amzn.to", "amzn.com")
REDIRECT_MAX = 5
REDIRECT_TIMEOUT = 12


class _RedirectCapturado(Exception):
    def __init__(self, url: str) -> None:
        super().__init__(url)
        self.url = url


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    """Captura o Location do redirect SEM seguir sequência automática —
    o chamador decide a próxima URL (loop com limite)."""

    def redirect_request(
        self, req, fp, code, msg, headers, newurl
    ) -> Any:
        raise _RedirectCapturado(newurl)


def _is_categoria(url: str) -> bool:
    """URL de categoria/lista não é produto:
      - browse node:  /b/...?node=... ou ?node=...
      - busca:        /s?k=... ou /s/<termo> ou /s?bbn=
      - vitrine/top:  /gp/bestsellers, /bestsellers, /wall, /resolver
    """
    partes = urllib.parse.urlparse(url)
    path = partes.path.lower()
    query = partes.query.lower()
    if partes.netloc.endswith("amzn.to") or partes.netloc == "amzn.to":
        return False  # link curto é de produto; só depois resolve
    if "node=" in query and "productid" not in query:
        return True
    if path.endswith("/b") or "/b/" in path or path in ("/b", ""):
        if "node" in query:
            return True
    if path.startswith("/s") or path.startswith("/search") or "k=" in query:
        return True
    if any(part in path for part in (
            "/bestsellers", "/bestseller/z", "/new-releases", "/wall",
            "/promozone", "/gp/bestsellers", "/storefront", "/l/",
            "/dl/", "/dasher")):
        return True
    return False


def _host_amazon(host: str) -> bool:
    h = host.lower()
    return any(padrao in h for padrao in AMAZON_HOSTS)


def _resolve_product_url(url: str) -> Optional[str]:
    """Segue redirects (amzn.to, /gp/... regionais) só via cabeçalhos
    Location — nunca baixa o body. Best-effort: falha -> None."""
    atual = url
    for _ in range(REDIRECT_MAX):
        try:
            opener = urllib.request.build_opener(_NoAutoRedirect())
            req = urllib.request.Request(
                atual, headers={"User-Agent": "TopfyAffiliateOS/0.1",
                                "Accept": "text/html,*/*"})
            with opener.open(req, timeout=REDIRECT_TIMEOUT) as resp:
                return resp.geturl()
        except _RedirectCapturado as r:
            atual = r.url
            continue
        except (urllib.error.URLError, urllib.error.HTTPError,
                OSError, ValueError):
            return None
    return None


def _extrair_asin(url: str) -> Optional[str]:
    m = ASIN_RE.search(url)
    if m:
        return m.group(1)
    m = ASIN_PARAM_RE.search(url)
    return m.group(1) if m else None


class AmazonConnector(MarketplaceConnector):
    code = "amazon"

    def detect_url(self, url: str) -> bool:
        try:
            return _host_amazon(urllib.parse.urlparse(url).netloc.lower())
        except ValueError:
            return False

    def normalize_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))

    def get_product(self, url: str) -> dict[str, Any]:
        if not self.detect_url(url):
            raise ValueError(f"URL não é da Amazon: {url}")

        if _is_categoria(url):
            raise ValueError(
                "URL da Amazon é de CATEGORIA/vitrine, não de um produto — "
                "cole a URL de um produto (ex.: <dominio>/dp/<ASIN> ou "
                "amzn.to/...) para criar uma campanha.")

        # amzn.to -> canonical da Amazon (só cabeçalhos, best-effort)
        canonical = self._resolve(url)
        if canonical and _is_categoria(canonical):
            raise ValueError(
                "O link amzn.to resolve para uma página de CATEGORIA da "
                "Amazon, não para um produto — cole um link de produto "
                "(ex.: .../dp/<ASIN>).")
        canonical = self.normalize_url(canonical or url)
        external_id = _extrair_asin(canonical)

        return {
            "external_product_id": external_id,
            "canonical_url": canonical,
            "title": None,          # manual — nunca inventa título
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
                "Amazon sem API pública de dados (PA-API descontinuada; "
                "Creators exige elegibilidade) — preencha título, preço e "
                "imagem manualmente antes de redigir a copy. "
                "O link amzn.to/tag usado como afiliado precisa de "
                "confirmação no painel da Amazon."
            ),
        }

    def _resolve(self, url: str) -> Optional[str]:
        return _resolve_product_url(url)

    def generate_affiliate_link(self, product_url: str) -> dict[str, Any]:
        host = urllib.parse.urlparse(product_url).netloc.lower()
        is_amzn = "amzn." in host
        tem_tag = "tag=" in urllib.parse.urlparse(product_url).query.lower()
        if not (is_amzn or tem_tag):
            raise CredencialNaoConfigurada(
                "amazon: sem URL de afiliado — cole o link que a Amazon gerou "
                "para você (formato amzn.to/... ou ...?tag=<seu_tag>); ele "
                "entra como verification_status='UNKNOWN' até clique/conversão "
                "do painel (Creators exige elegibilidade para a API).")
        return {
            "affiliate_url": product_url,
            "generation_method": "MANUAL",
            "verification_status": "UNKNOWN",
            "verification_evidence": (
                "Programa Amazon Creators exige elegibilidade (10 vendas "
                "qualificadas/30 dias) e não tem API pública no Brasil; link "
                "do usuário registrado em modo manual. Confirmação só com "
                "clique/conversão no painel da Amazon."),
        }

    def verify_affiliate_link(self, affiliate_url: str) -> dict[str, Any]:
        return {
            "verification_status": "UNKNOWN",
            "verification_evidence": (
                "Sem endpoint público de verificação de link de afiliado da "
                "Amazon — confirmação definitiva só com relatório do painel "
                "Amazon Creators."),
        }

    def search_offers(self, query: str) -> list[dict[str, Any]]:
        raise CredencialNaoConfigurada(
            "amazon: busca por termo exige a API oficial (Creators com "
            "elegibilidade) — não disponível em modo manual.")

    def health_check(self) -> dict[str, Any]:
        return {
            "connector_type": "MANUAL",
            "credential_status": "NOT_CONFIGURED",
            "health_status": "OK",
            "detalhe": (
                "Modo manual — importação por URL amzn./url de produto, sem "
                "escolher API (PA-API descontinuada em 15/05/2026)."),
        }