"""Topfy Affiliate OS — conector Mercado Livre (importação manual).

Automação de compra é proibida pela plataforma; este conector só LÊ dados
públicos de anúncios via API oficial (api.mercadolibre.com, GET /items —
sem autenticação) para o fluxo de importação manual de URL. O OAuth do app
(credenciais em ml_credentials) é para dados da conta do usuário, não para
leitura de anúncio.

Link de afiliado: o programa "Mercado Livre Afiliados" não tem API pública
de geração — o usuário cola o link gerado no painel oficial; por isso
generate_affiliate_link é sempre manual (verification_status nunca
'VERIFIED' sem evidência).

Nunca inventa preço, avaliação, comissão ou link de afiliado.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from . import CredencialNaoConfigurada, MarketplaceConnector

API_BASE = "https://api.mercadolibre.com"
# Padrão sem classes de caractere consecutivas: o módulo `re` do Python
# 3.14 (3.14.6) tem regressão que quebra literal + classe + classe
# (ex: ML[A-Z][A-Z] não casa "MLB"). Alternância explícita funciona.
ITEM_ID_RE = re.compile(r"\bML(?:B|A|C|M|U|T|V|P|EC|CO)-?(\d{7,15})\b")
# meli.la: encurtador oficial do ML (link de "compartilhar" do app) — o ID
# do anúncio só aparece na URL final, depois do redirect.
SHORTLINK_HOSTS = ("meli.la",)
REDIRECT_MAX = 5
REDIRECT_TIMEOUT = 12


class _RedirectCapturado(Exception):
    def __init__(self, url: str) -> None:
        super().__init__(url)
        self.url = url


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    """Captura o Location do redirect sem seguir automaticamente — o
    chamador decide a próxima URL (loop com limite)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl) -> Any:
        raise _RedirectCapturado(newurl)


def _resolve_shortlink(url: str) -> Optional[str]:
    """Segue o redirect do meli.la só pelos cabeçalhos Location (nunca
    baixa o body). Best-effort: falha -> None (cai no erro de ID não
    encontrado, que já orienta o usuário a colar o link do anúncio)."""
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


