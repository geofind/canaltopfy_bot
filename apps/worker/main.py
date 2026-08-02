"""Topfy Affiliate OS — worker: consome a fila de jobs do Postgres.

Rodar: python -m main (com .env carregado — usar python-dotenv ou
variáveis de ambiente do processo).
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

import db
from pipeline import (import_product, generate_affiliate_link, compute_score,
                      generate_copies, montar_copy_text, publish_to_telegram,
                      enviar_mensagem_grupo, regenerate_copies, dispatch_queues)

POLL_INTERVAL_SECONDS = 5


def process_job(job: dict[str, Any]) -> None:
    payload = job.get("payload") or {}
    tipo = job.get("type", "")
    org = job.get("organization_id")

    if tipo == "product.import":
        product_id = payload.get("product_id")
        campaign_id = payload.get("campaign_id")
        if not product_id or not campaign_id:
            raise ValueError(
                "job product.import sem product_id/campaign_id — precisa "
                "ser criado por createCampaignFromUrl (web)")

        row = import_product(payload["source_name"], payload["url"])
        db._get().table("products").update(row).eq("id", product_id).execute()
        db.register_audit(org, actor_type="worker", action="produto_importado",
                          entity_type="product", entity_id=str(product_id),
                          metadata={"source_name": payload["source_name"]})

        link = generate_affiliate_link(payload["source_name"], payload["url"])
        db._get().table("products").update({
            "affiliate_link": link.get("affiliate_url"),
            "affiliate_link_status": link.get("verification_status", "UNKNOWN"),
        }).eq("id", product_id).execute()

        product_row = db.get_product(str(product_id))
        score = compute_score(product_row, link)
        db._get().table("products").update({
            "score": score["score_total"],
            "score_breakdown": {
                k: v for k, v in score.items()
                if k not in ("score_total", "reason_summary", "warnings", "bloqueios")
            },
            "status": "READY",
        }).eq("id", product_id).execute()

        db._get().table("campaigns").update({
            "status": "READY",
            "title": product_row.get("title"),
        }).eq("id", campaign_id).execute()
        db.register_audit(org, actor_type="worker", action="campanha_atualizada",
                          entity_type="campaign", entity_id=str(campaign_id))

        copias = generate_copies(product_row)
        for copia in copias:
            validation_errors = copia.pop("validation_errors", None)
            db._get().table("contents").insert({
                "campaign_id": campaign_id,
                "version": 1,
                "status": "DRAFT" if validation_errors else "PENDING_REVIEW",
                "provider": copia.pop("provider", "fallback"),
                "model": copia.pop("model", None),
                "copy_text": montar_copy_text(copia),
                "hooks": [],
                "compliance": {"validation_errors": validation_errors or []},
            }).execute()
        db.update_campaign(campaign_id, {"status": "CONTENT_GENERATING"})
        db.register_audit(org, actor_type="worker", action="copies_geradas",
                          entity_type="campaign", entity_id=str(campaign_id),
                          metadata={"total": len(copias)})

    elif tipo == "publication.telegram":
        resultado = publish_to_telegram(
            payload["campaign_id"], payload["content_id"],
            payload.get("chat_id", ""), payload.get("group_id"))
        db.register_audit(org, actor_type="worker", action="publicacao_telegram",
                          entity_type="publication",
                          entity_id=str(resultado["publication_id"]),
                          metadata=resultado)

    elif tipo == "telegram.send":
        group_id = payload.get("group_id")
        text = payload.get("text", "")
        if not group_id or not text:
            raise ValueError(
                "job telegram.send precisa de group_id e text no payload")
        resultado = enviar_mensagem_grupo(group_id, text)
        db.register_audit(org, actor_type="user", action="telegram_mensagem_livre",
                          entity_type="channel_group", entity_id=str(group_id),
                          metadata=resultado)

    elif tipo == "content.regenerate":
        campaign_id = payload.get("campaign_id")
        if not campaign_id:
            raise ValueError("job content.regenerate sem campaign_id")
        resultado = regenerate_copies(campaign_id)
        db.register_audit(org, actor_type="user", action="copies_regeneradas",
                          entity_type="campaign", entity_id=str(campaign_id),
                          metadata=resultado)

    else:
        raise ValueError(f"tipo de job desconhecido: {tipo}")


def run_forever() -> None:
    while True:
        try:
            despachados = dispatch_queues()
            if despachados:
                print(f"[worker] filas: {len(despachados)} item(ns) despachado(s)")
        except Exception as exc:  # filas: nunca derruba o loop
            print(f"[worker] erro ao despachar filas: {exc}", file=sys.stderr)
        try:
            job = db.get_next_job()
        except Exception as exc:  # rede/credencial — continua tentando
            print(f"[worker] erro ao buscar job: {exc}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            process_job(job)
            db.finish_job(job["id"], ok=True)
            print(f"[worker] job {job['id']} ({job['type']}) concluído")
        except Exception as exc:
            db.finish_job(job["id"], ok=False, error=str(exc))
            print(f"[worker] job {job['id']} ({job['type']}) FALHOU: {exc}",
                  file=sys.stderr)


def run_once(max_jobs: int = 1) -> list[dict[str, Any]]:
    """Processa até max_jobs da fila e volta — útil para testes/cron."""
    processados = []
    for _ in range(max_jobs):
        job = db.get_next_job()
        if not job:
            break
        try:
            process_job(job)
            db.finish_job(job["id"], ok=True)
            processados.append({"id": job["id"], "type": job["type"], "ok": True})
        except Exception as exc:
            db.finish_job(job["id"], ok=False, error=str(exc))
            processados.append({"id": job["id"], "type": job["type"], "ok": False,
                                "error": str(exc)})
    return processados


if __name__ == "__main__":
    run_forever()
