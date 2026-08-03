"""Testes stdlib do worker Topfy Affiliate OS.

Cobrem: score decomposto (pesos do spec somando 100, bloqueios), copy
determinística (nunca inventa fato), validar_copy (frases proibidas),
adapters simulados (nunca fingem sucesso), conectores AliExpress e
Mercado Livre (sem rede nos testes) e helpers do pipeline.
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

# Garante que o worker roda sem credenciais externas nos testes
for chave in ("ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET",
              "ALIEXPRESS_TRACKING_ID", "TELEGRAM_BOT_TOKEN",
              "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
              "OPENROUTER_API_KEY", "TOPFY_PRODUCTION"):
    os.environ.pop(chave, None)

from scoring import PESO_MAXIMO, calcular_score  # noqa: E402
from content import (gerar_copy, validar_copy, FRASES_PROIBIDAS,  # noqa: E402
                     aplicar_hashtags_produto, hashtags_produto,
                     escolher_imagem_limpa)
from adapters import (AmazonAdapter, WhatsAppAdapter, TikTokAdapter,  # noqa: E402
                      InstagramAdapter, YouTubeAdapter)
from connectors.aliexpress import AliExpressConnector, _parse_produto_api  # noqa: E402
from connectors.mercadolivre import MercadoLivreConnector  # noqa: E402

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

    def test_categoria_priorizada_reforca_peso_de_vendas(self):
        """Laboratório de Captura (/campanhas): categoria marcada como
        prioridade de mais vendidos dobra o teto da dimensão vendas sem
        mudar PESO_MAXIMO (spec aprovado) pras demais categorias."""
        produto = dict(PRODUTO_VERIFIED, sold_count=50000)
        normal = calcular_score(produto, LINK_VERIFIED)
        priorizado = calcular_score(
            produto, LINK_VERIFIED, prioritize_bestsellers=True)
        self.assertEqual(normal["vendas"], PESO_MAXIMO["vendas"])
        self.assertGreater(priorizado["vendas"], normal["vendas"])
        self.assertGreater(priorizado["score_total"], normal["score_total"])

    def test_sem_vendas_confirmadas_prioridade_nao_inventa_pontos(self):
        produto = dict(PRODUTO_VERIFIED, sold_count=None)
        score = calcular_score(
            produto, LINK_VERIFIED, prioritize_bestsellers=True)
        self.assertEqual(score["vendas"], 0.0)


class ContentTests(unittest.TestCase):
    def test_hashtags_descrevem_tipo_marca_e_compatibilidade(self):
        produto = {
            "title": "Carregador sem fio Samsung 15W para celular iPhone 15"
        }
        hashtags = hashtags_produto(produto)
        self.assertIn("#carregador", hashtags)
        self.assertIn("#semfio", hashtags)
        self.assertIn("#samsung", hashtags)
        self.assertIn("#celular", hashtags)
        self.assertIn("#iphone", hashtags)
        self.assertLessEqual(len(hashtags), 6)

    def test_hashtags_sao_adicionadas_uma_unica_vez(self):
        produto = {"title": "Celular iPhone Apple"}
        copia = {"body": "Oferta real"}
        uma_vez = aplicar_hashtags_produto(copia, produto)
        duas_vezes = aplicar_hashtags_produto(uma_vez, produto)
        self.assertEqual(uma_vez, duas_vezes)
        self.assertEqual(duas_vezes["body"].count("#iphone"), 1)

    def test_copy_fallback_ja_sai_com_hashtags_pesquisaveis(self):
        produto = dict(PRODUTO_VERIFIED, title="Mouse sem fio gamer Logitech")
        copy = gerar_copy(produto, "oferta-padrao", provider="fallback", seed=1)
        self.assertIn("#mouse", copy["body"])
        self.assertIn("#semfio", copy["body"])
        self.assertIn("#gamer", copy["body"])

    def test_copy_nunca_inventa_fato(self):
        for seed in range(10):
            copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao",
                              provider="fallback", seed=seed)
            self.assertIn("49,90", copy["body"] or "")  # formato BR: vírgula decimal
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

    def test_openrouter_ausente_cai_no_fallback_com_provider_auto(self):
        copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="auto", seed=7)
        self.assertEqual(copy["provider"], "fallback")

    def test_cupom_real_aparece_na_copy(self):
        produto = dict(PRODUTO_VERIFIED, coupons=[{"code": "OFERTAMELI15"}])
        copy = gerar_copy(produto, "oferta-padrao", provider="fallback", seed=1)
        self.assertIn("OFERTAMELI15", copy["body"])

    def test_sem_cupom_nao_aparece_linha_de_cupom(self):
        copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="fallback", seed=1)
        self.assertNotIn("cupom", copy["body"].lower())

    def test_vendidos_poucos_nao_aparece(self):
        produto = dict(PRODUTO_VERIFIED, sold_count=3)
        copy = gerar_copy(produto, "oferta-beneficios", provider="fallback", seed=1)
        self.assertNotIn("vendidos", copy["body"])

    def test_vendidos_muitos_aparece(self):
        produto = dict(PRODUTO_VERIFIED, sold_count=1200)
        copy = gerar_copy(produto, "oferta-beneficios", provider="fallback", seed=1)
        self.assertIn("1.200 vendidos", copy["body"])

    def test_preco_formato_brasileiro(self):
        copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="fallback", seed=1)
        self.assertIn("R$ 49,90", copy["body"])
        self.assertIn("R$ 99,90", copy["body"])

    def test_headline_no_padrao_produto_preco_hashtag(self):
        """Padrão pedido (referência BenchPromos): "🔥 <produto> - R$ X 🔥
        #anúncio" — preço e hashtag na própria linha do título."""
        copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="fallback", seed=1)
        self.assertIn("R$ 49,90", copy["headline"])
        self.assertIn("#anúncio", copy["headline"])

    def test_linha_desconto_calculada_dos_precos_reais(self):
        """"🏷 -X% (de R$ Y)" só aparece com os dois preços confirmados —
        X é calculado a partir deles, nunca inventado."""
        copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="fallback", seed=1)
        self.assertIn("🏷 -50% (de R$ 99,90)", copy["body"])

    def test_sem_preco_original_nao_gera_linha_de_desconto(self):
        produto = {k: v for k, v in PRODUTO_VERIFIED.items() if k != "original_price"}
        copy = gerar_copy(produto, "oferta-padrao", provider="fallback", seed=1)
        self.assertNotIn("🏷", copy["body"])

    def test_body_nao_repete_o_titulo_que_ja_esta_na_headline(self):
        """Regressão: o body chegou a repetir o título inteiro numa linha
        "🔴 ... 🔴" (derivada do próprio nome do produto) logo abaixo da
        headline, que já mostra o título completo — informação duplicada
        no mesmo post. O body só deve trazer o que falta (cupom/preço/
        desconto), nunca o nome do produto de novo."""
        produto = dict(PRODUTO_VERIFIED, title="Mouse Sem Fio K7, Branco")
        copy = gerar_copy(produto, "oferta-padrao", provider="fallback", seed=1)
        self.assertNotIn("🔴", copy["body"])
        self.assertNotIn("Mouse Sem Fio K7", copy["body"])

    def test_disclaimer_e_o_texto_de_apoio_ao_canal(self):
        copy = gerar_copy(PRODUTO_VERIFIED, "oferta-padrao", provider="fallback", seed=1)
        self.assertIn("ajuda o Canal Topfy", copy["disclaimer"])


