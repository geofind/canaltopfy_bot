"""Testes da descoberta supervisionada de ofertas Mercado Livre."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

import db
import discovery
from connectors import CredencialNaoConfigurada
from connectors.mercadolivre import MercadoLivreConnector


class MercadoLivreSearchOffersTests(unittest.TestCase):
    def test_exige_conta_conectada(self):
        with self.assertRaises(CredencialNaoConfigurada):
            MercadoLivreConnector().search_offers("notebook")

    def test_busca_mlb_com_token_e_remove_duplicados(self):
        fixture = {
            "results": [
                {
                    "id": "MLB1234567890", "title": "Notebook Oferta",
                    "permalink": "https://produto.mercadolivre.com.br/MLB-1234567890-x",
                    "thumbnail": "https://http2.mlstatic.com/x.jpg",
                    "price": 900, "original_price": 1000,
                    "currency_id": "BRL", "sold_quantity": 42,
                },
                {
                    "id": "MLB1234567890", "title": "Duplicado",
                    "permalink": "https://produto.mercadolivre.com.br/MLB-1234567890-x",
                    "price": 900, "original_price": 1000,
                    "currency_id": "BRL",
                },
            ]
        }
        with mock.patch("connectors.mercadolivre._get_json",
                        return_value=fixture) as get_json:
            ofertas = MercadoLivreConnector("tok").search_offers("notebook")

        self.assertEqual(len(ofertas), 1)
        self.assertEqual(ofertas[0]["discount_percent"], 10.0)
        url = get_json.call_args.args[0]
        self.assertIn("/sites/MLB/search?", url)
        self.assertIn("q=notebook", url)
        self.assertEqual(get_json.call_args.kwargs["access_token"], "tok")

    def test_401_orienta_reconectar(self):
        erro = HTTPError("url", 401, "Unauthorized", None, None)
        self.addCleanup(erro.close)
        with mock.patch("connectors.mercadolivre._get_json",
                        side_effect=erro):
            with self.assertRaisesRegex(CredencialNaoConfigurada,
                                        "reconecte"):
                MercadoLivreConnector("expirado").search_offers("fone")


class _Response:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, name, state):
        self.name = name
        self.state = state
        self.pending_insert = None

    def select(self, *_args): return self
    def eq(self, *_args): return self
    def limit(self, *_args): return self

    def insert(self, row):
        self.pending_insert = row
        self.state.setdefault(self.name, []).append(row)
        return self

    def execute(self):
        if self.pending_insert is not None and self.name == "products":
            return _Response([{**self.pending_insert, "id": "product-1"}])
        return _Response([])


class _Client:
    def __init__(self):
        self.state = {}

    def table(self, name):
        return _Table(name, self.state)


class MercadoLivreDiscoveryTests(unittest.TestCase):
    OFERTA = {
        "external_product_id": "MLB1234567890",
        "canonical_url": "https://produto.mercadolivre.com.br/MLB-1234567890-x",
        "title": "Notebook Oferta", "main_image_url": "https://img/x.jpg",
        "current_price": 900.0, "original_price": 1000.0,
        "discount_percent": 10.0, "currency": "BRL", "sold_count": 42,
        "method": "API", "source_confidence": "VERIFIED",
    }

    def test_captura_privada_sem_link_ou_publicacao(self):
        client = _Client()
        with mock.patch.object(db, "get_ml_access_token", return_value="tok"), \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(MercadoLivreConnector, "search_offers",
                               return_value=[dict(self.OFERTA)]), \
             mock.patch.object(db, "register_audit") as audit:
            resultado = discovery.capturar_ofertas_mercadolivre(
                "org-1", termos=["notebook"], min_discount_pct=5)

        self.assertEqual(resultado["total"], 1)
        produto = client.state["products"][0]
        campanha = client.state["campaigns"][0]
        self.assertIsNone(produto["affiliate_link"])
        self.assertEqual(produto["affiliate_link_status"], "UNKNOWN")
        self.assertFalse(campanha["public_page"])
        self.assertEqual(campanha["status"], "READY")
        self.assertNotIn("publications", client.state)
        audit.assert_called_once()

    def test_ignora_desconto_abaixo_do_minimo(self):
        client = _Client()
        oferta = {**self.OFERTA, "discount_percent": 4.9}
        with mock.patch.object(db, "get_ml_access_token", return_value="tok"), \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(MercadoLivreConnector, "search_offers",
                               return_value=[oferta]):
            resultado = discovery.capturar_ofertas_mercadolivre(
                "org-1", termos=["notebook"], min_discount_pct=5)
        self.assertEqual(resultado["total"], 0)
        self.assertNotIn("products", client.state)


if __name__ == "__main__":
    unittest.main()
