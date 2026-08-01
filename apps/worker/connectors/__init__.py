"""Topfy Affiliate OS — conectores de marketplace.

Interface comum portada do CanalTopfy Lab (scripts/cupons/connectors),
validada ao vivo nesta sessão com a API real da AliExpress.

Regra central: link com parâmetro de afiliado não prova comissão. Nenhum
conector marca verification_status="VERIFIED" sem evidência real devolvida
pela própria API oficial do programa.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class CredencialNaoConfigurada(RuntimeError):
    """Levantada quando uma operação exige API oficial mas não há
    credencial configurada — nunca finge que funcionou."""


class MarketplaceConnector(ABC):
    code: str  # bate com products.source_name no banco

    @abstractmethod
    def detect_url(self, url: str) -> bool:
        """True se a URL pertence a este marketplace."""

    @abstractmethod
    def normalize_url(self, url: str) -> str:
        """Remove parâmetros de rastreamento/sessão, devolve URL canônica."""

    @abstractmethod
    def get_product(self, url: str) -> dict[str, Any]:
        """Devolve os campos de Product que der para obter a partir da URL.
        Campo sem evidência fica None — nunca inventa preço/avaliação/venda.
        Sempre inclui 'method' ('API' ou 'MANUAL') e 'source_confidence'
        ('VERIFIED' só quando o dado veio mesmo da API oficial)."""

    def search_offers(self, query: str) -> list[dict[str, Any]]:
        """Busca por termo — só disponível em modo API. Levanta
        CredencialNaoConfigurada em modo manual."""
        raise CredencialNaoConfigurada(
            f"{self.code}: busca por termo exige API oficial configurada")

    @abstractmethod
    def generate_affiliate_link(self, product_url: str) -> dict[str, Any]:
        """Devolve {'affiliate_url', 'tracking_id', 'generation_method',
        'verification_status', ...}. Em modo manual, 'verification_status'
        nunca é 'VERIFIED'."""

    @abstractmethod
    def verify_affiliate_link(self, affiliate_url: str) -> dict[str, Any]:
        """Devolve {'verification_status', 'verification_evidence'}. Nunca
        devolve 'VERIFIED' sem evidência real da API oficial."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Devolve {'connector_type', 'credential_status', 'health_status'}
        sem chamada de rede se não houver credencial configurada."""
