"""Topfy Affiliate OS — conector AliExpress (portado do CanalTopfy Lab).

Modo API (ALIEXPRESS_APP_KEY + ALIEXPRESS_APP_SECRET): Affiliate API oficial
(open.aliexpress.com). HMAC-SHA256 testada contra o serviço ao vivo com
credencial real (app 541338) — resp_code 200 em product.query,
productdetail.get e link.generate. Modo manual: só o que dá para ler da URL.

Nunca inventa preço, avaliação, cupom ou link de afiliado.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from . import CredencialNaoConfigurada, MarketplaceConnector

API_GATEWAY = "https://api-sg.aliexpress.com/sync"
PRODUCT_ID_RE = re.compile(r"/item/(\d+)\.html")


def _credenciais() -> Optional[tuple[str, str, Optional[str]]]:
    app_key = os.environ.get("ALIEXPRESS_APP_KEY")
    app_secret = os.environ.get("ALIEXPRESS_APP_SECRET")
    if not app_key or not app_secret:
        return None
    tracking_id = os.environ.get("ALIEXPRESS_TRACKING_ID")
    return app_key, app_secret, tracking_id


def _assinar(params: dict[str, str], app_secret: str) -> str:
    concatenado = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(app_secret.encode("utf-8"), concatenado.encode("utf-8"),
                    hashlib.sha256).hexdigest().upper()


def _chamar_api(method: str, app_key: str, app_secret: str,
                extra_params: dict[str, str]) -> dict[str, Any]:
    params = {
        "app_key": app_key,
        "method": method,
        "sign_method": "sha256",
        "timestamp": str(int(time.time() * 1000)),
        "v": "2.0",
        "format": "json",
        **extra_params,
    }
    params["sign"] = _assinar(params, app_secret)
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(API_GATEWAY, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"AliExpress API ({method}) inacessível: {exc}") from exc


def _para_float(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().rstrip("%").strip()
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _para_int(valor: Any) -> Optional[int]:
    numero = _para_float(valor)
    return int(numero) if numero is not None else None


def _parse_produto_api(bruto: dict[str, Any]) -> dict[str, Any]:
    product_id = bruto.get("product_id")
    imagens_extra = (bruto.get("product_small_image_urls") or {}).get("string") or []
    categoria = " > ".join(
        nome for nome in (
            bruto.get("first_level_category_name"),
            bruto.get("second_level_category_name"),
        ) if nome) or None

    comissao = _para_float(bruto.get("commission_rate"))
    if comissao is None:
        comissao = _para_float(bruto.get("hot_product_commission_rate"))

    return {
        "external_product_id": str(product_id) if product_id is not None else None,
        "canonical_url": bruto.get("product_detail_url"),
        "title": bruto.get("product_title"),
        "main_image_url": bruto.get("product_main_image_url"),
        "image_urls": json.dumps(imagens_extra, ensure_ascii=False) if imagens_extra else None,
        "category": categoria,
        "seller_id": str(bruto["shop_id"]) if bruto.get("shop_id") is not None else None,
        "seller_name": bruto.get("shop_name"),
        "current_price": _para_float(bruto.get("target_sale_price")),
        "original_price": _para_float(bruto.get("target_original_price")),
        "discount_percent": _para_float(bruto.get("discount")),
        "commission_percent": comissao,
        "sold_count": _para_int(bruto.get("lastest_volume")),
        "positive_feedback_percent": _para_float(bruto.get("evaluate_rate")),
        "currency": bruto.get("target_sale_price_currency") or "BRL",
        "method": "API",
        "source_confidence": "VERIFIED",
    }


class AliExpressConnector(MarketplaceConnector):
    code = "aliexpress"

    def detect_url(self, url: str) -> bool:
        host = urllib.parse.urlparse(url).netloc.lower()
        return "aliexpress." in host

    def normalize_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))

    def _external_id(self, url: str) -> Optional[str]:
        match = PRODUCT_ID_RE.search(url)
        return match.group(1) if match else None

    def get_product(self, url: str) -> dict[str, Any]:
        if not self.detect_url(url):
            raise ValueError(f"URL não é da AliExpress: {url}")
        canonical = self.normalize_url(url)
        external_id = self._external_id(url)
        creds = _credenciais()

        if creds is None:
            return {
                "external_product_id": external_id,
                "canonical_url": canonical,
                "title": None,
                "current_price": None,
                "original_price": None,
                "discount_percent": None,
                "commission_percent": None,
                "main_image_url": None,
                "sold_count": None,
                "positive_feedback_percent": None,
                "currency": "BRL",
                "method": "MANUAL",
                "source_confidence": "UNKNOWN",
                "aviso": (
                    "Sem ALIEXPRESS_APP_KEY/ALIEXPRESS_APP_SECRET configurados — "
                    "preencha os campos manualmente. ID do produto "
                    f"{'detectado: ' + external_id if external_id else 'não detectado na URL'}."
                ),
            }

        if not external_id:
            raise ValueError(
                "Não foi possível extrair o ID do produto da URL — "
                "esperado padrão /item/<numero>.html")

        app_key, app_secret, tracking_id = creds
        resposta = _chamar_api(
            "aliexpress.affiliate.productdetail.get", app_key, app_secret,
            {"product_ids": external_id, "target_currency": "BRL",
             "target_language": "PT", "tracking_id": tracking_id or ""})
        resp_result = resposta.get(
            "aliexpress_affiliate_productdetail_get_response", {}).get("resp_result", {})
        if resp_result.get("resp_code") != 200:
            return {
                "external_product_id": external_id,
                "canonical_url": canonical,
                "method": "API",
                "source_confidence": "NOT_AVAILABLE",
                "aviso": (
                    f"API oficial recusou a consulta (resp_code="
                    f"{resp_result.get('resp_code')}): {resp_result.get('resp_msg')}"),
            }
        produtos = resp_result.get("result", {}).get("products", {}).get("product", [])
        if not produtos:
            return {
                "external_product_id": external_id,
                "canonical_url": canonical,
                "method": "API",
                "source_confidence": "NOT_AVAILABLE",
                "aviso": "API oficial respondeu sem dados para este product_id.",
            }
        campos = _parse_produto_api(produtos[0])
        campos["canonical_url"] = canonical
        return campos

    def search_offers(self, query: str) -> list[dict[str, Any]]:
        creds = _credenciais()
        if creds is None:
            raise CredencialNaoConfigurada(
                "aliexpress: busca por termo exige "
                "ALIEXPRESS_APP_KEY/ALIEXPRESS_APP_SECRET configurados")
        app_key, app_secret, tracking_id = creds
        resposta = _chamar_api(
            "aliexpress.affiliate.product.query", app_key, app_secret,
            {"keywords": query, "page_no": "1", "page_size": "20",
             "target_currency": "BRL", "target_language": "PT",
             "tracking_id": tracking_id or ""})
        resp_result = resposta.get(
            "aliexpress_affiliate_product_query_response", {}).get("resp_result", {})
        if resp_result.get("resp_code") != 200:
            raise RuntimeError(
                f"AliExpress product.query recusado (resp_code="
                f"{resp_result.get('resp_code')}): {resp_result.get('resp_msg')}")
        produtos = resp_result.get("result", {}).get("products", {}).get("product", [])
        resultado = []
        for bruto in produtos:
            campos = _parse_produto_api(bruto)
            if campos.get("canonical_url"):
                campos["canonical_url"] = self.normalize_url(campos["canonical_url"])
            resultado.append(campos)
        return resultado

    def generate_affiliate_link(self, product_url: str) -> dict[str, Any]:
        creds = _credenciais()
        if creds is None:
            raise CredencialNaoConfigurada(
                "aliexpress: gerar link de afiliado exige "
                "ALIEXPRESS_APP_KEY/ALIEXPRESS_APP_SECRET (API oficial) — "
                "sem isso, cole aqui um link já gerado por você no portal "
                "oficial de afiliados; ele entra como "
                "verification_status='UNKNOWN' até validação.")
        app_key, app_secret, tracking_id = creds
        canonical = self.normalize_url(product_url)
        resposta = _chamar_api(
            "aliexpress.affiliate.link.generate", app_key, app_secret,
            {"source_values": canonical, "tracking_id": tracking_id or "",
             "promotion_link_type": "0"})
        resp_result = resposta.get(
            "aliexpress_affiliate_link_generate_response", {}).get("resp_result", {})
        if resp_result.get("resp_code") != 200:
            return {
                "affiliate_url": None,
                "generation_method": "API",
                "verification_status": "NOT_AVAILABLE",
                "erro": (
                    f"API oficial recusou a geração do link (resp_code="
                    f"{resp_result.get('resp_code')}): {resp_result.get('resp_msg')}"),
            }
        links = resp_result.get("result", {}).get("promotion_links", {}).get("promotion_link", [])
        affiliate_url = links[0].get("promotion_link") if links else None
        if not affiliate_url:
            return {
                "affiliate_url": None,
                "generation_method": "API",
                "verification_status": "NOT_AVAILABLE",
                "erro": (
                    "API oficial respondeu resp_code 200 mas sem "
                    "promotion_link no resultado — produto pode não estar "
                    "elegível para afiliação."),
            }
        return {
            "affiliate_url": affiliate_url,
            "tracking_id": tracking_id,
            "generation_method": "API",
            "verification_status": "VERIFIED",
            "verification_evidence": (
                "Link gerado com sucesso pela API oficial de afiliados da "
                "AliExpress (aliexpress.affiliate.link.generate, resp_code "
                "200) — confirma geração real vinculada ao tracking_id "
                "configurado; não confirma clique/conversão."),
        }

    def verify_affiliate_link(self, affiliate_url: str) -> dict[str, Any]:
        creds = _credenciais()
        if creds is None:
            raise CredencialNaoConfigurada(
                "aliexpress: verificação automática exige API oficial "
                "configurada — sem isso, verificação fica UNKNOWN "
                "até confirmação manual no painel de afiliados.")
        return {
            "verification_status": "UNKNOWN",
            "verification_evidence": (
                "Sem endpoint dedicado de verificação na API oficial de "
                "afiliados da AliExpress — confirmação definitiva só com "
                "relatório de clique/conversão ou nova chamada a "
                "generate_affiliate_link."),
        }

    def health_check(self) -> dict[str, Any]:
        creds = _credenciais()
        if creds is None:
            return {
                "connector_type": "MANUAL",
                "credential_status": "NOT_CONFIGURED",
                "health_status": "OK",
                "detalhe": "Modo manual — colar URL, sem chamada de rede.",
            }
        app_key, app_secret, tracking_id = creds
        try:
            resposta = _chamar_api(
                "aliexpress.affiliate.product.query", app_key, app_secret,
                {"keywords": "teste", "page_no": "1", "page_size": "1",
                 "target_currency": "BRL", "target_language": "PT",
                 "tracking_id": tracking_id or ""})
        except RuntimeError as exc:
            return {
                "connector_type": "API",
                "credential_status": "ERROR",
                "health_status": "DOWN",
                "detalhe": f"Falha de rede: {exc}",
            }
        resp_result = resposta.get(
            "aliexpress_affiliate_product_query_response", {}).get("resp_result", {})
        if resp_result.get("resp_code") == 200:
            return {
                "connector_type": "API",
                "credential_status": "ACTIVE",
                "health_status": "OK",
                "detalhe": "aliexpress.affiliate.product.query respondeu resp_code 200.",
            }
        return {
            "connector_type": "API",
            "credential_status": "ERROR",
            "health_status": "DEGRADED",
            "detalhe": (
                f"resp_code={resp_result.get('resp_code')} "
                f"resp_msg={resp_result.get('resp_msg')}"),
        }