def _get_json(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, method="GET",
                                 headers={"Accept": "application/json",
                                          "User-Agent": "TopfyAffiliateOS/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _para_float(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _para_int(valor: Any) -> Optional[int]:
    numero = _para_float(valor)
    return int(numero) if numero is not None else None


def _resolver_categoria(category_id: Optional[str]) -> Optional[str]:
    """Nome legível da categoria via /categories/{id} (path_from_root).
    Nunca quebra a importação se a chamada falhar."""
    if not category_id:
        return None
    try:
        bruto = _get_json(f"{API_BASE}/categories/{category_id}")
    except (urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(bruto, dict):
        return None
    path = bruto.get("path_from_root") or []
    nomes = [p.get("name") for p in path if isinstance(p, dict) and p.get("name")]
    return " > ".join(nomes) if nomes else None


def _parse_produto_api(bruto: dict[str, Any]) -> dict[str, Any]:
    preco = _para_float(bruto.get("price"))
    preco_original = _para_float(bruto.get("original_price"))
    desconto = None
    if preco and preco_original and preco_original > preco:
        desconto = round((1 - preco / preco_original) * 100, 2)

    imagens = [
        img.get("secure_url") or img.get("url")
        for img in (bruto.get("pictures") or [])
        if isinstance(img, dict) and (img.get("secure_url") or img.get("url"))
    ]
    vendedor = bruto.get("seller") or {}
    seller_id = bruto.get("seller_id") or vendedor.get("id")

    return {
        "external_product_id": bruto.get("id"),
        "canonical_url": bruto.get("permalink"),
        "title": bruto.get("title"),
        "main_image_url": bruto.get("thumbnail"),
        "image_urls": json.dumps(imagens, ensure_ascii=False) if imagens else None,
        "category": None,  # resolvido depois (chamada extra) e preenchido por get_product
        "seller_id": str(seller_id) if seller_id is not None else None,
        "seller_name": vendedor.get("nickname"),
        "current_price": preco,
        "original_price": preco_original,
        "discount_percent": desconto,
        "commission_percent": None,  # comissão só existe no painel de afiliados
        "sold_count": _para_int(bruto.get("sold_quantity")),
        "positive_feedback_percent": None,  # API pública não expõe avaliação
        "currency": bruto.get("currency_id") or "BRL",
        "method": "API",
        "source_confidence": "VERIFIED",
    }


class MercadoLivreConnector(MarketplaceConnector):
    code = "mercadolivre"

    def detect_url(self, url: str) -> bool:
        host = urllib.parse.urlparse(url).netloc.lower()
        return ("mercadolivre." in host or "mercadolibre." in host
                or host in SHORTLINK_HOSTS)

    def normalize_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))

    def _external_id(self, url: str) -> Optional[str]:
        match = ITEM_ID_RE.search(url)
        return match.group(0).replace("-", "") if match else None

    def get_product(self, url: str) -> dict[str, Any]:
        if not self.detect_url(url):
            raise ValueError(f"URL não é do Mercado Livre: {url}")

        host = urllib.parse.urlparse(url).netloc.lower()
        if host in SHORTLINK_HOSTS:
            resolvida = _resolve_shortlink(url)
            if resolvida:
                url = resolvida

        canonical = self.normalize_url(url)
        external_id = self._external_id(url)

        if not external_id:
            raise ValueError(
                "Não foi possível extrair o ID do anúncio da URL — "
                "esperado padrão MLB-<numero> (ex: "
                "produto.mercadolivre.com.br/MLB-2837492291-...). Se o "
                "link curto (meli.la) aponta para um perfil, loja ou "
                "busca em vez de um anúncio específico, cole o link do "
                "produto.")

        try:
            bruto = _get_json(f"{API_BASE}/items/{external_id}")
        except urllib.error.HTTPError as exc:
            return {
                "external_product_id": external_id,
                "canonical_url": canonical,
                "method": "API",
                "source_confidence": "NOT_AVAILABLE",
                "aviso": (
                    f"API oficial do Mercado Livre recusou a consulta "
                    f"(HTTP {exc.code}): anúncio inexistente, excluído ou "
                    f"inacessível."),
            }
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Mercado Livre API inacessível: {exc}") from exc

        if not isinstance(bruto, dict) or not bruto.get("id"):
            return {
                "external_product_id": external_id,
                "canonical_url": canonical,
                "method": "API",
                "source_confidence": "NOT_AVAILABLE",
                "aviso": "API oficial respondeu sem dados para este anúncio.",
            }

        campos = _parse_produto_api(bruto)
        campos["canonical_url"] = canonical
        campos["category"] = _resolver_categoria(bruto.get("category_id"))

        if not campos["seller_name"] and campos["seller_id"]:
            try:
                user = _get_json(f"{API_BASE}/users/{campos['seller_id']}")
                if isinstance(user, dict) and user.get("nickname"):
                    campos["seller_name"] = user["nickname"]
            except urllib.error.URLError:
                pass

        if campos["currency"] not in ("BRL", None):
            campos["aviso"] = (
                f"Anúncio em {campos['currency']} — a API pública do Mercado "
                f"Livre não converte moeda; preço abaixo é o preço local.")
        return campos

    def generate_affiliate_link(self, product_url: str) -> dict[str, Any]:
        raise CredencialNaoConfigurada(
            "mercadolivre: o programa Mercado Livre Afiliados não tem API "
            "pública de geração de link — cole aqui o link gerado por você "
            "no painel oficial de afiliados; ele entra como "
            "verification_status='UNKNOWN' até confirmação manual.")

    def verify_affiliate_link(self, affiliate_url: str) -> dict[str, Any]:
        return {
            "verification_status": "UNKNOWN",
            "verification_evidence": (
                "Sem endpoint público de verificação de link de afiliado no "
                "Mercado Livre — confirmação definitiva só com relatório de "
                "clique/conversão do painel de afiliados."),
        }

    def health_check(self) -> dict[str, Any]:
        try:
            bruto = _get_json(f"{API_BASE}/items/MLB1")
        except Exception as exc:
            return {
                "connector_type": "API",
                "credential_status": "NOT_REQUIRED",
                "health_status": "DOWN",
                "detalhe": f"Falha de rede: {exc}",
            }
        if isinstance(bruto, dict) and bruto.get("id"):
            return {
                "connector_type": "API",
                "credential_status": "NOT_REQUIRED",
                "health_status": "OK",
                "detalhe": "GET /items respondeu (API pública, sem credencial).",
            }
        return {
            "connector_type": "API",
            "credential_status": "NOT_REQUIRED",
            "health_status": "DEGRADED",
            "detalhe": "API pública respondeu sem o formato esperado.",
        }
