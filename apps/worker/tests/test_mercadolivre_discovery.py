"""Testes da descoberta supervisionada de ofertas Mercado Livre."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

import db
import discovery
import main as worker_main
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

    def test_403_usa_catalogo_oficial_com_preco_imagem_e_item(self):
        proibido = HTTPError("url", 403, "Forbidden", None, None)
        self.addCleanup(proibido.close)
        previsto = [{
            "domain_id": "MLB-ELECTRIC_AIR_FRYERS",
            "domain_name": "Fritadeiras",
            "category_id": "MLB260398",
            "category_name": "Fritadeiras Eletricas",
        }]
        catalogo = {
            "results": [{
                "id": "MLB43435820", "name": "Air Fryer WAP",
                "domain_id": "MLB-KITCHEN_APPLIANCES",
                "pictures": [{"url": "https://http2.mlstatic.com/air.jpg"}],
            }],
        }
        itens = {"results": [
            {"item_id": "MLB6253142964", "price": 499,
             "original_price": 699, "currency_id": "BRL", "seller_id": 10},
            {"item_id": "MLB6000000000", "price": 550,
             "original_price": 600, "currency_id": "BRL", "seller_id": 11},
        ]}
        with mock.patch("connectors.mercadolivre._get_json",
                        side_effect=[proibido, previsto, catalogo, itens]) as get_json:
            ofertas = MercadoLivreConnector("tok").search_offers("air fryer")

        self.assertEqual(len(ofertas), 1)
        self.assertEqual(ofertas[0]["external_product_id"], "MLB6253142964")
        self.assertEqual(ofertas[0]["title"], "Air Fryer WAP")
        self.assertEqual(ofertas[0]["main_image_url"],
                         "https://http2.mlstatic.com/air.jpg")
        self.assertEqual(ofertas[0]["discount_percent"], 28.61)
        self.assertEqual(
            ofertas[0]["canonical_url"],
            "https://www.mercadolivre.com.br/p/MLB43435820?wid=MLB6253142964")
        chamadas = [call.args[0] for call in get_json.call_args_list]
        self.assertIn("/domain_discovery/search?", chamadas[1])
        self.assertIn("/products/search?", chamadas[2])
        self.assertIn("domain_id=MLB-ELECTRIC_AIR_FRYERS", chamadas[2])
        self.assertIn("/products/MLB43435820/items", chamadas[3])

    def test_preditor_de_dominio_rejeita_resposta_invalida(self):
        with mock.patch("connectors.mercadolivre._get_json",
                        return_value=[{"domain_id": "MLB-BOOKS"}]):
            self.assertIsNone(MercadoLivreConnector("tok").predict_domain(
                "smartphone"))

    def test_preco_vigente_substitui_preco_de_busca(self):
        oferta = {
            "external_product_id": "MLB1234567890",
            "current_price": 90.0,
            "original_price": 120.0,
            "discount_percent": 25.0,
            "currency": "BRL",
        }
        sale_price = {
            "amount": 75.0,
            "regular_amount": 100.0,
            "currency_id": "BRL",
        }
        with mock.patch("connectors.mercadolivre._get_json",
                        return_value=sale_price) as get_json:
            resultado = MercadoLivreConnector("tok").enrich_offer_price(oferta)

        self.assertEqual(resultado["current_price"], 75.0)
        self.assertEqual(resultado["original_price"], 100.0)
        self.assertEqual(resultado["discount_percent"], 25.0)
        self.assertEqual(resultado["price_source"], "sale_price")
        self.assertIn("/items/MLB1234567890/sale_price?", get_json.call_args.args[0])

    def test_preco_vigente_indisponivel_preserva_oferta(self):
        oferta = {"external_product_id": "MLB1234567890", "current_price": 90.0}
        erro = HTTPError("url", 404, "Not Found", None, None)
        self.addCleanup(erro.close)
        with mock.patch("connectors.mercadolivre._get_json", side_effect=erro):
            resultado = MercadoLivreConnector("tok").enrich_offer_price(oferta)
        self.assertIs(resultado, oferta)

    def test_429_interrompe_rajada_de_consultas_de_preco(self):
        oferta = {"external_product_id": "MLB1234567890", "current_price": 90.0}
        erro = HTTPError("url", 429, "Too Many Requests", None, None)
        self.addCleanup(erro.close)
        with mock.patch("connectors.mercadolivre._get_json", side_effect=erro):
            with self.assertRaisesRegex(RuntimeError, "429"):
                MercadoLivreConnector("tok").enrich_offer_price(oferta)

    def test_tendencias_oficiais_com_limite_e_dedupe(self):
        fixture = [
            {"keyword": "creatina"},
            {"keyword": "Creatina"},
            {"keyword": "air fryer"},
            {"keyword": "notebook"},
        ]
        with mock.patch("connectors.mercadolivre._get_json",
                        return_value=fixture) as get_json:
            termos = MercadoLivreConnector("tok").get_trending_terms(limit=2)
        self.assertEqual(termos, ["creatina", "air fryer"])
        self.assertEqual(get_json.call_args.args[0],
                         "https://api.mercadolibre.com/trends/MLB")

    def test_highlights_resolve_item_e_produto_e_ignora_user_product(self):
        ranking = {"content": [
            {"id": "MLBU3013800008", "position": 1,
             "type": "USER_PRODUCT"},
            {"id": "MLB6868664726", "position": 2, "type": "ITEM"},
            {"id": "MLB24162817", "position": 3, "type": "PRODUCT"},
        ]}
        item = {
            "id": "MLB6868664726", "title": "Geladeira Oferta",
            "permalink": "https://produto.mercadolivre.com.br/MLB-6868664726-x",
            "thumbnail": "https://img/item.jpg", "price": 1800,
            "original_price": 2000, "currency_id": "BRL",
        }
        produto = {
            "id": "MLB24162817", "name": "Produto Catalogo",
            "pictures": [{"url": "https://img/catalogo.jpg"}],
        }
        itens = {"results": [{
            "item_id": "MLB6999999999", "price": 80,
            "original_price": 100, "currency_id": "BRL",
        }]}
        with mock.patch("connectors.mercadolivre._get_json",
                        side_effect=[ranking, item, produto, itens]):
            ofertas = MercadoLivreConnector("tok").search_highlights(
                ["MLB432825"], limit=2)

        self.assertEqual([o["external_product_id"] for o in ofertas],
                         ["MLB6868664726", "MLB6999999999"])
        self.assertEqual([o["highlight_rank"] for o in ofertas], [2, 3])
        self.assertTrue(all(o["discovery_source"] == "highlights"
                            for o in ofertas))


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
             mock.patch.object(MercadoLivreConnector, "enrich_offer_price",
                               side_effect=lambda oferta: oferta), \
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
                               return_value=[oferta]), \
             mock.patch.object(MercadoLivreConnector, "enrich_offer_price",
                               side_effect=lambda item: item):
            resultado = discovery.capturar_ofertas_mercadolivre(
                "org-1", termos=["notebook"], min_discount_pct=5)
        self.assertEqual(resultado["total"], 0)
        self.assertNotIn("products", client.state)

    def test_bloqueia_por_palavra_da_curadoria(self):
        """Laboratório de Captura (/campanhas): palavra bloqueada impede a
        oferta de virar produto/campanha, mesmo passando no desconto."""
        client = _Client()
        capture_config = {
            "min_score": None, "categories": {},
            "keywords_by_source": {},
            "blocklist": [{"term": "notebook", "expires_at": None}],
        }
        with mock.patch.object(db, "get_ml_access_token", return_value="tok"), \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(db, "get_capture_lab_config",
                               return_value=capture_config), \
             mock.patch.object(MercadoLivreConnector, "search_offers",
                               return_value=[dict(self.OFERTA)]), \
             mock.patch.object(MercadoLivreConnector, "enrich_offer_price",
                               side_effect=lambda oferta: oferta), \
             mock.patch.object(db, "register_audit") as audit:
            resultado = discovery.capturar_ofertas_mercadolivre(
                "org-1", termos=["notebook"], min_discount_pct=5)
        self.assertEqual(resultado["total"], 0)
        self.assertNotIn("products", client.state)
        audit.assert_called_once()
        self.assertEqual(
            audit.call_args.kwargs["action"], "mercadolivre_bloqueado_por_palavra")

    def test_categoria_pausada_pela_curadoria_bloqueia_captura(self):
        client = _Client()
        capture_config = {
            "min_score": None,
            "categories": {"notebooks": {"active": False}},
            "keywords_by_source": {}, "blocklist": [],
        }
        with mock.patch.object(db, "get_ml_access_token", return_value="tok"), \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(db, "get_capture_lab_config",
                               return_value=capture_config), \
             mock.patch.object(MercadoLivreConnector, "search_offers",
                               return_value=[dict(self.OFERTA)]), \
             mock.patch.object(MercadoLivreConnector, "enrich_offer_price",
                               side_effect=lambda oferta: oferta), \
             mock.patch.object(db, "register_audit") as audit:
            resultado = discovery.capturar_ofertas_mercadolivre(
                "org-1", termos=["notebook"], min_discount_pct=5)
        self.assertEqual(resultado["total"], 0)
        self.assertNotIn("products", client.state)
        audit.assert_called_once()
        self.assertEqual(
            audit.call_args.kwargs["action"], "mercadolivre_categoria_bloqueada")

    def test_categoria_sem_configuracao_nao_bloqueia(self):
        """Ausência de linha em discovery_categories libera a captura —
        curadoria é opt-out, não uma lista fechada."""
        client = _Client()
        capture_config = {
            "min_score": None, "categories": {},
            "keywords_by_source": {}, "blocklist": [],
        }
        with mock.patch.object(db, "get_ml_access_token", return_value="tok"), \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(db, "get_capture_lab_config",
                               return_value=capture_config), \
             mock.patch.object(MercadoLivreConnector, "search_offers",
                               return_value=[dict(self.OFERTA)]), \
             mock.patch.object(MercadoLivreConnector, "enrich_offer_price",
                               side_effect=lambda oferta: oferta), \
             mock.patch.object(db, "register_audit"):
            resultado = discovery.capturar_ofertas_mercadolivre(
                "org-1", termos=["notebook"], min_discount_pct=5)
        self.assertEqual(resultado["total"], 1)


class MercadoLivreDiscoveryScheduleTests(unittest.TestCase):
    def test_ciclo_5_min_respeita_cooldown_de_fontes_pesadas(self):
        inicio = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
        configuracao = {
            "ML_DISCOVERY_ENABLED": True,
            "ML_DISCOVERY_ORG_ID": "org-1",
            "ML_DISCOVERY_TERMOS": ["creatina", "notebook", "smartwatch"],
            "ML_DISCOVERY_INTERVAL_MINUTES": 5,
            "ML_DISCOVERY_TERMS_PER_CYCLE": 2,
            "ML_DISCOVERY_TRENDS_ENABLED": True,
            "ML_DISCOVERY_TREND_LIMIT": 2,
            "ML_DISCOVERY_TREND_REFRESH_MINUTES": 360,
            "ML_DISCOVERY_HIGHLIGHT_CATEGORIES": ["MLB432825"],
            "ML_DISCOVERY_HIGHLIGHT_LIMIT": 5,
            "ML_DISCOVERY_HIGHLIGHT_CATEGORIES_PER_CYCLE": 8,
            "ML_DISCOVERY_HIGHLIGHT_REFRESH_MINUTES": 60,
        }
        with mock.patch.multiple(worker_main, **configuracao), \
             mock.patch.object(worker_main, "_ultima_descoberta_ml", None), \
             mock.patch.object(worker_main, "_ultima_tendencia_ml", None), \
             mock.patch.object(worker_main, "_ultimo_highlight_ml", None), \
             mock.patch.object(worker_main, "_indice_termo_ml", 0), \
             mock.patch.object(worker_main, "_indice_categoria_ml", 0), \
             mock.patch.object(worker_main, "capturar_ofertas_mercadolivre",
                               return_value={"total": 0}) as capturar:
            worker_main.rodar_descoberta_ml_se_configurada(now=inicio)
            worker_main.rodar_descoberta_ml_se_configurada(
                now=inicio + timedelta(minutes=6))

        self.assertEqual(capturar.call_count, 2)
        primeira = capturar.call_args_list[0].kwargs
        segunda = capturar.call_args_list[1].kwargs
        self.assertEqual(primeira["trend_limit"], 2)
        self.assertEqual(primeira["highlight_limit"], 5)
        self.assertEqual(segunda["trend_limit"], 0)
        self.assertEqual(segunda["highlight_limit"], 0)
        self.assertEqual(primeira["termos"], ["creatina", "notebook"])
        self.assertEqual(segunda["termos"], ["smartwatch", "creatina"])
        self.assertEqual(primeira["highlight_categories"], ["MLB432825"])
        self.assertEqual(segunda["highlight_categories"], [])


class WorkerHeartbeatTests(unittest.TestCase):
    def test_publica_configuracao_real_e_respeita_intervalo(self):
        start = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
        with mock.patch.multiple(
                worker_main,
                REPLENISHER_ORG_ID="org-1",
                REPLENISHER_TERMS=("smartphone", "monitor"),
                ML_DISCOVERY_TERMOS=["celular", "notebook", "tv"],
                ML_DISCOVERY_HIGHLIGHT_CATEGORIES=["MLB1", "MLB2"],
                ML_DISCOVERY_TERMS_PER_CYCLE=3,
                ML_DISCOVERY_HIGHLIGHT_CATEGORIES_PER_CYCLE=8,
                _ultimo_heartbeat=None), \
             mock.patch.object(worker_main.db, "register_audit") as audit:
            worker_main.registrar_heartbeat_se_necessario(now=start)
            worker_main.registrar_heartbeat_se_necessario(
                now=start + timedelta(minutes=1))
        audit.assert_called_once()
        metadata = audit.call_args.kwargs["metadata"]
        self.assertEqual(metadata["search_terms_count"], 2)
        self.assertEqual(metadata["ml_search_terms_count"], 3)
        self.assertEqual(metadata["ml_categories_count"], 2)
        self.assertEqual(metadata["ml_terms_per_cycle"], 3)
        self.assertTrue(metadata["category_diversity_enabled"])


class ReabastecedorMesclaPalavrasChaveTests(unittest.TestCase):
    """Laboratório de Captura (/campanhas): palavras-chave cadastradas pra
    aliexpress/shopee/magalu somam ao pool compartilhado que o reabastecedor
    usa pra capturar essas 3 fontes (REPLENISHER_TERMS continua o fallback)."""

    def test_mescla_palavras_das_tres_fontes_capturaveis_pelo_reabastecedor(self):
        def fake_keywords(organization_id, source_name):
            return {
                "aliexpress": ["fone bluetooth"],
                "shopee": ["air fryer"],
                "magalu": ["notebook"],
            }.get(source_name, [])

        with mock.patch.multiple(
                worker_main,
                REPLENISHER_ENABLED=True,
                REPLENISHER_ORG_ID="org-1",
                REPLENISHER_QUEUE_ID="queue-1",
                REPLENISHER_TERMS=("smartphone",)), \
             mock.patch.object(worker_main, "_ultimo_ciclo_reabastecedor", None), \
             mock.patch.object(worker_main, "_reabastecedor_thread", None), \
             mock.patch.object(worker_main.db, "get_discovery_keywords",
                               side_effect=fake_keywords), \
             mock.patch("threading.Thread") as thread_cls:
            thread_instance = mock.MagicMock()
            thread_cls.return_value = thread_instance
            worker_main.rodar_reabastecedor_se_configurado(
                now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        config_passada = thread_cls.call_args.kwargs["args"][0]
        self.assertEqual(
            set(config_passada.terms),
            {"smartphone", "fone bluetooth", "air fryer", "notebook"})
        thread_instance.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
