"""Testes stdlib do worker Topfy Affiliate OS.

Cobrem: score decomposto (pesos do spec somando 100, bloqueios), copy
determinística (nunca inventa fato), validar_copy (frases proibidas),
adapters simulados (nunca fingem sucesso), conector AliExpress (modo
manual sem credencial — sem rede) e helpers do pipeline.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

# Garante que o worker roda sem credenciais externas nos testes
for chave in ("ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET",
              "ALIEXPRESS_TRACKING_ID", "TELEGRAM_BOT_TOKEN",
              "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
              "OLLAMA_BASE_URL", "TOPFY_PRODUCTION"):
    os.environ.pop(chave, None)

from scoring import PESO_MAXIMO, calcular_score  # noqa: E402
from content import gerar_copy, validar_copy, FRASES_PROIBIDAS  # noqa: E402
from adapters import (AmazonAdapter, WhatsAppAdapter, TikTokAdapter,  # noqa: E402
                      InstagramAdapter, YouTubeAdapter)
from connectors.aliexpress import AliExpressConnector  # noqa: E402

PRODUTO_VERIFIED = {
    "id": 1,
    "title": "Fone Bluetooth XYZ",
    "current_price": 49.9,
    "original_price": 99.9,
    "discount_percent": 50.0,
    "rating": 4.7,
    "sold_count": 1200,
    "commission_percent": 8.5,
    "main_image_url": "https://img.aliexpress.com/x.jpg",
    "source_confidence": "VERIFIED",
}
LINK_VERIFIED = {"verification_status": "VERIFIED", "affiliate_url": "https://s.click.aliexpress.com/x"}


class ScoreTests(unittest.TestCase):
    def test_pesos_somam_100(self):
        self.assertEqual(sum(PESO_MAXIMO.values()), 100)
        self.assertEqual(sorted(PESO_MAXIMO), sorted([
            "desconto_real", "vendas", "avaliacao", "comissao",
            "tendencia", "apelo_visual", "concorrencia", "confiabilidade"]))

    def test_score_completo_sem_bloqueios(self):
        score = calcular_score(PRODUTO_VERIFIED, LINK_VERIFIED)
        self.assertEqual(score["bloqueios"], [])
        self.assertGreater(score["score_total"], 60)

    def test_link_nao_verificado_bloqueia(self):
        score = calcular_score(PRODUTO_VERIFIED, {"verification_status": "UNKNOWN"})
        self.assertTrue(any("verificado" in b.lower() for b in score["bloqueios"]))

    def test_sem_preco_bloqueia(self):
        produto = dict(PRODUTO_VERIFIED, current_price=None, original_price=None)
        score = calcular_score(produto, LINK_VERIFIED)
        self.assertTrue(any("preço" in b.lower() for b in score["bloqueios"]))
        self.assertEqual(score["desconto_real"], 0.0)

    def test_sem_imagem_apelo_visual_zero(self):
        produto = dict(PRODUTO_VERIFIED, main_image_url=None)
        score = calcular_score(produto, LINK_VERIFIED)
        self.assertEqual(score["apelo_visual"], 0.0)

    def test_confiabilidade_unknow_pontua_menos(self):
        produto = dict(PRODUTO_VERIFIED, source_confidence="UNKNOWN")
        score = calcular_score(produto, LINK_VERIFIED)
        self.assertLess(score["confiabilidade"], 5.0)


class ContentTests(unittest.TestCase):
    def test_copy_nunca_inventa_fato(self):
        for seed in range(10):
            copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao",
                              provider="fallback", seed=seed)
            self.assertIn("49.90", copy["body"] or "")
            self.assertIn(PRODUTO_VERIFIED["title"], copy["headline"])

    def test_produto_sem_preco_nunca_mostra_numero(self):
        produto = {"id": 9, "title": "Produto Sem Dados"}
        for seed in range(10):
            copy = gerar_copy(produto, "oferta-padrao", provider="fallback", seed=seed)
            self.assertNotRegex(copy["headline"], r"R\$\s*\d")

    def test_validar_copy_detecta_frase_proibida(self):
        copia = {
            "headline": "ÚLTIMAS UNIDADES! Compre agora!",
            "body": "texto",
            "cta": "Ver",
            "disclaimer": "Link de afiliado.",
        }
        problemas = validar_copy(copia)
        self.assertTrue(any("proibida" in p for p in problemas))

    def test_validar_copy_exige_disclaimer(self):
        copia = {"headline": "x", "body": "y", "cta": "z", "disclaimer": ""}
        problemas = validar_copy(copia)
        self.assertTrue(any("disclaimer" in p for p in problemas))

    def test_mesma_seed_e_reproduzivel(self):
        a = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="fallback", seed=42)
        b = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="fallback", seed=42)
        self.assertEqual(a, b)

    def test_ollama_ausente_cai_no_fallback_com_provider_auto(self):
        copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="auto", seed=7)
        self.assertEqual(copy["provider"], "fallback")


class AdaptersTests(unittest.TestCase):
    def test_adapters_simulados_nunca_publicam_de_verdade(self):
        whatsapp = WhatsAppAdapter().send_message("5511999999999", "texto")
        self.assertIn(whatsapp.status, ("PENDING", "FAILED"))
        self.assertTrue(whatsapp.simulated)
        for adapter in [TikTokAdapter(), InstagramAdapter(), YouTubeAdapter()]:
            resultado = adapter.create_post("texto", "https://img/x.jpg")
            self.assertIn(resultado.status, ("PENDING", "FAILED"))
            self.assertTrue(resultado.simulated)

    def test_amazon_mock_gera_link_nao_disponivel(self):
        resultado = AmazonAdapter().generate_affiliate_link("https://amzn.to/x")
        self.assertEqual(resultado["verification_status"], "NOT_AVAILABLE")
        self.assertIsNone(resultado["affiliate_url"])

    def test_wa_me_url(self):
        url = WhatsAppAdapter().build_wa_me_url("5511999999999", "Olá, oferta!")
        self.assertIn("wa.me/5511999999999", url)
        self.assertIn("Ol%C3%A1", url)


class AliExpressConnectorTests(unittest.TestCase):
    def setUp(self):
        self.conector = AliExpressConnector()

    def test_detect_url(self):
        self.assertTrue(self.conector.detect_url("https://pt.aliexpress.com/item/100500.html"))
        self.assertFalse(self.conector.detect_url("https://www.amazon.com.br/dp/B0XYZ"))

    def test_normalize_url_remove_query(self):
        self.assertEqual(
            self.conector.normalize_url("https://pt.aliexpress.com/item/100500.html?spm=abc&x=1"),
            "https://pt.aliexpress.com/item/100500.html")

    def test_modo_manual_sem_rede(self):
        """Sem credencial, get_product devolve MANUAL/UNKNOWN sem rede."""
        produto = self.conector.get_product("https://pt.aliexpress.com/item/100500.html")
        self.assertEqual(produto["method"], "MANUAL")
        self.assertEqual(produto["source_confidence"], "UNKNOWN")
        self.assertEqual(produto["external_product_id"], "100500")
        self.assertIsNone(produto["current_price"])

    def test_gerar_link_sem_credencial_levanta_aviso(self):
        from connectors import CredencialNaoConfigurada
        with self.assertRaises(CredencialNaoConfigurada):
            self.conector.generate_affiliate_link("https://pt.aliexpress.com/item/100500.html")

    def test_health_check_sem_credencial(self):
        health = self.conector.health_check()
        self.assertEqual(health["connector_type"], "MANUAL")
        self.assertEqual(health["credential_status"], "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
