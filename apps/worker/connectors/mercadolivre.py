"""Topfy Affiliate OS — conector Mercado Livre (importação manual).

Automação de compra é proibida pela plataforma; este conector só LÊ dados
públicos de anúncios via API oficial (api.mercadolibre.com, GET /items) para
o fluxo de importação manual de URL.

Autenticação best-effort: a API pública tem devolvido 403 PolicyAgent
("PA_UNAUTHORIZED_RESULT_FROM_POLICIES") pra chamadas anônimas — a própria
documentação oficial do ML mostra GET /items com `Authorization: Bearer
$ACCESS_TOKEN`. Por isso o conector aceita um access_token opcional (vindo
do OAuth já conectado em ml_credentials, reaproveitado aqui — antes só era
usado pra dados da conta) e manda como Bearer quando disponível. Sem token
(ninguém conectou, ou expirou), cai no mesmo caminho anônimo de sempre — sem
regressão. Não é garantia de resolver o 403 (não investigado a fundo), e o
token deste app expira em ~6h sem refresh confiável (reconectar em
/integracoes quando vencer).

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
# meli.la: encurtador oficial do Mercado Livre (link de "compartilhar" do
# app) — o ID do anúncio só aparece na URL final, depois do redirect.
from ._shortlink import resolve_shortlink

SHORTLINK_HOSTS = ("meli.la",)


def _resolve_shortlink(url: str) -> Optional[str]:
    """Segue o redirect do link curto e devolve a URL final do anúncio.
    Best-effort: falha -> None (cai no erro de ID não encontrado, que já
    orienta o usuário a colar o link do anúncio)."""
    return resolve_shortlink(url)


def _get_json(url: str, timeout: int = 10,
              access_token: Optional[str] = None) -> Any:
    headers = {"Accept": "application/json",
               "User-Agent": "TopfyAffiliateOS/0.1"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(url, method="GET", headers=headers)
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


def _resolver_categoria(category_id: Optional[str],
                        access_token: Optional[str] = None) -> Optional[str]:
    """Nome legível da categoria via /categories/{id} (path_from_root).
    Nunca quebra a importação se a chamada falhar."""
    if not category_id:
        return None
    try:
        bruto = _get_json(f"{API_BASE}/categories/{category_id}",
                          access_token=access_token)
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


def _parse_catalog_offer(produto: dict[str, Any],
                         oferta: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Combina produto de catálogo e oferta concorrente da PDP."""
    catalog_id = str(produto.get("id") or "").strip()
    item_id = str(oferta.get("item_id") or "").strip()
    preco = _para_float(oferta.get("price"))
    original = _para_float(oferta.get("original_price"))
    currency = oferta.get("currency_id") or "BRL"
    if not catalog_id or not item_id or preco is None or currency != "BRL":
        return None
    desconto = None
    if original and original > preco:
        desconto = round((1 - preco / original) * 100, 2)
    imagens = [
        p.get("secure_url") or p.get("url")
        for p in (produto.get("pictures") or [])
        if isinstance(p, dict) and (p.get("secure_url") or p.get("url"))
    ]
    return {
        "external_product_id": item_id,
        "catalog_product_id": catalog_id,
        "canonical_url": (
            f"https://www.mercadolivre.com.br/p/{catalog_id}?wid={item_id}"),
        "title": produto.get("name") or produto.get("title"),
        "main_image_url": imagens[0] if imagens else None,
        "image_urls": json.dumps(imagens, ensure_ascii=False) if imagens else None,
        "category": produto.get("domain_id") or oferta.get("category_id"),
        "seller_id": (str(oferta.get("seller_id"))
                      if oferta.get("seller_id") is not None else None),
        "seller_name": None,
        "current_price": preco,
        "original_price": original,
        "discount_percent": desconto,
        "commission_percent": None,
        "sold_count": None,
        "positive_feedback_percent": None,
        "currency": currency,
        "method": "API",
        "source_confidence": "VERIFIED",
    }


