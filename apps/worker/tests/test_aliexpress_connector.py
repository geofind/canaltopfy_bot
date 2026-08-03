"""Testes do conector AliExpress Affiliate API."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from connectors.aliexpress import AliExpressConnector  # noqa: E402

RESPOSTA_VAZIA = {
    "aliexpress_affiliate_product_query_response": {
        "resp_result": {"resp_code": 200, "result": {"products": {}}},
    },
}


class SearchOffersTests(unittest.TestCase):
    """Pedido do usuário: só produtos mais vendidos e bem avaliados que
    enviam para o Brasil — "bem avaliados" já é filtrado pelo Topfy Score
    (dimensão avaliação usa evaluate_rate); aqui garantimos que a busca em
    si já pede pra API oficial ordenar por vendas e restringir a entrega
    ao Brasil, sem depender de nenhum scraping do site."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {
            "ALIEXPRESS_APP_KEY": "app-123",
            "ALIEXPRESS_APP_SECRET": "secret-456",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_busca_pede_mais_vendidos_e_entrega_no_brasil(self):
        with mock.patch("connectors.aliexpress._chamar_api",
                        return_value=RESPOSTA_VAZIA) as chamar:
            AliExpressConnector().search_offers("fone bluetooth")
        _metodo, _app_key, _app_secret, extra_params = chamar.call_args.args
        self.assertEqual(extra_params["ship_to_country"], "BR")
        self.assertEqual(extra_params["sort"], "LAST_VOLUME_DESC")

    def test_sem_credenciais_levanta_erro_sem_chamar_api(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("connectors.aliexpress._chamar_api") as chamar:
            with self.assertRaises(Exception):
                AliExpressConnector().search_offers("fone bluetooth")
            chamar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
