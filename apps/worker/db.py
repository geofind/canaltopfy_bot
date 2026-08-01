"""Topfy Affiliate OS — acesso ao banco (Supabase PostgREST).

Worker usa a service_role key para escrita (máquina de estados e jobs);
leitura de dados externos respeita os campos obrigatórios do princípio de
dados (source_name, source_url, collected_at, method, confidence, status,
external_id).
"""
from __future__ import annotations

import os
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


def has_active_publication(campaign_id: str, channel: str) -> bool:
    """Deduplicação: existe publicação não-falha da campanha neste canal?"""
    resp = (_get().table("publications")
            .select("id").eq("campaign_id", campaign_id).eq("channel", channel)
            .neq("status", "FAILED").neq("status", "CANCELLED").execute())
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
