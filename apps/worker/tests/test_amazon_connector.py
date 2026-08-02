"""Testes offline do conector Amazon (importação manual, sem rede).

Cobrem: detecção de domínio (amazon./amzn.to), extração de ASIN, rejeição de
URLs de categoria (node=, /s, bestsellers), normalize_url, importação manual
sem inventar dados, redirect best-effort (amzn.to -> canonical) e o link de
afiliado UNKNOWN (nunca VERIFIED).
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from connectors.amazon import (AmazonConnector, _extrair_asin,  # noqa: E402
                                _is_categoria)
from connectors import CredencialNaoConfigurada  # noqa: E402


class DetectUrlTests(unittest.TestCase):
    def setUp(self):
        self.conector = AmazonConnector()

    def test_amazon_br(self):
        self.assertTrue(self.conector.detect_url(
            "https://www.amazon.com.br/dp/B0XX1234Z5"))

    def test_amzn_to(self):
        self.assertTrue(self.conector.detect_url("https://amzn.to/4hKx5yk"))
        self.assertTrue(self.conector.detect_url("https://amzn.to/45CQFoY"))

    def test_amazon_us(self):
        self.assertTrue(self.conector.detect_url(
            "https://www.amazon.com/dp/B0XX1234Z5"))

    def test_nao_amazon(self):
        self.assertFalse(self.conector.detect_url(
            "https://www.google.com/search?q=amazon"))
        self.assertFalse(self.conector.detect_url(
            "https://pt.aliexpress.com/item/100500.html"))

    def test_invalida(self):
        self.assertFalse(self.conector.detect_url("nao-e-uma-url"))


class CategoriaTests(unittest.TestCase):
    def test_browse_node(self):
        self.assertTrue(_is_categoria(
            "https://www.amazon.com.br/b?node=103991115011"))

    def test_busca_s(self):
        self.assertTrue(_is_categoria(
            "https://www.amazon.com.br/s?k=smartwatch"))

    def test_bestsellers(self):
        self.assertTrue(_is_categoria(
            "https://www.amazon.com.br/gp/bestsellers"))

    def test_produto_dp_nao_e_categoria(self):
        self.assertFalse(_is_categoria(
            "https://www.amazon.com.br/dp/B0XX1234Z5?tag=topfy-20"))

    def test_amzn_to_curto_nao_e_categoria(self):
        self.assertFalse(_is_categoria("https://amzn.to/4hKx5yk"))


class AsinTests(unittest.TestCase):
    def test_dp_br(self):
        from connectors.amazon import _extrair_asin
        self.assertEqual(
            _extrair_asin("https://www.amazon.com.br/dp/B0XX1234Z5"),
            "B0XX1234Z5")

    def test_gp_product(self):
        self.assertEqual(
            _extrair_asin("https://www.amazon.com/gp/product/B0YY1234Z6"),
            "B0YY1234Z6")

    def test_sem_asin(self):
        self.assertIsNone(_extrair_asin("https://amzn.to/4hKx5yk"))


class ImportProductTests(unittest.TestCase):
    def setUp(self):
        self.conector = AmazonConnector()

    @mock.patch("connectors.amazon._resolve_product_url",
                return_value="https://www.amazon.com.br/dp/B0XX1234Z5")
    def test_amzn_to_resolve_canonical(self, _resolve):
        produto = self.conector.get_product("https://amzn.to/4hKx5yk")
        self.assertEqual(produto["method"], "MANUAL")
        self.assertEqual(produto["source_confidence"], "UNKNOWN")
        self.assertEqual(produto["external_product_id"], "B0XX1234Z5")
        self.assertEqual(produto["canonical_url"],
                         "https://www.amazon.com.br/dp/B0XX1234Z5")
        # campos caros ficam None — nunca inventa
        self.assertIsNone(produto["title"])
        self.assertIsNone(produto["current_price"])
        self.assertIsNone(produto["original_price"])
        self.assertIsNone(produto["main_image_url"])

    @mock.patch("connectors.amazon._resolve_product_url", return_value=None)
    def test_amzn_sem_resolve_nao_quebra(self, _resolve):
        produto = self.conector.get_product("https://amzn.to/4hKx5yk")
        self.assertEqual(produto["canonical_url"], "https://amzn.to/4hKx5yk")
        self.assertIsNone(produto["external_product_id"])

    def test_dp_direto_sem_rede(self):
        with mock.patch.object(self.conector, "_resolve",
                               return_value="https://www.amazon.com.br"
                                            "/dp/B0ZZ1234Z7?tag=abc-20"):
            produto = self.conector.get_product(
                "https://www.amazon.com.br/dp/B0ZZ1234Z7?tag=abc-20")
        self.assertEqual(produto["external_product_id"], "B0ZZ1234Z7")
        # canonical_url normalizado (sem query de tracking)
        self.assertEqual(
            produto["canonical_url"],
            "https://www.amazon.com.br/dp/B0ZZ1234Z7")

    def test_rejeita_categoria(self):
        with self.assertRaises(ValueError) as ctx:
            self.conector.get_product(
                "https://www.amazon.com.br/b?node=103991115011")
        self.assertIn("CATEGORIA", str(ctx.exception))

    def test_detect_url_antes_de_categoria(self):
        with self.assertRaises(ValueError):
            self.conector.get_product(
                "https://www.amazon.com.br/s?k=teste")


class AffiliateLinkTests(unittest.TestCase):
    def setUp(self):
        self.conector = AmazonConnector()

    def test_amzn_to_e_link_afiliado_unknow(self):
        link = self.conector.generate_affiliate_link("https://amzn.to/4hKx5yk")
        self.assertEqual(link["affiliate_url"], "https://amzn.to/4hKx5yk")
        self.assertEqual(link["verification_status"], "UNKNOWN")
        self.assertEqual(link["generation_method"], "MANUAL")

    def test_url_sem_tag_nao_vira_afiliado(self):
        with self.assertRaises(CredencialNaoConfigurada):
            self.conector.generate_affiliate_link(
                "https://www.amazon.com.br/dp/B0XX1234Z5")

    def test_verify_sempre_unknow(self):
        self.assertEqual(
            self.conector.verify_affiliate_link("https://amzn.to/4hKx5yk")
            ["verification_status"], "UNKNOWN")

    def test_health_manual(self):
        self.assertEqual(self.conector.health_check()["connector_type"],
                         "MANUAL")


if __name__ == "__main__":
    unittest.main()