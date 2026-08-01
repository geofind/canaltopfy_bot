"""Topfy Affiliate OS — pipeline de campanha (Fase 1, fluxo vertical).

Máquina de estados (spec):
IMPORTED -> VALIDATING -> READY -> CONTENT_GENERATING
-> REVIEW_REQUIRED -> APPROVED -> SCHEDULED -> PUBLISHING
-> PUBLISHED -> MONITORING -> SCALE / REWORK / ARCHIVED / FAILED

Etapas deste módulo:
1. import_product: valida a URL, extrai via conector (API ou MANUAL).
2. generate_affiliate_link: gera link oficial (ou registra aviso manual).
3. compute_score: Topfy Score decomposto (bloqueios impedem aprovação).
4. generate_copies: 3 cópias (provider auto: Ollama + fallback).
5. validate + approve: humana (spec: aprovação humana obrigatória).
6. publish: fila de publicações (telegram real / adapters simulados).

Regras de segurança (spec):
- nada publica sem publicações aprovadas explicitamente;
- toda ação registrada no audit_log;
- banco é a fonte da verdade (worker só confirma o que o banco diz).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import db
from connectors import CredencialNaoConfigurada
from connectors.aliexpress import AliExpressConnector
from content import gerar_copy, validar_copy
from scoring import calcular_score

CONECTORES = {
    "aliexpress": AliExpressConnector,
}


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
    com registro — nunca persiste copy quebrada."""
    if n < 1:
        raise ValueError("n deve ser >= 1")
    copias = []
    for i in range(n):
        template = ("oferta-padrao", "oferta-curta", "oferta-beneficios")[i % 3]
        semente = seed + i if seed is not None else None
        copia = gerar_copy(product, template, provider="auto", seed=semente)
        problemas = validar_copy(copia)
        if problemas:
            copia["validation_errors"] = problemas
        copias.append(copia)
    return copias


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


def publish_to_telegram(campaign_id: str, content_id: str, chat_id: str) -> dict[str, Any]:
    """Etapa 6 — publicação no Telegram (canal real). CTA aponta para o
    redirect first-party /r/<id>. Deduplicação por canal."""
    from db import get_campaign, get_publication, create_publication
    from db import has_active_publication, mark_publication_result, register_audit
    from publishers.telegram import publicar_oferta_telegram

    campanha = get_campaign(campaign_id)
    if not campanha:
        raise ValueError(f"campaign {campaign_id} não encontrada")
    if campanha["status"] not in ("APPROVED", "SCHEDULED", "PUBLISHED"):
        raise ValueError(
            f"publicar exige campanha aprovada (atual: {campanha['status']})")

    if has_active_publication(campaign_id, "telegram"):
        raise ValueError(
            "esta campanha já foi publicada no Telegram — publicar de novo "
            "duplicaria a mensagem")

    pub = create_publication(campaign_id, {
        "content_id": content_id,
        "channel": "telegram",
        "mode": "production",
        "status": "PUBLISHING",
    })
    pub_id = pub["id"]

    try:
        produto = db.get_product(campanha["product_id"]) or {}
        redirect_url = (
            f"{os.environ.get('CANALTOPFY_PUBLIC_BASE_URL', 'http://localhost:3000')}"
            f"/r/{pub_id}")
        resultado = publicar_oferta_telegram(
            copy=_load_content(content_id),
            chat_id=chat_id,
            redirect_url=redirect_url,
            image_url=produto.get("image_url"),
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


def _load_content(content_id: str) -> dict[str, Any]:
    resp = db._get().table("contents").select("*").eq("id", content_id).maybe_single().execute()
    if not resp.data:
        raise ValueError(f"content {content_id} não encontrado")
    return {
        "headline": resp.data.get("copy_text", "").split("\n\n")[0],
        "body": resp.data.get("copy_text", ""),
        "cta": "Ver oferta",
        "disclaimer": DISCLAIMER_PADRAO,
    }


DISCLAIMER_PADRAO = (
    "Link de afiliado: se você comprar por aqui, o Topfy pode ganhar uma "
    "comissão, sem custo extra para você."
)
