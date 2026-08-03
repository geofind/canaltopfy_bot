"""Topfy Affiliate OS — acesso ao banco (Supabase PostgREST).

Worker usa a service_role key para escrita (máquina de estados e jobs);
leitura de dados externos respeita os campos obrigatórios do princípio de
dados (source_name, source_url, collected_at, method, confidence, status,
external_id).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import create_client, Client


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórios para o worker.")
    return create_client(url, key)


def _get() -> Client:
    client = getattr(_get, "_client", None)
    if client is None:
        client = get_client()
        _get._client = client
    return client


def get_product(product_id: str) -> Optional[dict[str, Any]]:
    resp = _get().table("products").select("*").eq("id", product_id).maybe_single().execute()
    return resp.data


def update_product(product_id: str, fields: dict[str, Any]) -> None:
    _get().table("products").update(fields).eq("id", product_id).execute()


def get_ml_access_token(organization_id: str) -> Optional[str]:
    """access_token do Mercado Livre já conectado pela org (ml_credentials),
    só se ainda não tiver expirado — sem refresh (este app do ML não emite
    refresh_token confiável; expirado exige reconectar em /integracoes)."""
    resp = (_get().table("ml_credentials").select("access_token, expires_at")
            .eq("organization_id", organization_id).maybe_single().execute())
    if not resp.data:
        return None
    expira = resp.data.get("expires_at")
    if expira:
        venceu = datetime.fromisoformat(expira.replace("Z", "+00:00"))
        if venceu <= datetime.now(timezone.utc):
            return None
    return resp.data.get("access_token")


def get_campaign(campaign_id: str) -> Optional[dict[str, Any]]:
    resp = _get().table("campaigns").select("*").eq("id", campaign_id).maybe_single().execute()
    return resp.data


def update_campaign(campaign_id: str, fields: dict[str, Any]) -> None:
    _get().table("campaigns").update(fields).eq("id", campaign_id).execute()


def get_campaign_contents(campaign_id: str) -> list[dict[str, Any]]:
    resp = _get().table("contents").select("*").eq("campaign_id", campaign_id).execute()
    return resp.data or []


def create_content(campaign_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    resp = _get().table("contents").insert({**fields, "campaign_id": campaign_id}).execute()
    return resp.data[0]


def get_publication(publication_id: str) -> Optional[dict[str, Any]]:
    resp = _get().table("publications").select("*").eq("id", publication_id).maybe_single().execute()
    return resp.data


def has_active_publication(campaign_id: str, channel: str,
                           chat_id: Optional[str] = None) -> bool:
    """Deduplicação: existe publicação não-falha da campanha neste canal?
    Com `chat_id`, a dedup é por canal E grupo — permite publicar a mesma
    campanha em vários grupos, mas nunca duas vezes no mesmo."""
    query = (_get().table("publications")
             .select("id").eq("campaign_id", campaign_id).eq("channel", channel)
             .neq("status", "FAILED").neq("status", "CANCELLED"))
    if chat_id:
        query = query.eq("chat_id", chat_id)
    resp = query.execute()
    return bool(resp.data)


def create_publication(campaign_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    resp = _get().table("publications").insert({**fields, "campaign_id": campaign_id}).execute()
    return resp.data[0]


def mark_publication_result(publication_id: str, fields: dict[str, Any]) -> None:
    _get().table("publications").update(fields).eq("id", publication_id).execute()


def get_next_job() -> Optional[dict[str, Any]]:
    resp = (_get().table("jobs")
            .select("*")
            .eq("status", "pending")
            .lte("scheduled_for", "now()")
            .order("created_at")
            .limit(1).execute())
    if not resp.data:
        return None
    job = resp.data[0]
    _get().table("jobs").update({"status": "running", "started_at": "now()"}).eq("id", job["id"]).execute()
    return job


def finish_job(job_id: int, *, ok: bool, error: Optional[str] = None) -> None:
    fields: dict[str, Any] = {
        "status": "done" if ok else "failed",
        "finished_at": "now()",
    }
    if error:
        fields["error"] = error
    _get().table("jobs").update(fields).eq("id", job_id).execute()


def get_channel_group(group_id: str) -> Optional[dict[str, Any]]:
    resp = (_get().table("channel_groups").select("*")
            .eq("id", group_id).maybe_single().execute())
    return resp.data


def list_channel_groups(organization_id: str) -> list[dict[str, Any]]:
    resp = (_get().table("channel_groups").select("*")
            .eq("organization_id", organization_id).order("name").execute())
    return resp.data or []


def get_active_coupons(organization_id: str,
                      source_name: Optional[str] = None) -> list[dict[str, Any]]:
    """Cupons cadastrados e ativos — nunca inventados pela copy, só
    aparecem no post se estiverem aqui. Prioriza cupom específico da loja
    (source_name); sem nenhum específico, usa os "vale pra qualquer loja"
    (source_name nulo no cadastro)."""
    todos = (_get().table("coupon_codes").select("code, label, source_name")
             .eq("organization_id", organization_id)
             .eq("is_active", True).order("created_at").execute().data or [])
    especificos = [c for c in todos if source_name and c.get("source_name") == source_name]
    return especificos or [c for c in todos if not c.get("source_name")]


def get_cta_phrases(organization_id: str) -> list[dict[str, Any]]:
    resp = (_get().table("cta_phrases").select("phrase")
            .eq("organization_id", organization_id)
            .eq("is_active", True).order("created_at").execute())
    return resp.data or []


def get_active_queues() -> list[dict[str, Any]]:
    resp = (_get().table("queues").select("*")
            .eq("is_active", True).order("created_at").execute())
    return resp.data or []


def get_queue_groups(queue_id: str) -> list[dict[str, Any]]:
    resp = (_get().table("queue_groups").select("group_id")
            .eq("queue_id", queue_id).execute())
    return resp.data or []


def get_last_dispatched_at(queue_id: str) -> Optional[str]:
    resp = (_get().table("queue_items")
            .select("dispatched_at").eq("queue_id", queue_id)
            .not_.is_("dispatched_at", "null")
            .order("dispatched_at", desc=True).limit(1).execute())
    if not resp.data:
        return None
    return resp.data[0].get("dispatched_at")


def get_pending_queue_items(queue_id: str, now_iso: str,
                            limit: int = 10) -> list[dict[str, Any]]:
    resp = (_get().table("queue_items")
            .select("*, campaign:campaigns(product:products(category,title))")
            .eq("queue_id", queue_id).eq("status", "PENDING")
            .lte("scheduled_at", now_iso)
            .order("scheduled_at").limit(limit).execute())
    return resp.data or []


def get_last_done_queue_product(queue_id: str) -> Optional[dict[str, Any]]:
    """Produto do último item realmente concluído, para diversidade."""
    resp = (_get().table("queue_items")
            .select("campaign:campaigns(product:products(category,title))")
            .eq("queue_id", queue_id).eq("status", "DONE")
            .order("published_at", desc=True).limit(1).execute())
    if not resp.data:
        return None
    campaign = resp.data[0].get("campaign") or {}
    return campaign.get("product") or None


def mark_queue_item(item_id: str, fields: dict[str, Any]) -> None:
    _get().table("queue_items").update(fields).eq("id", item_id).execute()


def get_capture_lab_config(organization_id: str) -> dict[str, Any]:
    """Configuração do Laboratório de Captura (categorias, palavras-chave,
    bloqueio de palavras, corte de score) — tudo editável pela tela em
    /campanhas. Cada seção falha isolada (tabela ainda não migrada, rede,
    etc.) e nunca derruba o worker: sem dado, aquele pedaço volta vazio e o
    chamador usa os defaults/env de sempre."""
    config: dict[str, Any] = {
        "min_score": None,
        "categories": {},
        "keywords_by_source": {},
        "blocklist": [],
    }
    try:
        settings = (_get().table("discovery_settings").select("min_score")
                    .eq("organization_id", organization_id)
                    .maybe_single().execute().data)
        if settings and settings.get("min_score") is not None:
            config["min_score"] = float(settings["min_score"])
    except Exception:
        pass
    try:
        categorias = (_get().table("discovery_categories")
                      .select("family_key, active, min_score, locked_until, target_percent")
                      .eq("organization_id", organization_id)
                      .execute().data or [])
        config["categories"] = {row["family_key"]: row for row in categorias}
    except Exception:
        pass
    try:
        termos = (_get().table("discovery_keywords").select("source_name, term")
                  .eq("organization_id", organization_id)
                  .eq("active", True).execute().data or [])
        por_fonte: dict[str, list[str]] = {}
        for linha in termos:
            por_fonte.setdefault(linha["source_name"], []).append(linha["term"])
        config["keywords_by_source"] = por_fonte
    except Exception:
        pass
    try:
        config["blocklist"] = (_get().table("discovery_blocklist")
                               .select("term, expires_at")
                               .eq("organization_id", organization_id)
                               .execute().data or [])
    except Exception:
        pass
    return config


def get_discovery_keywords(organization_id: str, source_name: str) -> list[str]:
    """Termos de busca ativos cadastrados pela tela pra essa fonte — somam-se
    (nunca substituem) aos termos vindos de variável de ambiente em
    main.py, então quem não usou a tela continua com o comportamento de
    sempre."""
    try:
        resp = (_get().table("discovery_keywords").select("term")
                .eq("organization_id", organization_id)
                .eq("source_name", source_name)
                .eq("active", True).execute())
        return [row["term"] for row in (resp.data or []) if row.get("term")]
    except Exception:
        return []


def register_audit(organization_id: Optional[str], *, actor_type: str,
                   action: str, entity_type: str, entity_id: str,
                   metadata: Optional[dict[str, Any]] = None) -> None:
    _get().table("audit_log").insert({
        "organization_id": organization_id,
        "actor_type": actor_type,
        "actor_id": "worker",
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
    }).execute()
