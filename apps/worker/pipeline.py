"""Topfy Affiliate OS — pipeline de campanha (Fase 1, fluxo vertical).

Máquina de estados (spec):
IMPORTED -> VALIDATING -> READY -> CONTENT_GENERATING
-> REVIEW_REQUIRED -> APPROVED -> SCHEDULED -> PUBLISHING
-> PUBLISHED -> MONITORING -> SCALE / REWORK / ARCHIVED / FAILED

Etapas deste módulo:
1. import_product: valida a URL, extrai via conector (API ou MANUAL).
2. generate_affiliate_link: gera link oficial (ou registra aviso manual).
3. compute_score: Topfy Score decomposto (bloqueios impedem aprovação).
4. generate_copies: 3 cópias (provider auto: OpenRouter + fallback).
5. validate + approve: humana (spec: aprovação humana obrigatória).
6. publish: fila de publicações (telegram real / adapters simulados).

Regras de segurança (spec):
- nada publica sem publicações aprovadas explicitamente;
- toda ação registrada no audit_log;
- banco é a fonte da verdade (worker só confirma o que o banco diz).
"""
from __future__ import annotations

import html.parser
import os
import random
import urllib.error
import urllib.request
from datetime import datetime, time, timezone, timedelta
from typing import Any, Optional
from urllib.parse import quote

import db
from connectors import CredencialNaoConfigurada
from connectors.aliexpress import AliExpressConnector
from connectors.amazon import AmazonConnector
from connectors.mercadolivre import MercadoLivreConnector
from content import gerar_copy, validar_copy
from scoring import calcular_score

CONECTORES = {
    "aliexpress": AliExpressConnector,
    "amazon": AmazonConnector,
    "mercadolivre": MercadoLivreConnector,
}

CTA_PADRAO = ("Ver oferta", "Conferir na loja", "Ver oferta na loja")

MAX_QUEUE_ATTEMPTS = 3


def get_connector(source_name: str):
    cls = CONECTORES.get(source_name)
    if cls is None:
        raise ValueError(
            f"Conector não implementado: {source_name} "
            f"(disponíveis: {', '.join(sorted(CONECTORES))})")
    return cls()


