"""Topfy Affiliate OS — worker: consome a fila de jobs do Postgres.

Rodar: python -m main (com .env carregado — usar python-dotenv ou
variáveis de ambiente do processo).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

import db
from discovery import capturar_ofertas_mercadolivre
from pipeline import (import_product, generate_affiliate_link, compute_score,
                      generate_copies, montar_copy_text, publish_to_telegram,
                      enviar_mensagem_grupo, regenerate_copies, dispatch_queues,
                      ciclo_automatico, normalizar_product_row,
                      completar_link_mercadolivre_assistido)

POLL_INTERVAL_SECONDS = 5

# Modo 100% automático (capturar -> aprovar -> publicar sem revisão
# humana) — OPT-IN, desligado por padrão. Só roda se as 3 env vars
# abaixo estiverem configuradas; sem elas, comportamento do worker é
# idêntico ao de sempre (nada muda pra quem não ligou isso).
AUTO_PIPELINE_ENABLED = os.environ.get("AUTO_PIPELINE_ENABLED", "").lower() in ("1", "true", "yes")
AUTO_PIPELINE_ORG_ID = os.environ.get("AUTO_PIPELINE_ORG_ID", "")
AUTO_PIPELINE_TERMOS = [t.strip() for t in
                       os.environ.get("AUTO_PIPELINE_TERMOS", "").split(",") if t.strip()]
AUTO_PIPELINE_QUEUE_ID = os.environ.get("AUTO_PIPELINE_QUEUE_ID", "") or None
AUTO_PIPELINE_MIN_SCORE = float(os.environ.get("AUTO_PIPELINE_MIN_SCORE", "60"))
AUTO_PIPELINE_MAX_NOVOS = int(os.environ.get("AUTO_PIPELINE_MAX_NOVOS", "5"))
AUTO_PIPELINE_INTERVAL_MINUTES = int(os.environ.get("AUTO_PIPELINE_INTERVAL_MINUTES", "30"))

_ultimo_ciclo_automatico: Optional[datetime] = None

# Descoberta Mercado Livre via API oficial: captura oportunidades, mas nunca
# publica sem o link gerado pelas ferramentas oficiais do programa afiliado.
ML_DISCOVERY_ENABLED = os.environ.get("ML_DISCOVERY_ENABLED", "").lower() in ("1", "true", "yes")
ML_DISCOVERY_ORG_ID = os.environ.get("ML_DISCOVERY_ORG_ID", "") or AUTO_PIPELINE_ORG_ID
ML_DISCOVERY_TERMOS = [t.strip() for t in
                      os.environ.get("ML_DISCOVERY_TERMOS", "").split(",") if t.strip()]
ML_DISCOVERY_MIN_DISCOUNT = float(os.environ.get("ML_DISCOVERY_MIN_DISCOUNT", "5"))
ML_DISCOVERY_MAX_NOVOS = int(os.environ.get("ML_DISCOVERY_MAX_NOVOS", "10"))
ML_DISCOVERY_INTERVAL_MINUTES = int(os.environ.get("ML_DISCOVERY_INTERVAL_MINUTES", "60"))

_ultima_descoberta_ml: Optional[datetime] = None


def rodar_ciclo_automatico_se_configurado(*, now: Optional[datetime] = None) -> None:
    """Roda o modo 100% automático no próprio ritmo (AUTO_PIPELINE_
    INTERVAL_MINUTES, não a cada poll de 5s) — chamado a cada volta do
    run_forever. Sem AUTO_PIPELINE_ENABLED/ORG_ID/TERMOS configurados,
    não faz nada (opt-in real, sem default)."""
    global _ultimo_ciclo_automatico
    if not (AUTO_PIPELINE_ENABLED and AUTO_PIPELINE_ORG_ID and AUTO_PIPELINE_TERMOS):
        return
    agora = now or datetime.now(timezone.utc)
    if (_ultimo_ciclo_automatico is not None and
            (agora - _ultimo_ciclo_automatico).total_seconds() <
            AUTO_PIPELINE_INTERVAL_MINUTES * 60):
        return
    _ultimo_ciclo_automatico = agora
    try:
        resultado = ciclo_automatico(
            AUTO_PIPELINE_ORG_ID, termos=AUTO_PIPELINE_TERMOS,
            min_score=AUTO_PIPELINE_MIN_SCORE,
            max_novos=AUTO_PIPELINE_MAX_NOVOS,
            queue_id=AUTO_PIPELINE_QUEUE_ID)
        if resultado["total"]:
            print(f"[worker] modo automatico: {resultado['total']} "
                  f"campanha(s) capturada(s) e aprovada(s) sozinha(s)")
    except Exception as exc:  # nunca derruba o loop principal
        print(f"[worker] erro no ciclo automatico: {exc}", file=sys.stderr)


def rodar_descoberta_ml_se_configurada(*, now: Optional[datetime] = None) -> None:
    """Executa a descoberta MLB no intervalo configurado, sem publicação."""
    global _ultima_descoberta_ml
    if not (ML_DISCOVERY_ENABLED and ML_DISCOVERY_ORG_ID and ML_DISCOVERY_TERMOS):
        return
    agora = now or datetime.now(timezone.utc)
    if (_ultima_descoberta_ml is not None and
            (agora - _ultima_descoberta_ml).total_seconds() <
            ML_DISCOVERY_INTERVAL_MINUTES * 60):
        return
    _ultima_descoberta_ml = agora
    try:
        resultado = capturar_ofertas_mercadolivre(
            ML_DISCOVERY_ORG_ID,
            termos=ML_DISCOVERY_TERMOS,
            min_discount_pct=ML_DISCOVERY_MIN_DISCOUNT,
            max_novos=ML_DISCOVERY_MAX_NOVOS,
        )
        if resultado["total"]:
            print(f"[worker] Mercado Livre: {resultado['total']} "
                  "oferta(s) capturada(s), aguardando link oficial")
    except Exception as exc:
        print(f"[worker] erro na descoberta Mercado Livre: {exc}",
              file=sys.stderr)


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

        row = import_product(payload["source_name"], payload["url"],
                             organization_id=org)
        db._get().table("products").update(row).eq("id", product_id).execute()
        db.register_audit(org, actor_type="worker", action="produto_importado",
                          entity_type="product", entity_id=str(product_id),
                          metadata={"source_name": payload["source_name"]})

        link = generate_affiliate_link(payload["source_name"], payload["url"])
        db._get().table("products").update({
            "affiliate_link": link.get("affiliate_url"),
            "affiliate_link_status": link.get("verification_status", "UNKNOWN"),
        }).eq("id", product_id).execute()

        product_row = normalizar_product_row(db.get_product(str(product_id)))
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

    elif tipo == "mercadolivre.link.ready":
        campaign_id = payload.get("campaign_id")
        affiliate_url = payload.get("affiliate_url")
        if not campaign_id or not affiliate_url:
            raise ValueError(
                "job mercadolivre.link.ready precisa de campaign_id e affiliate_url")
        completar_link_mercadolivre_assistido(
            campaign_id,
            affiliate_url,
            official_tool_confirmed=bool(payload.get("official_tool_confirmed")),
            auto_approve=bool(payload.get("auto_approve")),
            queue_id=payload.get("queue_id") or None,
        )

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
        rodar_ciclo_automatico_se_configurado()
        rodar_descoberta_ml_se_configurada()
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