def _melhor_oferta_catalogo(produto: dict[str, Any],
                            ofertas: list[Any]) -> Optional[dict[str, Any]]:
    candidatas = [
        parsed for item in ofertas
        if isinstance(item, dict)
        and (parsed := _parse_catalog_offer(produto, item)) is not None
    ]
    if not candidatas:
        return None
    return max(candidatas, key=lambda row: (
        float(row.get("discount_percent") or 0),
        -float(row.get("current_price") or 0),
    ))


def _aplicar_preco_venda(oferta: dict[str, Any],
                         bruto: dict[str, Any]) -> dict[str, Any]:
    """Aplica o preco vigente do endpoint /sale_price sem inventar desconto."""
    atual = _para_float(bruto.get("amount"))
    regular = _para_float(bruto.get("regular_amount"))
    moeda = bruto.get("currency_id") or oferta.get("currency")
    if atual is None or atual <= 0 or moeda != "BRL":
        return oferta

    resultado = dict(oferta)
    resultado["current_price"] = atual
    resultado["currency"] = moeda
    if regular is not None and regular > atual:
        resultado["original_price"] = regular
        resultado["discount_percent"] = round((1 - atual / regular) * 100, 2)
    else:
        original_anterior = _para_float(oferta.get("original_price"))
        if original_anterior is not None and original_anterior > atual:
            resultado["original_price"] = original_anterior
            resultado["discount_percent"] = round(
                (1 - atual / original_anterior) * 100, 2)
        else:
            resultado["original_price"] = None
            resultado["discount_percent"] = None
    resultado["price_source"] = "sale_price"
    return resultado