def import_product(source_name: str, url: str) -> dict[str, Any]:
    """Etapa 1 — IMPORTED -> VALIDATING -> READY.

    Extrai o produto via conector (API oficial quando há credencial;
    caso contrário MANUAL com aviso). Devolve o payload que vai para a
    tabela products — nunca inventa campo."""
    conector = get_connector(source_name)
    if not conector.detect_url(url):
        raise ValueError(f"URL não pertence a {source_name}: {url}")
    produto = conector.get_product(url)

    campo_map = {
        "external_product_id": "external_id",
        "canonical_url": "source_url",
        "title": "title",
        "main_image_url": "image_url",
        "category": "category",
        "seller_name": "seller",
        "current_price": "discounted_price_brl",
        "original_price": "original_price_brl",
        "discount_percent": "discount_pct",
        "commission_percent": "commission_pct",
        "sold_count": "sales_count",
        "positive_feedback_percent": None,  # usado pelo score, não persiste
        "currency": "currency",
    }

    row = {
        "source_name": source_name,
        "source_url": produto.get("canonical_url") or url,
        "method": produto.get("method", "MANUAL"),
        "confidence": produto.get("source_confidence", "UNKNOWN"),
        "status": "READY" if produto.get("method") == "API" else "IMPORTED",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    for origem, destino in campo_map.items():
        if destino and produto.get(origem) is not None:
            row[destino] = produto[origem]

    if not row.get("title"):
        # título é not null na tabela — quando o conector não devolve
        # nenhum (API recusou/product_id não encontrado), usa um rótulo
        # honesto em vez de inventar ou deixar o placeholder "Importando
        # produto…" parado pra sempre.
        identificador = row.get("external_id") or "sem ID"
        row["title"] = f"Produto {identificador} — dados indisponíveis"

    if produto.get("aviso"):
        row["aviso"] = produto["aviso"]
    return row


def generate_affiliate_link(source_name: str, product_url: str) -> dict[str, Any]:
    """Etapa 2 — gera o link de afiliado via API oficial; em modo manual
    devolve status UNKNOWN (nunca VERIFIED sem evidência)."""
    conector = get_connector(source_name)
    try:
        return conector.generate_affiliate_link(product_url)
    except CredencialNaoConfigurada as exc:
        return {
            "affiliate_url": None,
            "generation_method": "MANUAL",
            "verification_status": "UNKNOWN",
            "erro": str(exc),
        }


def compute_score(product: dict[str, Any],
                  affiliate_link: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Etapa 3 — Topfy Score decomposto. `product` usa os campos do schema
    do banco; o score lê também positive_feedback_percent quando presente."""
    return calcular_score(product, affiliate_link)


def generate_copies(product: dict[str, Any], *,
                    n: int = 3, seed: Optional[int] = None) -> list[dict[str, Any]]:
    """Etapa 4 — gera n cópias (3 no padrão) com variações de template.
    Cada cópia é validada por validar_copy; cópias inválidas são descartadas
    com registro — nunca persiste copy quebrada. Textos contextualizados
    pela loja de origem (product.source_name)."""
    if n < 1:
        raise ValueError("n deve ser >= 1")
    copias = []
    for i in range(n):
        template = ("oferta-padrao", "oferta-curta", "oferta-beneficios")[i % 3]
        semente = seed + i if seed is not None else None
        copia = gerar_copy(product, template, provider="auto", seed=semente,
                           loja=product.get("source_name"))
        problemas = validar_copy(copia)
        if problemas:
            copia["validation_errors"] = problemas
        copias.append(copia)
    return copias


def montar_copy_text(copia: dict[str, Any]) -> str:
    """Texto completo persistido em contents.copy_text (headline, corpo,
    CTA e disclaimer separados por linha em branco)."""
    return (f"{copia.get('headline', '')}\n\n{copia.get('body', '')}\n\n"
            f"{copia.get('cta', 'Ver oferta')}\n\n{copia.get('disclaimer', '')}")


class _MetaOgp(html.parser.HTMLParser):
    """Extrai og:image / twitter:image do HTML — sem dependências."""

    def __init__(self) -> None:
        super().__init__()
        self.imagem: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag != "meta" or self.imagem:
            return
        d = dict(attrs)
        prop = d.get("property") or d.get("name") or ""
        if prop in ("og:image", "twitter:image") and d.get("content"):
            self.imagem = d["content"]


def extrair_og_image(url: str, *, timeout: int = 15) -> Optional[str]:
    """Best-effort: lê a página pública da loja e devolve a URL da imagem
    real do produto (meta og:image). 1 GET com timeout curto; NUNCA levanta
    exceção (falha silenciosa = sem imagem). Só captura a imagem — nunca
    preço/dados (isso continua via API oficial ou manual)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0 Safari/537.36"),
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            html = resp.read(500_000).decode(charset, errors="replace")
        parser = _MetaOgp()
        parser.feed(html)
        if parser.imagem and parser.imagem.startswith("http"):
            return parser.imagem
        return None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None


def imagem_para_post(produto: dict[str, Any]) -> Optional[str]:
    """Imagem REAL do produto para compor o card do post — sem banco de
    imagens: usa a image_url já gravada se houver; senão captura og:image
    da página pública da loja NA HORA da publicação (best-effort)."""
    atual = (produto.get("image_url") or "").strip()
    if atual:
        return atual
    source_url = (produto.get("source_url") or "").strip()
    if not source_url:
        return None
    return extrair_og_image(source_url)


def sortear_cta(organization_id: Optional[str], *,
                seed: Optional[int] = None) -> str:
    """Sorteia um gatilho/CTA das frases cadastradas da org (tabela
    cta_phrases); sem nenhuma cadastrada, usa os 3 padrão (Fase A)."""
    frases = [f["phrase"] for f in db.get_cta_phrases(organization_id)] if organization_id else []
    candidatas = frases if frases else list(CTA_PADRAO)
    return random.Random(seed).choice(candidatas)


def approve_campaign(campaign_id: str, content_ids: list[str]) -> None:
    """Etapa 5 — aprovação humana (spec: aprovação humana obrigatória).
    Marca a campanha APPROVED e os conteúdos escolhidos APPROVED; os
    demais ficam REJECTED."""
    db.update_campaign(campaign_id, {"status": "APPROVED"})
    for content_id in content_ids:
        db._get().table("contents").update({"status": "APPROVED"}).eq("id", content_id).execute()
    db.register_audit(
        db.get_campaign(campaign_id).get("organization_id"),
        actor_type="user", action="campaign_aprovada",
        entity_type="campaign", entity_id=campaign_id)


def publish_to_telegram(campaign_id: str, content_id: str,
                        chat_id: str = "",
                        group_id: Optional[str] = None) -> dict[str, Any]:
    """Etapa 6 — publicação no Telegram (canal real). CTA aponta para o
    redirect first-party /r/<id>. Deduplicação por canal E grupo
    (publications.chat_id). `chat_id` vazio usa TELEGRAM_CHAT_ID (grupo
    padrão); `group_id` resolve o chat de um grupo cadastrado e tem
    precedência sobre chat_id. O CTA da mensagem é sorteado das frases
    cadastradas (sortear_cta)."""
    from db import get_campaign, get_publication, create_publication
    from db import has_active_publication, mark_publication_result, register_audit
    from publishers.telegram import publicar_oferta_telegram

    chat_destino = chat_id or ""
    if group_id:
        grupo = db.get_channel_group(group_id)
        if not grupo:
            raise ValueError(f"grupo {group_id} não encontrado")
        chat_destino = grupo["telegram_chat_id"] or ""
    if not chat_destino:
        chat_destino = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat_destino:
        raise ValueError(
            "publicar no Telegram exige um grupo cadastrado (group_id), "
            "chat_id ou TELEGRAM_CHAT_ID no .env")

    campanha = get_campaign(campaign_id)
    if not campanha:
        raise ValueError(f"campaign {campaign_id} não encontrada")
    if campanha["status"] not in ("APPROVED", "SCHEDULED", "PUBLISHED"):
        raise ValueError(
            f"publicar exige campanha aprovada (atual: {campanha['status']})")

    if has_active_publication(campaign_id, "telegram", chat_id=chat_destino):
        raise ValueError(
            "esta campanha já foi publicada neste grupo — publicar de novo "
            "duplicaria a mensagem")

    pub = create_publication(campaign_id, {
        "content_id": content_id,
        "channel": "telegram",
        "mode": "production",
        "status": "PUBLISHING",
        "chat_id": chat_destino,
    })
    pub_id = pub["id"]

    try:
        base_url = os.environ.get(
            "CANALTOPFY_PUBLIC_BASE_URL", "http://localhost:3000")
        redirect_url = f"{base_url}/r/{pub_id}"
        card_url = f"{base_url}/og/card/{campaign_id}"
        produto = db.get_product(campanha["product_id"])
        if produto:
            imagem = imagem_para_post(produto)
            if imagem:
                card_url += f"?img={quote(imagem, safe='')}"
        copy = _load_content(content_id)
        copy["cta"] = sortear_cta(campanha.get("organization_id"))
        resultado = publicar_oferta_telegram(
            copy=copy,
            chat_id=chat_destino,
            redirect_url=redirect_url,
            image_url=card_url,
        )
    except Exception as exc:
        mark_publication_result(pub_id, {"status": "FAILED", "error": str(exc)})
        register_audit(
            campanha.get("organization_id"), actor_type="worker",
            action="publicacao_telegram_falhou", entity_type="publication",
            entity_id=str(pub_id), metadata={"error": str(exc)})
        raise

    mark_publication_result(pub_id, {
        "status": "PUBLISHED",
        "external_id": resultado["external_message_id"],
        "published_at": datetime.now(timezone.utc).isoformat(),
    })
    db.update_campaign(campaign_id, {"status": "PUBLISHED"})
    register_audit(
        campanha.get("organization_id"), actor_type="worker",
        action="publicacao_telegram_ok", entity_type="publication",
        entity_id=str(pub_id), metadata=resultado)
    return {"publication_id": pub_id, **resultado}


def enviar_mensagem_telegram(chat_id: str, text: str) -> dict[str, Any]:
    """Modo send: mensagem de texto livre para um chat (sem publication)."""
    from publishers.telegram import enviar_mensagem_telegram as enviar
    return enviar(chat_id=chat_id, text=text)


def enviar_mensagem_grupo(group_id: str, text: str) -> dict[str, Any]:
    """Modo send: mensagem livre para um grupo cadastrado."""
    grupo = db.get_channel_group(group_id)
    if not grupo:
        raise ValueError(f"grupo {group_id} não encontrado")
    return enviar_mensagem_telegram(grupo["telegram_chat_id"], text)


def regenerate_copies(campaign_id: str, *,
                      seed: Optional[int] = None) -> dict[str, Any]:
    """Gera um novo ciclo de cópias com contexto (fatos reais do produto)
    e variação aleatória (seed nova). Revoga aprovações antigas — nenhuma
    publicação usa copy velha depois de regenerar. Campanha volta para
    REVIEW_REQUIRED (aprovação humana continua obrigatória)."""
    campanha = db.get_campaign(campaign_id)
    if not campanha:
        raise ValueError(f"campaign {campaign_id} não encontrada")
    produto = db.get_product(campanha["product_id"])
    if not produto:
        raise ValueError("campanha sem produto — não dá para gerar textos")

    resp = (db._get().table("contents").select("version")
            .eq("campaign_id", campaign_id)
            .order("version", desc=True).limit(1).execute())
    versao = (resp.data[0]["version"] if resp.data else 0) + 1

    db._get().table("contents").update({"status": "REJECTED"}) \
        .eq("campaign_id", campaign_id).neq("status", "PUBLISHED").execute()

    copias = generate_copies(produto, seed=seed)
    for copia in copias:
        validation_errors = copia.pop("validation_errors", None)
        db._get().table("contents").insert({
            "campaign_id": campaign_id,
            "version": versao,
            "status": "DRAFT" if validation_errors else "PENDING_REVIEW",
            "provider": copia.pop("provider", "fallback"),
            "model": copia.pop("model", None),
            "copy_text": montar_copy_text(copia),
            "hooks": [],
            "compliance": {
                "validation_errors": validation_errors or [],
                "regenerated": True,
            },
        }).execute()

    db.update_campaign(campaign_id, {"status": "REVIEW_REQUIRED"})
    db.register_audit(
        campanha.get("organization_id"), actor_type="user",
        action="copies_regeneradas", entity_type="campaign",
        entity_id=campaign_id,
        metadata={"total": len(copias), "version": versao})
    return {"total": len(copias), "version": versao}


def dispatch_queues(*, now: Optional[datetime] = None,
                    max_items_per_cycle: int = 10) -> list[dict[str, Any]]:
    """Despacha as filas ativas: respeita janela diária (window_start/
    window_end) e intervalo mínimo (interval_minutes) entre envios; publica
    cada item em todos os grupos da fila. Devolve resumo do ciclo.

    Um item por fila por ciclo (poll de 5s); sem lock — o worker roda com
    uma réplica. Falha volta o item para PENDING (attempts+1) até
    MAX_QUEUE_ATTEMPTS; depois CANCELLED."""
    agora = now or datetime.now(timezone.utc)
    despachados = []
    for fila in db.get_active_queues():
        if not _janela_ativa(fila, agora):
            continue
        intervalo_min = (fila.get("interval_minutes") or 5) * 60
        ultimo = db.get_last_dispatched_at(fila["id"])
        if ultimo:
            if (agora - _parse_iso(ultimo)).total_seconds() < intervalo_min:
                continue
        itens = db.get_pending_queue_items(fila["id"], agora.isoformat(),
                                           limit=max_items_per_cycle)
        grupos = db.get_queue_groups(fila["id"])
        if not itens or not grupos:
            continue
        item = itens[0]
        if not item.get("content_id"):
            db.mark_queue_item(item["id"], {
                "status": "CANCELLED", "error": "item sem content_id"})
            continue
        db.mark_queue_item(item["id"], {
            "status": "DISPATCHED", "dispatched_at": agora.isoformat()})
        falhas: list[str] = []
        for grupo in grupos:
            try:
                publish_to_telegram(item["campaign_id"], item["content_id"],
                                    group_id=grupo["group_id"])
            except ValueError as exc:
                if "já foi publicada" in str(exc):
                    continue
                falhas.append(str(exc))
            except Exception as exc:  # rede/telegram
                falhas.append(str(exc))
        if falhas:
            tentativas = (item.get("attempts") or 0) + 1
            db.mark_queue_item(item["id"], {
                "status": "PENDING" if tentativas < MAX_QUEUE_ATTEMPTS else "CANCELLED",
                "attempts": tentativas,
                "error": "; ".join(falhas)[:500],
            })
        else:
            db.mark_queue_item(item["id"], {
                "status": "DONE", "published_at": agora.isoformat()})
            despachados.append({
                "queue_id": fila["id"], "item_id": item["id"],
                "groups": len(grupos)})
    return despachados


def _janela_ativa(fila: dict[str, Any], momento: datetime) -> bool:
    inicio = fila.get("window_start")
    fim = fila.get("window_end")
    if not inicio or not fim:
        return True
    # window_start/window_end são horários de Brasília (America/Sao_Paulo,
    # UTC-3 fixo desde 2019). Importante: momento chega sem timezone quando
    # vem de um local, então assumimos UTC e convertemos.
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    hora = momento.astimezone(timezone(timedelta(hours=-3))).time()
    i, f = time.fromisoformat(str(inicio)), time.fromisoformat(str(fim))
    if i <= f:
        return i <= hora < f
    return hora >= i or hora < f


def _parse_iso(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _load_content(content_id: str) -> dict[str, Any]:
    resp = db._get().table("contents").select("*").eq("id", content_id).maybe_single().execute()
    if not resp.data:
        raise ValueError(f"content {content_id} não encontrado")
    partes = (resp.data.get("copy_text") or "").split("\n\n")
    headline = partes[0] if partes else ""
    if len(partes) >= 4:  # headline / body / cta / disclaimer
        body = "\n\n".join(partes[1:-2])
    else:
        body = resp.data.get("copy_text", "")
    return {
        "headline": headline,
        "body": body,
        "cta": "",
        "disclaimer": "",
    }


DISCLAIMER_PADRAO = (
    "Link de afiliado: se você comprar por aqui, o Topfy pode ganhar uma "
    "comissão, sem custo extra para você."
)