class EscolherImagemLimpaTests(unittest.TestCase):
    """Checagem de imagem via IA de visão — opt-in (IMAGE_QUALITY_CHECK_
    ENABLED), best-effort: nunca deixa o produto sem imagem por causa
    disso, mesmo se a checagem falhar ou não estiver ligada."""

    PRODUTO = {
        "main_image_url": "https://img/principal.jpg",
        "image_urls": '["https://img/a.jpg", "https://img/b.jpg"]',
    }

    def test_desligado_por_padrao_devolve_principal_sem_chamar_ia(self):
        os.environ.pop("IMAGE_QUALITY_CHECK_ENABLED", None)
        checar = mock.Mock()
        resultado = escolher_imagem_limpa(self.PRODUTO, checar=checar)
        self.assertEqual(resultado, "https://img/principal.jpg")
        checar.assert_not_called()

    def test_ligado_escolhe_primeira_sem_marca(self):
        os.environ["IMAGE_QUALITY_CHECK_ENABLED"] = "true"
        try:
            # True = tem marca/texto (rejeitada); só "b" devolve False (limpa).
            def checar(url):
                return {"https://img/principal.jpg": True,
                        "https://img/a.jpg": True,
                        "https://img/b.jpg": False}[url]
            resultado = escolher_imagem_limpa(self.PRODUTO, checar=checar)
            self.assertEqual(resultado, "https://img/b.jpg")
        finally:
            os.environ.pop("IMAGE_QUALITY_CHECK_ENABLED", None)

    def test_ligado_mas_nenhuma_limpa_cai_na_principal(self):
        os.environ["IMAGE_QUALITY_CHECK_ENABLED"] = "1"
        try:
            resultado = escolher_imagem_limpa(self.PRODUTO, checar=lambda url: True)
            self.assertEqual(resultado, "https://img/principal.jpg")
        finally:
            os.environ.pop("IMAGE_QUALITY_CHECK_ENABLED", None)

    def test_falha_na_checagem_none_nao_bloqueia(self):
        os.environ["IMAGE_QUALITY_CHECK_ENABLED"] = "1"
        try:
            resultado = escolher_imagem_limpa(self.PRODUTO, checar=lambda url: None)
            self.assertEqual(resultado, "https://img/principal.jpg")
        finally:
            os.environ.pop("IMAGE_QUALITY_CHECK_ENABLED", None)

    def test_sem_imagem_nenhuma_devolve_none(self):
        os.environ.pop("IMAGE_QUALITY_CHECK_ENABLED", None)
        self.assertIsNone(escolher_imagem_limpa({}))


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

    def test_estoque_br_confirmado_por_campo_explicito_da_api(self):
        produto = _parse_produto_api({
            "product_id": "1005001",
            "product_title": "Mini PC",
            "ship_from_country_code": "BR",
        })
        self.assertEqual(produto["local_stock_country"], "BR")
        self.assertEqual(produto["local_stock_status"], "VERIFIED_API")

    def test_estoque_br_declarado_no_titulo_fica_identificado(self):
        produto = _parse_produto_api({
            "product_id": "1005002",
            "product_title": "Mini PC com estoque no Brasil",
        })
        self.assertEqual(produto["local_stock_country"], "BR")
        self.assertEqual(produto["local_stock_status"], "DECLARED_TITLE")

    def test_entrega_rapida_nao_e_tratada_como_estoque_local(self):
        produto = _parse_produto_api({
            "product_id": "1005003",
            "product_title": "Mini PC com entrega rápida",
            "delivery_time": "3 dias",
        })
        self.assertNotIn("local_stock_status", produto)

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

    def test_external_id_fallback_productids(self):
        """Short-link resolvido pode deixar o ID em productIds na query."""
        self.assertEqual(
            self.conector._external_id(
                "https://pt.aliexpress.com/item.html?spm=a2g0o&productIds=1005001234"),
            "1005001234")

    def test_external_id_fallback_sequencia_longa(self):
        """Fallback: sequência numérica de 8+ dígitos vira o ID do produto."""
        self.assertEqual(
            self.conector._external_id(
                "https://pt.aliexpress.com/item.html?spm=abc123456789"),
            "123456789")

    def test_shortlink_resolve_para_produto(self):
        """s.click/aliexpress resolvido para um produto -> extrai o ID."""
        url_produto = "https://pt.aliexpress.com/item/1005009876543.html"
        with mock.patch("connectors.aliexpress.resolve_shortlink",
                        return_value=url_produto):
            produto = self.conector.get_product(
                "https://s.click.aliexpress.com/e/_oHmAbCd")
        self.assertEqual(produto["external_product_id"], "1005009876543")
        self.assertEqual(produto["canonical_url"], url_produto)

    def test_shortlink_falha_resolucao_sem_credencial_nao_quebra(self):
        """Redirect indisponível sem credencial -> MANUAL/UNKNOWN sem rede
        (mesmo comportamento do modo manual normal, nunca quebra)."""
        with mock.patch("connectors.aliexpress.resolve_shortlink",
                        return_value=None):
            produto = self.conector.get_product(
                "https://s.click.aliexpress.com/e/_oQmAbCd")
        self.assertEqual(produto["method"], "MANUAL")
        self.assertEqual(produto["source_confidence"], "UNKNOWN")
        self.assertIsNone(produto["external_product_id"])

    def test_shortlink_falha_resolucao_com_credencial_levanta_erro(self):
        """Com API configurada, short-link irresolúvel levanta erro claro
        de ID não encontrado (não inventa ID nem chama rede com lixo)."""
        creds_fake = ("app_key", "app_secret", "tracking_id")
        with mock.patch("connectors.aliexpress.resolve_shortlink",
                        return_value=None), \
             mock.patch("connectors.aliexpress._credenciais",
                        return_value=creds_fake):
            with self.assertRaises(ValueError) as ctx:
                self.conector.get_product(
                    "https://s.click.aliexpress.com/e/_oQmAbCd")
        self.assertIn("ID do produto", str(ctx.exception))


