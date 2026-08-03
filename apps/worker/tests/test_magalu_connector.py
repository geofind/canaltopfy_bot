import os
import unittest
from unittest.mock import patch

from connectors import CredencialNaoConfigurada
from connectors.magalu import MagaluConnector


class MagaluConnectorTest(unittest.TestCase):
    def setUp(self):
        self.connector = MagaluConnector()

    def test_detects_official_magalu_hosts(self):
        self.assertTrue(self.connector.detect_url("https://www.magazineluiza.com.br/produto/p/123/"))
        self.assertTrue(self.connector.detect_url("https://www.magazinevoce.com.br/magazinecanaltopfy/"))
        self.assertFalse(self.connector.detect_url("https://example.com/produto/p/123/"))

    @patch.dict(os.environ, {"MAGALU_STORE_SLUG": "canaltopfy"}, clear=False)
    def test_generates_official_storefront_product_link(self):
        result = self.connector.generate_affiliate_link(
            "https://www.magazineluiza.com.br/smart-tv/p/240147400/et/elit/?partner_id=123#top"
        )
        self.assertEqual(
            result["affiliate_url"],
            "https://www.magazinevoce.com.br/magazinecanaltopfy/smart-tv/p/240147400/et/elit/",
        )
        self.assertEqual(result["generation_method"], "OFFICIAL_STOREFRONT")
        self.assertEqual(result["verification_status"], "VERIFIED")

    @patch.dict(os.environ, {"MAGALU_STORE_SLUG": "canaltopfy"}, clear=False)
    def test_preserves_storefront_link(self):
        url = "https://www.magazinevoce.com.br/magazinecanaltopfy/smart-tv/p/240147400/et/elit/"
        self.assertEqual(self.connector.generate_affiliate_link(url)["affiliate_url"], url)

    @patch.dict(os.environ, {"MAGALU_STORE_SLUG": "canaltopfy"}, clear=False)
    def test_adds_showcase_to_coupon_page(self):
        result = self.connector.generate_affiliate_link(
            "https://especiais.magazineluiza.com.br/magazinevoce/cupons/?foo=bar"
        )
        self.assertIn("showcase=magazinecanaltopfy", result["affiliate_url"])
        self.assertEqual(
            self.connector.verify_affiliate_link(result["affiliate_url"])["verification_status"],
            "VERIFIED",
        )

    @patch.dict(os.environ, {"MAGALU_STORE_SLUG": "canaltopfy"}, clear=False)
    def test_get_product_does_not_invent_catalog_data(self):
        product = self.connector.get_product(
            "https://www.magazineluiza.com.br/smart-tv/p/240147400/et/elit/"
        )
        self.assertEqual(product["external_product_id"], "240147400")
        self.assertIsNone(product["title"])
        self.assertIsNone(product["current_price"])
        self.assertIsNone(product["main_image_url"])

    @patch.dict(os.environ, {}, clear=True)
    def test_requires_store_slug(self):
        with self.assertRaises(CredencialNaoConfigurada):
            self.connector.generate_affiliate_link(
                "https://www.magazineluiza.com.br/smart-tv/p/240147400/et/elit/"
            )
        self.assertEqual(self.connector.health_check()["health_status"], "DOWN")

    def test_search_loads_at_least_twenty_auditable_offers(self):
        offers = self.connector.search_offers("todos")
        self.assertGreaterEqual(len(offers), 20)
        for offer in offers:
            self.assertTrue(offer["canonical_url"].startswith(
                "https://www.magazinevoce.com.br/magazinecanaltopfy/"))
            self.assertTrue(offer["main_image_url"].startswith(
                "https://a-static.mlcdn.com.br/"))
            self.assertGreater(offer["current_price"], 0)
            self.assertGreater(offer["original_price"], 0)
            self.assertIn("source_page", offer)

    def test_search_filters_seed_by_term(self):
        offers = self.connector.search_offers("geladeira")
        self.assertTrue(offers)
        self.assertTrue(all("geladeira" in offer["title"].lower()
                            for offer in offers))


if __name__ == "__main__":
    unittest.main()