class MercadoLivreConnector(MarketplaceConnector):
    code = "mercadolivre"

    def __init__(self, access_token: Optional[str] = None) -> None:
        self.access_token = access_token

    def detect_url(self, url: str) -> bool:
        host = urllib.parse.urlparse(url).netloc.lower()
        return ("mercadolivre." in host or "mercadolibre." in host
                or host in SHORTLINK_HOSTS)

    def normalize_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))

    def _external_id(self, url: str) -> Optional[str]:
        """Prioriza o ID do ANÚNCIO sobre o ID de CATÁLOGO: páginas
        .../p/MLB<id> agregam ofertas de vários vendedores pro mesmo
        produto — o item_id/wid (em query ou fragment) identifica a
        oferta específica, que é o que a API /items/ espera. Sem esses
        parâmetros (ex.: permalink direto produto.mercadolivre.com.br/
        MLB-<id>-slug), cai no scan simples da URL inteira."""
        parsed = urllib.parse.urlparse(url)
        for bruto in (parsed.query, parsed.fragment):
            params = urllib.parse.parse_qs(bruto)
            for chave in ("wid", "item_id", "pdp_filters"):
                for valor in params.get(chave, []):
                    match = ITEM_ID_RE.search(valor)
                    if match:
                        return match.group(0).replace("-", "")
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
            bruto = _get_json(f"{API_BASE}/items/{external_id}",
                              access_token=self.access_token)
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
        campos = self.enrich_offer_price(campos)
        campos["category"] = _resolver_categoria(
            bruto.get("category_id"), access_token=self.access_token)

        if not campos["seller_name"] and campos["seller_id"]:
            try:
                user = _get_json(f"{API_BASE}/users/{campos['seller_id']}",
                                 access_token=self.access_token)
                if isinstance(user, dict) and user.get("nickname"):
                    campos["seller_name"] = user["nickname"]
            except urllib.error.URLError:
                pass

        if campos["currency"] not in ("BRL", None):
            campos["aviso"] = (
                f"Anúncio em {campos['currency']} — a API pública do Mercado "
                f"Livre não converte moeda; preço abaixo é o preço local.")
        return campos

    def enrich_offer_price(self, oferta: dict[str, Any]) -> dict[str, Any]:
        """Confirma preco e desconto no endpoint oficial de preco vigente.

        Falhas transitórias ou indisponibilidade para um item preservam os
        dados ja obtidos. Token invalido e tratado como credencial expirada.
        """
        external_id = str(oferta.get("external_product_id") or "").strip()
        if not external_id or not self.access_token:
            return oferta
        try:
            bruto = _get_json(
                f"{API_BASE}/items/{urllib.parse.quote(external_id)}/sale_price?"
                "context=channel_marketplace",
                access_token=self.access_token,
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise CredencialNaoConfigurada(
                    "mercadolivre: token expirado ao consultar preco; "
                    "reconecte a conta em /integracoes") from exc
            if exc.code == 429:
                raise RuntimeError(
                    "Mercado Livre limitou consultas de preco (HTTP 429); "
                    "o worker tentara novamente no proximo ciclo") from exc
            return oferta
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return oferta
        if not isinstance(bruto, dict):
            return oferta
        return _aplicar_preco_venda(oferta, bruto)

    def get_trending_terms(self, *, category_ids: Optional[list[str]] = None,
                           limit: int = 3) -> list[str]:
        """Retorna termos do recurso oficial /trends, com limite pequeno."""
        if limit <= 0:
            return []
        if not self.access_token:
            raise CredencialNaoConfigurada(
                "mercadolivre: conecte a conta para consultar tendencias")
        categorias = category_ids or [""]
        termos: list[str] = []
        vistos: set[str] = set()
        for categoria in categorias:
            categoria = categoria.strip().upper()
            if categoria and not re.fullmatch(r"MLB\d+", categoria):
                continue
            sufixo = f"/{categoria}" if categoria else ""
            try:
                bruto = _get_json(
                    f"{API_BASE}/trends/MLB{sufixo}",
                    access_token=self.access_token,
                )
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    raise CredencialNaoConfigurada(
                        "mercadolivre: token expirado ao consultar tendencias; "
                        "reconecte a conta em /integracoes") from exc
                if exc.code == 429:
                    raise RuntimeError(
                        "Mercado Livre limitou consultas de tendencias "
                        "(HTTP 429); aguarde o proximo ciclo") from exc
                continue
            except (urllib.error.URLError, json.JSONDecodeError, ValueError):
                continue
            if not isinstance(bruto, list):
                continue
            for item in bruto:
                termo = (str(item.get("keyword") or "").strip()
                         if isinstance(item, dict) else "")
                chave = termo.casefold()
                if not termo or chave in vistos:
                    continue
                vistos.add(chave)
                termos.append(termo)
                if len(termos) >= limit:
                    return termos
        return termos

    def predict_domain(self, query: str) -> Optional[dict[str, Any]]:
        """Prediz dominio/categoria para impedir homonimos irrelevantes."""
        termo = query.strip()
        if not termo or not self.access_token:
            return None
        params = urllib.parse.urlencode({"limit": 1, "q": termo})
        try:
            bruto = _get_json(
                f"{API_BASE}/sites/MLB/domain_discovery/search?{params}",
                access_token=self.access_token,
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise CredencialNaoConfigurada(
                    "mercadolivre: token expirado ao prever categoria; "
                    "reconecte a conta em /integracoes") from exc
            if exc.code == 429:
                raise RuntimeError(
                    "Mercado Livre limitou o preditor de categoria (HTTP "
                    "429); aguarde o proximo ciclo") from exc
            return None
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return None
        if not isinstance(bruto, list) or not bruto or not isinstance(bruto[0], dict):
            return None
        previsto = bruto[0]
        domain_id = str(previsto.get("domain_id") or "")
        category_id = str(previsto.get("category_id") or "")
        if not domain_id.startswith("MLB-") or not re.fullmatch(
                r"MLB\d+", category_id):
            return None
        return {
            "domain_id": domain_id,
            "domain_name": previsto.get("domain_name"),
            "category_id": category_id,
            "category_name": previsto.get("category_name"),
        }

    def search_highlights(self, category_ids: list[str], *,
                          limit: int = 5) -> list[dict[str, Any]]:
        """Resolve rankings /highlights em ofertas compraveis verificaveis.

        USER_PRODUCT e ignorado porque pode nao expor uma oferta publica para
        a conta consultante. ITEM e PRODUCT usam apenas endpoints documentados.
        """
        if limit <= 0:
            return []
        if not self.access_token:
            raise CredencialNaoConfigurada(
                "mercadolivre: conecte a conta para consultar mais vendidos")
        encontrados: list[dict[str, Any]] = []
        vistos: set[str] = set()
        por_categoria = max(
            1, (limit + len(category_ids) - 1) // max(1, len(category_ids)))
        for categoria_bruta in category_ids:
            categoria = categoria_bruta.strip().upper()
            if not re.fullmatch(r"MLB\d+", categoria):
                continue
            try:
                ranking = _get_json(
                    f"{API_BASE}/highlights/MLB/category/{categoria}",
                    access_token=self.access_token,
                )
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    raise CredencialNaoConfigurada(
                        "mercadolivre: token expirado ao consultar mais "
                        "vendidos; reconecte a conta em /integracoes") from exc
                if exc.code == 429:
                    raise RuntimeError(
                        "Mercado Livre limitou consultas de mais vendidos "
                        "(HTTP 429); aguarde o proximo ciclo") from exc
                continue
            except (urllib.error.URLError, json.JSONDecodeError, ValueError):
                continue
            conteudo = ranking.get("content") if isinstance(ranking, dict) else None
            if not isinstance(conteudo, list):
                continue
            adicionados_categoria = 0
            for entrada in conteudo:
                if len(encontrados) >= limit:
                    return encontrados
                if adicionados_categoria >= por_categoria:
                    break
                if not isinstance(entrada, dict):
                    continue
                identificador = str(entrada.get("id") or "").strip()
                tipo = str(entrada.get("type") or "").upper()
                posicao = _para_int(entrada.get("position"))
                oferta: Optional[dict[str, Any]] = None
                try:
                    if tipo == "ITEM" and re.fullmatch(r"MLB\d+", identificador):
                        item = _get_json(
                            f"{API_BASE}/items/{identificador}",
                            access_token=self.access_token,
                        )
                        if isinstance(item, dict) and item.get("id"):
                            oferta = _parse_produto_api(item)
                    elif tipo == "PRODUCT" and re.fullmatch(
                            r"MLB\d+", identificador):
                        produto = _get_json(
                            f"{API_BASE}/products/{identificador}",
                            access_token=self.access_token,
                        )
                        itens = _get_json(
                            f"{API_BASE}/products/{identificador}/items",
                            access_token=self.access_token,
                        )
                        resultados = (itens.get("results")
                                      if isinstance(itens, dict) else None)
                        if isinstance(produto, dict) and isinstance(resultados, list):
                            oferta = _melhor_oferta_catalogo(produto, resultados)
                except urllib.error.HTTPError as exc:
                    if exc.code == 401:
                        raise CredencialNaoConfigurada(
                            "mercadolivre: token expirado ao resolver mais "
                            "vendidos; reconecte a conta em /integracoes") from exc
                    if exc.code == 429:
                        raise RuntimeError(
                            "Mercado Livre limitou a resolucao dos mais "
                            "vendidos (HTTP 429); aguarde o proximo ciclo") from exc
                    continue
                except (urllib.error.URLError, json.JSONDecodeError, ValueError):
                    continue
                external_id = (str(oferta.get("external_product_id"))
                               if oferta else "")
                if not oferta or not external_id or external_id in vistos:
                    continue
                vistos.add(external_id)
                oferta["discovery_source"] = "highlights"
                oferta["highlight_category"] = categoria
                oferta["highlight_rank"] = posicao
                encontrados.append(oferta)
                adicionados_categoria += 1
        return encontrados

    def search_offers(self, query: str) -> list[dict[str, Any]]:
        """Descobre anúncios brasileiros pela API oficial de busca.

        A busca exige o token OAuth da organização porque chamadas anônimas
        têm sido recusadas pela API. Ela devolve apenas URLs de produtos
        específicos; não acessa o Portal de Afiliados, não faz scraping e
        não tenta fabricar link comissionado.
        """
        termo = query.strip()
        if not termo:
            return []
        if not self.access_token:
            raise CredencialNaoConfigurada(
                "mercadolivre: conecte novamente sua conta em /integracoes "
                "para descobrir ofertas pela API oficial")

        params = urllib.parse.urlencode({
            "q": termo,
            "sort": "sold_quantity_desc",
            "limit": 50,
        })
        try:
            bruto = _get_json(
                f"{API_BASE}/sites/MLB/search?{params}",
                access_token=self.access_token,
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise CredencialNaoConfigurada(
                    "mercadolivre: token sem acesso à busca ou expirado; "
                    "reconecte a conta em /integracoes") from exc
            if exc.code == 403:
                return self._search_catalog_offers(termo)
            raise RuntimeError(
                f"Mercado Livre recusou a busca de ofertas (HTTP {exc.code})"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Mercado Livre API inacessível durante a busca: {exc}"
            ) from exc

        resultados = bruto.get("results") if isinstance(bruto, dict) else None
        if not isinstance(resultados, list):
            return []

        ofertas: list[dict[str, Any]] = []
        vistos: set[str] = set()
        for item in resultados:
            if not isinstance(item, dict):
                continue
            produto = _parse_produto_api(item)
            external_id = produto.get("external_product_id")
            permalink = produto.get("canonical_url")
            if (not external_id or not permalink or external_id in vistos or
                    produto.get("currency") != "BRL"):
                continue
            vistos.add(external_id)
            produto["discovery_source"] = "search"
            ofertas.append(produto)
        return ofertas

    def _search_catalog_offers(self, query: str) -> list[dict[str, Any]]:
        """Fallback oficial quando a busca de listagens devolve 403.

        Pesquisa cinco produtos no catálogo e escolhe, para cada página de
        produto, a oferta concorrente com maior desconto. O limite pequeno
        contém o volume de chamadas; discovery aplica dedupe e max_novos.
        """
        previsto = self.predict_domain(query)
        filtros = {
            "status": "active", "site_id": "MLB", "q": query, "limit": 10,
        }
        if previsto:
            filtros["domain_id"] = previsto["domain_id"]
        params = urllib.parse.urlencode(filtros)
        try:
            bruto = _get_json(
                f"{API_BASE}/products/search?{params}",
                access_token=self.access_token,
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise CredencialNaoConfigurada(
                    "mercadolivre: token expirado ou inválido; reconecte a "
                    "conta em /integracoes") from exc
            raise RuntimeError(
                f"Mercado Livre recusou a busca no catálogo (HTTP {exc.code})"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Mercado Livre API inacessível durante a busca: {exc}") from exc

        produtos = bruto.get("results") if isinstance(bruto, dict) else None
        if not isinstance(produtos, list):
            return []
        encontrados: list[dict[str, Any]] = []
        vistos: set[str] = set()
        for produto in produtos:
            if len(encontrados) >= 5:
                break
            if not isinstance(produto, dict) or not produto.get("id"):
                continue
            try:
                itens = _get_json(
                    f"{API_BASE}/products/{produto['id']}/items",
                    access_token=self.access_token,
                )
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    raise CredencialNaoConfigurada(
                        "mercadolivre: token expirado ao resolver catalogo; "
                        "reconecte a conta em /integracoes") from exc
                if exc.code == 429:
                    raise RuntimeError(
                        "Mercado Livre limitou a busca no catalogo (HTTP "
                        "429); aguarde o proximo ciclo") from exc
                continue
            except (urllib.error.URLError, json.JSONDecodeError, ValueError):
                continue
            ofertas = itens.get("results") if isinstance(itens, dict) else None
            if not isinstance(ofertas, list):
                continue
            melhor = _melhor_oferta_catalogo(produto, ofertas)
            external_id = melhor.get("external_product_id") if melhor else None
            if melhor and external_id not in vistos:
                vistos.add(str(external_id))
                melhor["discovery_source"] = "catalog_search"
                if previsto:
                    melhor["predicted_category_id"] = previsto["category_id"]
                    melhor["predicted_category_name"] = previsto["category_name"]
                encontrados.append(melhor)
        return encontrados

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
            bruto = _get_json(f"{API_BASE}/items/MLB1",
                              access_token=self.access_token)
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