class MercadoLivreConnectorTests(unittest.TestCase):
    def setUp(self):
        self.conector = MercadoLivreConnector()

    URL_BR = (
        "https://produto.mercadolivre.com.br/MLB-2837492291-fone-bluetooth-"
        "xyz-pro-_JM?matt_tool=xyz")

    ITEM_FIXTURE = {
        "id": "MLB2837492291",
        "title": "Fone Bluetooth XYZ Pro",
        "permalink": ("https://produto.mercadolivre.com.br/MLB-2837492291-"
                      "fone-bluetooth-xyz-pro-_JM"),
        "thumbnail": "https://http2.mlstatic.com/D_1-O.jpg",
        "pictures": [{"secure_url": "https://http2.mlstatic.com/D_2-O.jpg"}],
        "price": 99.9,
        "original_price": 199.8,
        "currency_id": "BRL",
        "sold_quantity": 500,
        "seller_id": 123456,
        "seller": {"id": 123456, "nickname": "LOJA-XYZ"},
        "category_id": "MLB1000",
    }

    def test_detect_url(self):
        self.assertTrue(self.conector.detect_url(self.URL_BR))
        self.assertTrue(
            self.conector.detect_url(
                "https://www.mercadolibre.com.ar/MLA-1234567890-foo"))
        self.assertTrue(
            self.conector.detect_url("https://meli.la/2qHBFJR"))
        self.assertFalse(
            self.conector.detect_url(
                "https://www.amazon.com.br/dp/B0XYZ"))

    def test_normalize_url_remove_query(self):
        self.assertEqual(
            self.conector.normalize_url(self.URL_BR),
            ("https://produto.mercadolivre.com.br/MLB-2837492291-fone-"
             "bluetooth-xyz-pro-_JM"))

    def test_external_id_da_url(self):
        self.assertEqual(self.conector._external_id(self.URL_BR),
                         "MLB2837492291")

    def test_external_id_prioriza_item_sobre_catalogo(self):
        """URL de catálogo (.../p/MLB<catalogo>) com item_id/wid na query
        ou no fragment tem que extrair o ID do ANÚNCIO, não o do
        catálogo — /items/ não aceita ID de catálogo."""
        url_catalogo = (
            "https://www.mercadolivre.com.br/creatina-monohidratada-pura-"
            "1kg-dark-lab-unidade-sem-sabor/p/MLB25929487"
            "?pdp_filters=item_id%3AMLB4812130742&matt_event_ts=123"
            "#polycard_client=recommendations_home_affiliate-profile"
            "&wid=MLB4812130742&sid=recos")
        self.assertEqual(self.conector._external_id(url_catalogo),
                         "MLB4812130742")

    def test_get_product_api_com_mock(self):
        """Dados reais da API oficial (fixture) — sem rede nos testes."""
        def fake_get_json(url, timeout=10, access_token=None):
            if "/items/" in url:
                return dict(self.ITEM_FIXTURE)
            if "/categories/" in url:
                return {"path_from_root": [
                    {"name": "Tecnologia"}, {"name": "Áudio"}]}
            raise AssertionError(f"URL inesperada: {url}")

        with mock.patch("connectors.mercadolivre._get_json",
                        side_effect=fake_get_json):
            produto = self.conector.get_product(self.URL_BR)

        self.assertEqual(produto["method"], "API")
        self.assertEqual(produto["source_confidence"], "VERIFIED")
        self.assertEqual(produto["external_product_id"], "MLB2837492291")
        self.assertEqual(produto["title"], "Fone Bluetooth XYZ Pro")
        self.assertEqual(produto["current_price"], 99.9)
        self.assertEqual(produto["original_price"], 199.8)
        self.assertEqual(produto["discount_percent"], 50.0)
        self.assertEqual(produto["seller_name"], "LOJA-XYZ")
        self.assertEqual(produto["sold_count"], 500)
        self.assertEqual(produto["currency"], "BRL")
        self.assertEqual(produto["category"], "Tecnologia > Áudio")
        self.assertNotIn("rating", produto)
        self.assertIsNone(produto["positive_feedback_percent"])

    def test_anuncio_inexistente_404(self):
        from urllib.error import HTTPError

        def fake_get_json(url, timeout=10, access_token=None):
            if "/items/" in url:
                err = HTTPError(url, 404, "Not Found", None, None)
                err.close()
                raise err
            return None

        with mock.patch("connectors.mercadolivre._get_json",
                        side_effect=fake_get_json):
            produto = self.conector.get_product(self.URL_BR)
        self.assertEqual(produto["source_confidence"], "NOT_AVAILABLE")
        self.assertIn("404", produto["aviso"])

    def test_gerar_link_levanta_aviso_manual(self):
        from connectors import CredencialNaoConfigurada
        with self.assertRaises(CredencialNaoConfigurada):
            self.conector.generate_affiliate_link(self.URL_BR)

    def test_health_check_api_indisponivel(self):
        from urllib.error import URLError
        with mock.patch("connectors.mercadolivre._get_json",
                        side_effect=URLError("sem rede")):
            health = self.conector.health_check()
        self.assertEqual(health["health_status"], "DOWN")
        self.assertEqual(health["credential_status"], "NOT_REQUIRED")

    def test_url_sem_id_levanta_erro(self):
        with self.assertRaises(ValueError):
            self.conector.get_product(
                "https://www.mercadolivre.com.br/sec/2x2x?quantity=1")

    def test_shortlink_resolve_para_produto(self):
        """meli.la resolvido para um anúncio -> extrai o ID normalmente."""
        def fake_get_json(url, timeout=10, access_token=None):
            if "/items/" in url:
                return dict(self.ITEM_FIXTURE)
            if "/categories/" in url:
                return {"path_from_root": [{"name": "Tecnologia"}]}
            raise AssertionError(f"URL inesperada: {url}")

        with mock.patch("connectors.mercadolivre._resolve_shortlink",
                        return_value=self.URL_BR), \
             mock.patch("connectors.mercadolivre._get_json",
                        side_effect=fake_get_json):
            produto = self.conector.get_product("https://meli.la/2qHBFJR")

        self.assertEqual(produto["external_product_id"], "MLB2837492291")
        self.assertEqual(produto["source_confidence"], "VERIFIED")

    def test_shortlink_resolve_para_perfil_levanta_erro_claro(self):
        """meli.la que aponta para um perfil/loja (sem ID de anúncio) tem
        que falhar com mensagem clara, não com um ID errado."""
        perfil_url = (
            "https://www.mercadolivre.com.br/social/cadu_21"
            "?matt_word=canaltopfy&matt_tool=11105536")
        with mock.patch("connectors.mercadolivre._resolve_shortlink",
                        return_value=perfil_url):
            with self.assertRaises(ValueError) as ctx:
                self.conector.get_product("https://meli.la/2qHBFJR")
        self.assertIn("perfil", str(ctx.exception))

    def test_shortlink_falha_resolucao_cai_no_erro_padrao(self):
        """Se o redirect não puder ser seguido (rede indisponível), o
        conector não quebra — cai no erro de 'ID não encontrado' de
        sempre, usando a própria URL curta."""
        with mock.patch("connectors.mercadolivre._resolve_shortlink",
                        return_value=None):
            with self.assertRaises(ValueError):
                self.conector.get_product("https://meli.la/2qHBFJR")

    def _fake_urlopen_capturando(self, capturado):
        class FakeResp:
            def __enter__(self_r):
                return self_r

            def __exit__(self_r, *exc):
                return False

            def read(self_r):
                return b'{"id": "MLB2837492291"}'

        def fake_urlopen(req, timeout=10):
            capturado.append(req)
            return FakeResp()
        return fake_urlopen

    def test_com_access_token_envia_authorization_bearer(self):
        """Conector construído com access_token manda Authorization:
        Bearer nas chamadas de leitura — tentativa de driblar o 403
        PolicyAgent que a API pública devolve pra tráfego anônimo."""
        capturado: list = []
        conector = MercadoLivreConnector(access_token="tok-123")
        with mock.patch("urllib.request.urlopen",
                        side_effect=self._fake_urlopen_capturando(capturado)):
            conector.get_product(self.URL_BR)
        self.assertTrue(capturado, "nenhuma chamada HTTP foi feita")
        primeira = capturado[0]
        self.assertEqual(primeira.get_header("Authorization"), "Bearer tok-123")

    def test_sem_access_token_nao_envia_authorization(self):
        """Sem token (ninguém conectou OAuth, ou expirou), continua 100%
        anônimo — nenhuma regressão no caminho de hoje."""
        capturado: list = []
        with mock.patch("urllib.request.urlopen",
                        side_effect=self._fake_urlopen_capturando(capturado)):
            self.conector.get_product(self.URL_BR)
        self.assertTrue(capturado, "nenhuma chamada HTTP foi feita")
        primeira = capturado[0]
        self.assertIsNone(primeira.get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
