"""Testes do conector Shopee Affiliate Open API."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from connectors.shopee import (
    ShopeeConnector,
    _authorization,
    _campaign_offer_query,
    _parse_campaign_offer,
    _parse_offer,
    _product_offer_query,
)


class ShopeeConnectorTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {
            "SHOPPE_APP_KEY": "app-123",
            "SHOPPE_APP_SECRET": "secret-456",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_assinatura_usa_payload_exato(self):
        payload = json.dumps({"query": "query { ping }"}, separators=(",", ":"))
        expected = hashlib.sha256(
            f"app-1231700000000{payload}secret-456".encode()
        ).hexdigest()
        header = _authorization("app-123", "secret-456", payload, 1700000000)
        self.assertEqual(
            header,
            f"SHA256 Credential=app-123, Timestamp=1700000000, Signature={expected}",
        )

    def test_query_escapa_termo_e_limita_pagina(self):
        query = _product_offer_query(keyword='tv "4k"', page=0, limit=999)
        self.assertIn('keyword:"tv \\"4k\\""', query)
        self.assertIn("page:1", query)
        self.assertIn("limit:50", query)

    def test_extrai_item_id_sem_confundir_com_shop_id(self):
        connector = ShopeeConnector()
        self.assertEqual(
            connector._external_id(
                "https://shopee.com.br/produto-i.12345678.987654321"),
            "987654321",
        )
        self.assertEqual(
            connector._external_id(
                "https://shopee.com.br/product/12345678/987654321"),
            "987654321",
        )

    def test_normaliza_oferta_com_link_afiliado_verificado(self):
        offer = _parse_offer({
            "itemId": 123456789,
            "productName": "Smartphone Oferta",
            "productLink": "https://shopee.com.br/produto-i.10.123456789",
            "offerLink": "https://s.shopee.com.br/abc",
            "imageUrl": "https://cf.shopee.com.br/file/x",
            "priceMin": "799.90",
            "priceDiscountRate": 20,
            "commissionRate": "0.12",
            "commission": "95.99",
            "ratingStar": "4.8",
            "sales": 321,
            "shopId": 10,
            "shopName": "Loja Oficial",
            "productCatIds": [100, 200],
        })
        self.assertEqual(offer["external_product_id"], "123456789")
        self.assertEqual(offer["current_price"], 799.9)
        self.assertEqual(offer["original_price"], 999.88)
        self.assertEqual(offer["commission_percent"], 12.0)
        self.assertEqual(offer["affiliate_link_status"], "VERIFIED")

    def test_busca_mapeia_resposta_graphql(self):
        fixture = {"productOfferV2": {"nodes": [{
            "itemId": 1,
            "productName": "Fone",
            "productLink": "https://shopee.com.br/fone-i.2.1",
            "offerLink": "https://s.shopee.com.br/x",
            "priceMin": "50",
            "priceDiscountRate": 10,
        }]}}
        with mock.patch("connectors.shopee._graphql", return_value=fixture) as call:
            offers = ShopeeConnector().search_offers("fone", page_no=2)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["title"], "Fone")
        self.assertIn("page:2", call.call_args.args[0])

    def test_campanha_oficial_traz_link_da_conta_e_validade(self):
        parsed = _parse_campaign_offer({
            "offerName": "Cupom Tecnologia",
            "offerLink": "https://s.shopee.com.br/topfy",
            "originalLink": "https://shopee.com.br/m/cupom-tech",
            "offerType": 1,
            "collectionId": 987,
            "periodStartTime": 1700000000,
            "periodEndTime": 1700100000,
            "commissionRate": "0.08",
        })
        self.assertEqual(parsed["external_product_id"], "collection:987")
        self.assertEqual(parsed["affiliate_link_status"], "VERIFIED")
        self.assertEqual(parsed["commission_percent"], 8.0)

    def test_busca_campanhas_usa_shopee_offer_v2(self):
        query = _campaign_offer_query(keyword="cupom", page=2, limit=100)
        self.assertIn("shopeeOfferV2", query)
        self.assertIn('keyword:"cupom"', query)
        self.assertIn("page:2", query)
        self.assertIn("limit:50", query)

    def test_gera_shortlink_com_sub_ids(self):
        with mock.patch.dict(os.environ, {
            "SHOPEE_AFFILIATE_SUB_IDS": "canaltopfy,telegram"
        }), mock.patch("connectors.shopee._graphql", return_value={
            "generateShortLink": {"shortLink": "https://s.shopee.com.br/abc"}
        }) as call:
            result = ShopeeConnector().generate_affiliate_link(
                "https://shopee.com.br/produto-i.10.123456789?tracking=x"
            )
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["affiliate_url"], "https://s.shopee.com.br/abc")
        self.assertIn('subIds:["canaltopfy","telegram"]', call.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
