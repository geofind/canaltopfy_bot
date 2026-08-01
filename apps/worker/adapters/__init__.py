"""Topfy Affiliate OS — adapters de plataformas externas (modo simulado).

Regra do spec: toda integração vive em modo 'simulated' até o usuário
configurar credenciais reais e aprovar a publicação. Nenhum adapter simulado
faz chamada de rede; apenas devolve o payload que seria enviado, para o
pipeline e os testes E2E funcionarem de ponta a ponta sem conta externa.

Fase 1 (MVP): telegram real + whatsapp assistido (wa.me) + web (vitrine).
Fase 2: tiktok, instagram, youtube (exigem auditoria/App Review da Meta/TikTok).
Fase 4: google ads.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class SimulatedResult:
    """Resultado de um adapter simulado — estrutura idêntica à de produção."""
    status: str  # 'PUBLISHED' | 'PENDING' | 'FAILED'
    external_id: Optional[str]
    external_url: Optional[str]
    simulated: bool = True
    evidence: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def _is_production_mode() -> bool:
    """Produção só quando o usuário configura explicitamente TOPFY_PRODUCTION=1."""
    return os.environ.get("TOPFY_PRODUCTION") == "1"


# ------------------------------------------------------------
# Amazon Creators API — mock até elegibilidade (10 vendas / 30 dias)
# ------------------------------------------------------------
class AmazonAdapter:
    channel = "amazon"

    def generate_affiliate_link(self, product_url: str) -> dict[str, Any]:
        return {
            "affiliate_url": None,
            "generation_method": "MOCK",
            "verification_status": "NOT_AVAILABLE",
            "aviso": (
                "Amazon Creators API exige elegibilidade (10 vendas "
                "qualificadas nos últimos 30 dias). Até lá, use link manual "
                "gerado no portal da Amazon Associates."),
        }

    def health_check(self) -> dict[str, Any]:
        return {
            "connector_type": "MOCK",
            "credential_status": "NOT_ELIGIBLE",
            "health_status": "OK",
            "detalhe": "Mock — aguardando elegibilidade para Amazon Creators API.",
        }


# ------------------------------------------------------------
# WhatsApp — assistido via wa.me no MVP; Cloud API na Fase 2
# ------------------------------------------------------------
class WhatsAppAdapter:
    channel = "whatsapp"

    def build_wa_me_url(self, phone: str, text: str) -> str:
        from urllib.parse import quote
        return f"https://wa.me/{phone}?text={quote(text)}"

    def send_message(self, phone: str, text: str) -> SimulatedResult:
        if _is_production_mode():
            # Produção real exige token da WhatsApp Business Cloud API —
            # nunca finge sucesso sem credencial válida.
            if not os.environ.get("WHATSAPP_TOKEN"):
                return SimulatedResult(
                    status="FAILED", external_id=None, external_url=None,
                    evidence="WHATSAPP_TOKEN não configurado — publicação real bloqueada.")
            raise NotImplementedError(
                "WhatsApp Cloud API: integração oficial na Fase 2 "
                "(opt-in + template aprovado + janela de 24h).")
        return SimulatedResult(
            status="PENDING", external_id=None,
            external_url=self.build_wa_me_url(phone, text),
            evidence="Modo simulado — gera link wa.me para envio manual.",
            details={"phone": phone})

    def health_check(self) -> dict[str, Any]:
        return {
            "connector_type": "MOCK",
            "credential_status": "NOT_CONFIGURED",
            "health_status": "OK",
            "detalhe": "Assistido (wa.me) no MVP; Cloud API na Fase 2.",
        }


# ------------------------------------------------------------
# TikTok — Content Posting API (auditoria exigida para Direct Post)
# ------------------------------------------------------------
class TikTokAdapter:
    channel = "tiktok"

    def create_post(self, title: str, text: str, media_url: Optional[str] = None) -> SimulatedResult:
        if _is_production_mode():
            return SimulatedResult(
                status="FAILED", external_id=None, external_url=None,
                evidence=(
                    "TikTok Content Posting API: Direct Post exige auditoria "
                    "da plataforma; sem credencial configurada, publicação "
                    "real bloqueada."))
        return SimulatedResult(
            status="PENDING", external_id=None, external_url=None,
            evidence="Modo simulado — Fase 2 (auditoria TikTok pendente).",
            details={"title": title, "text": text, "media_url": media_url})

    def health_check(self) -> dict[str, Any]:
        return {
            "connector_type": "MOCK",
            "credential_status": "NOT_CONFIGURED",
            "health_status": "OK",
            "detalhe": "Fase 2 — auditoria da TikTok exigida para Direct Post.",
        }


# ------------------------------------------------------------
# Instagram — Graph API Content Publishing (Business/Creator)
# ------------------------------------------------------------
class InstagramAdapter:
    channel = "instagram"

    def create_post(self, text: str, media_url: Optional[str] = None) -> SimulatedResult:
        if _is_production_mode():
            return SimulatedResult(
                status="FAILED", external_id=None, external_url=None,
                evidence=(
                    "Instagram Graph API exige conta Business/Creator e App "
                    "Review da Meta — sem credencial, publicação real "
                    "bloqueada."))
        return SimulatedResult(
            status="PENDING", external_id=None, external_url=None,
            evidence="Modo simulado — Fase 2 (App Review da Meta pendente).",
            details={"text": text, "media_url": media_url})

    def health_check(self) -> dict[str, Any]:
        return {
            "connector_type": "MOCK",
            "credential_status": "NOT_CONFIGURED",
            "health_status": "OK",
            "detalhe": "Fase 2 — conta Business/Creator + App Review exigidos.",
        }


# ------------------------------------------------------------
# YouTube — Data API v3 (Fase 2)
# ------------------------------------------------------------
class YouTubeAdapter:
    channel = "youtube"

    def create_post(self, text: str, title: Optional[str] = None) -> SimulatedResult:
        if _is_production_mode():
            return SimulatedResult(
                status="FAILED", external_id=None, external_url=None,
                evidence="YouTube Data API v3: sem credencial OAuth configurada.")
        return SimulatedResult(
            status="PENDING", external_id=None, external_url=None,
            evidence="Modo simulado — Fase 2 (YouTube Data API v3).",
            details={"title": title, "text": text})

    def health_check(self) -> dict[str, Any]:
        return {
            "connector_type": "MOCK",
            "credential_status": "NOT_CONFIGURED",
            "health_status": "OK",
            "detalhe": "Fase 2 — YouTube Data API v3.",
        }


def get_adapter(channel: str):
    adapters = {
        "amazon": AmazonAdapter,
        "whatsapp": WhatsAppAdapter,
        "tiktok": TikTokAdapter,
        "instagram": InstagramAdapter,
        "youtube": YouTubeAdapter,
    }
    cls = adapters.get(channel)
    if cls is None:
        raise ValueError(f"Adapter desconhecido: {channel}")
    return cls()
