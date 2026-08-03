"""Testes Fase A do worker — filas, grupos, CTAs, textos por loja e
imagem real para o post. Sem rede e sem credenciais nos testes.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

for chave in ("ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET",
              "ALIEXPRESS_TRACKING_ID", "TELEGRAM_BOT_TOKEN",
              "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
              "OPENROUTER_API_KEY", "TOPFY_PRODUCTION"):
    os.environ.pop(chave, None)

from content import gerar_copy  # noqa: E402
import db  # noqa: E402
import pipeline  # noqa: E402

PRODUTO = {
    "id": "p1",
    "title": "Fone Bluetooth XYZ",
    "current_price": 49.9,
    "original_price": 99.9,
    "sold_count": 1200,
    "rating": 4.7,
    "commission_percent": 8.5,
    "source_name": "aliexpress",
}


class NormalizarProductRowTests(unittest.TestCase):
    """Regressão: um product_row vindo do banco (db.get_product) usa
    nomes de COLUNA (discounted_price_brl, sales_count, commission_pct,
    image_url, confidence) — scoring.py e content.py leem nomes do
    CONECTOR (current_price, sold_count, commission_percent,
    main_image_url, source_confidence). Sem normalizar_product_row,
    compute_score bloqueava por "sem preço confirmado" (score ~0) e
    generate_copies caía no fallback "Ficha ainda sem fatos confirmados"
    mesmo com preço/venda reais salvos no banco."""

    PRODUCT_ROW_BANCO = {
        "id": "p1",
        "title": "Fone Bluetooth XYZ",
        "discounted_price_brl": 41.03,
        "original_price_brl": 82.07,
        "sales_count": 526,
        "commission_pct": 8.5,
        "image_url": "https://img.exemplo/x.jpg",
        "confidence": "VERIFIED",
        "source_name": "aliexpress",
    }

    def test_normaliza_sem_sobrescrever_valor_ja_no_formato_conector(self):
        normalizado = pipeline.normalizar_product_row(self.PRODUCT_ROW_BANCO)
        self.assertEqual(normalizado["current_price"], 41.03)
        self.assertEqual(normalizado["original_price"], 82.07)
        self.assertEqual(normalizado["sold_count"], 526)
        self.assertEqual(normalizado["commission_percent"], 8.5)
        self.assertEqual(normalizado["main_image_url"], "https://img.exemplo/x.jpg")
        self.assertEqual(normalizado["source_confidence"], "VERIFIED")
        # não sobrescreve se já vier no formato do conector
        ja_conector = {"current_price": 10.0, "discounted_price_brl": 999.0}
        self.assertEqual(
            pipeline.normalizar_product_row(ja_conector)["current_price"], 10.0)

    def test_compute_score_com_product_row_do_banco_nao_bloqueia_por_preco(self):
        link = {"verification_status": "VERIFIED"}
        score = pipeline.compute_score(self.PRODUCT_ROW_BANCO, link)
        self.assertNotIn("Sem preço confirmado — não é possível aprovar.",
                         score["bloqueios"])
        self.assertGreater(score["score_total"], 0)

    def test_generate_copies_com_product_row_do_banco_mostra_preco_real(self):
        normalizado = pipeline.normalizar_product_row(self.PRODUCT_ROW_BANCO)
        copias = pipeline.generate_copies(normalizado, seed=1)
        texto = pipeline.montar_copy_text(copias[0])
        self.assertIn("41", texto)
        self.assertNotIn("Ficha ainda sem fatos confirmados", texto)
        self.assertNotIn("preço a confirmar", texto)

    def test_normaliza_metadado_de_estoque_local_do_card(self):
        row = {
            **self.PRODUCT_ROW_BANCO,
            "card_config": {
                "theme": "navy",
                "local_stock": {
                    "country": "BR",
                    "status": "DECLARED_TITLE",
                    "evidence": "Informado no título do anúncio",
                },
            },
        }
        normalizado = pipeline.normalizar_product_row(row)
        self.assertEqual(normalizado["local_stock_country"], "BR")
        self.assertEqual(normalizado["local_stock_status"], "DECLARED_TITLE")


class EstoqueLocalCopyTests(unittest.TestCase):
    def test_copy_destaca_declaracao_do_anuncio_com_ressalva(self):
        produto = {
            **PRODUTO,
            "local_stock_country": "BR",
            "local_stock_status": "DECLARED_TITLE",
        }
        copia = gerar_copy(produto, provider="fallback", seed=1)
        self.assertIn("ESTOQUE NO BRASIL", copia["body"])
        self.assertIn("informado no anúncio", copia["body"])

    def test_copy_comum_nao_inventa_estoque_local(self):
        copia = gerar_copy(PRODUTO, provider="fallback", seed=1)
        self.assertNotIn("ESTOQUE NO BRASIL", copia["body"])


class DestaqueImperdivelCopyTests(unittest.TestCase):
    def test_mais_de_cinquenta_por_cento_fica_muito_destacado(self):
        produto = {
            **PRODUTO,
            "deal_highlight_reason": "DISCOUNT_OVER_50",
            "deal_highlight": {"reason": "DISCOUNT_OVER_50"},
        }
        copia = gerar_copy(produto, provider="fallback", seed=1)
        self.assertIn("🚨🔥 IMPERDÍVEL 🔥🚨", copia["headline"])
        self.assertIn("MAIS DE 50% DE DESCONTO CONFIRMADO", copia["body"])

    def test_desconto_entre_50_e_51_nao_arredonda_para_50_no_destaque(self):
        produto = {
            **PRODUTO,
            "current_price": 49.5,
            "original_price": 100,
            "deal_highlight_reason": "DISCOUNT_OVER_50",
            "deal_highlight": {"reason": "DISCOUNT_OVER_50"},
        }
        copia = gerar_copy(produto, provider="fallback", seed=1)
        self.assertIn("-50,5%", copia["body"])

    def test_menor_preco_mostra_periodo_confirmado(self):
        produto = {
            **PRODUTO,
            "deal_highlight_reason": "RECENT_LOW",
            "deal_highlight": {"reason": "RECENT_LOW", "lookback_days": 30},
        }
        copia = gerar_copy(produto, provider="fallback", seed=1)
        self.assertIn("IMPERDÍVEL", copia["headline"])
        self.assertIn("MENOR PREÇO CONFIRMADO DOS ÚLTIMOS 30 DIAS", copia["body"])

    def test_sem_evidencia_nao_usa_imperdivel(self):
        copia = gerar_copy(PRODUTO, provider="fallback", seed=1)
        self.assertNotIn("IMPERDÍVEL", copia["headline"])


class FakeTable:
    """Encadeamento de query PostgREST mínimo para os testes."""

    def __init__(self, rows=None, single=None):
        self.rows = rows or []
        self.single = single
        self.inserts: list[dict] = []
        self.updates: list[dict] = []
        self.calls: list[tuple] = []

    def select(self, *a, **k):
        self.calls.append(("select", a, k))
        return self

    def eq(self, *a, **k):
        self.calls.append(("eq", a, k))
        return self

    def neq(self, *a, **k):
        self.calls.append(("neq", a, k))
        return self

    def lte(self, *a, **k):
        self.calls.append(("lte", a, k))
        return self

    def gte(self, *a, **k):
        self.calls.append(("gte", a, k))
        return self

    def order(self, *a, **k):
        self.calls.append(("order", a, k))
        return self

    def limit(self, *a, **k):
        self.calls.append(("limit", a, k))
        return self

    def maybe_single(self):
        self.calls.append(("maybe_single", (), {}))
        return self

    def is_(self, *a, **k):
        self.calls.append(("is_", a, k))
        return self

    @property
    def not_(self):
        self.calls.append(("not_", (), {}))
        return self

    def update(self, fields):
        self.updates.append(fields)
        return self

    def insert(self, fields):
        self.inserts.append(fields)
        return self

    def execute(self):
        resp = mock.MagicMock()
        resp.data = self.single if self.single is not None else self.rows
        return resp


class TextosPorLojaTests(unittest.TestCase):
    def test_aliexpress_na_headline(self):
        copy = gerar_copy(PRODUTO, "oferta-padrao", provider="fallback",
                          seed=1, loja="aliexpress")
        self.assertIn("AliExpress", copy["headline"])

    def test_mercadolivre_na_headline(self):
        copy = gerar_copy(PRODUTO, "oferta-padrao", provider="fallback",
                          seed=2, loja="mercadolivre")
        self.assertIn("Mercado Livre", copy["headline"])

    def test_amazon_na_headline(self):
        copy = gerar_copy(PRODUTO, "oferta-padrao", provider="fallback",
                          seed=3, loja="amazon")
        self.assertIn("Amazon", copy["headline"])

    def test_loja_desconhecida_sem_rotulo(self):
        copy = gerar_copy(PRODUTO, "oferta-padrao", provider="fallback",
                          seed=3, loja="shopee")
        self.assertNotIn("Amazon", copy["headline"])
        self.assertNotIn("AliExpress", copy["headline"])

    def test_sem_loja_nao_muda_comportamento(self):
        copy = gerar_copy(PRODUTO, "oferta-padrao", provider="fallback", seed=4)
        self.assertNotIn("Mercado Livre", copy["headline"])

    def test_mesma_seed_reproducivel(self):
        a = gerar_copy(PRODUTO, "oferta-curta", provider="fallback",
                       seed=9, loja="aliexpress")
        b = gerar_copy(PRODUTO, "oferta-curta", provider="fallback",
                       seed=9, loja="aliexpress")
        self.assertEqual(a, b)

    def test_generate_copies_passa_a_loja(self):
        produto = dict(PRODUTO, source_name="mercadolivre")
        copias = pipeline.generate_copies(produto, seed=5)
        self.assertEqual(len(copias), 3)
        self.assertTrue(any("Mercado Livre" in c["headline"] for c in copias))


class CtaTests(unittest.TestCase):
    def test_fallback_sem_frases_cadastradas(self):
        with mock.patch.object(db, "get_cta_phrases", return_value=[]):
            cta = pipeline.sortear_cta("org-1", seed=42)
        self.assertIn(cta, pipeline.CTA_PADRAO)

    def test_sorteia_de_frases_cadastradas(self):
        frases = [{"phrase": "Aproveita essa oferta"},
                  {"phrase": "Desconto confirmado na loja"}]
        with mock.patch.object(db, "get_cta_phrases", return_value=frases):
            cta = pipeline.sortear_cta("org-1", seed=1)
        self.assertIn(cta, [f["phrase"] for f in frases])

    def test_sem_org_usa_padrao(self):
        with mock.patch.object(db, "get_cta_phrases", return_value=[]):
            cta = pipeline.sortear_cta(None, seed=7)
        self.assertIn(cta, pipeline.CTA_PADRAO)


class ImagemPostTests(unittest.TestCase):
    def test_extrai_og_image(self):
        html = ("<html><head><meta property=\"og:image\" "
                "content=\"https://img.example.com/foto.jpg\"></head></html>")
        with mock.patch("urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.headers.get_content_charset.return_value = "utf-8"
            resp.read.return_value = html.encode()
            urlopen.return_value.__enter__.return_value = resp
            imagem = pipeline.extrair_og_image("https://loja.exemplo/item/1")
        self.assertEqual(imagem, "https://img.example.com/foto.jpg")

    def test_pagina_sem_og_image_retorna_none(self):
        html = "<html><head></head><body>oi</body></html>"
        with mock.patch("urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.headers.get_content_charset.return_value = "utf-8"
            resp.read.return_value = html.encode()
            urlopen.return_value.__enter__.return_value = resp
            self.assertIsNone(pipeline.extrair_og_image("https://loja.exemplo"))
        urlopen.assert_called_once()

    def test_erro_de_rede_retorna_none(self):
        from urllib.error import URLError
        with mock.patch("urllib.request.urlopen",
                        side_effect=URLError("sem rede")):
            self.assertIsNone(pipeline.extrair_og_image("https://loja.exemplo"))

    def test_imagem_para_post_prioriza_image_url(self):
        produto = {"image_url": "https://img1/x.jpg",
                   "source_url": "https://loja.exemplo"}
        with mock.patch.object(pipeline, "extrair_og_image",
                               return_value="https://img2/y.jpg"):
            self.assertEqual(pipeline.imagem_para_post(produto),
                             "https://img1/x.jpg")

    def test_imagem_para_post_captura_og_na_hora(self):
        produto = {"image_url": None, "source_url": "https://loja.exemplo/item"}
        with mock.patch.object(pipeline, "extrair_og_image",
                               return_value="https://img2/y.jpg"):
            self.assertEqual(pipeline.imagem_para_post(produto),
                             "https://img2/y.jpg")

    def test_sem_source_url_nao_tenta(self):
        with mock.patch.object(pipeline, "extrair_og_image") as mock_extrai:
            pipeline.imagem_para_post({"image_url": None, "source_url": None})
        mock_extrai.assert_not_called()


class ImagemCupomTests(unittest.TestCase):
    """Campanha de cupom (coupon_discovery.py) usa o selo oficial da loja
    em vez da foto de produto — só quando o item É um cupom."""

    def test_campanha_de_cupom_usa_selo_da_loja(self):
        produto = {
            "source_name": "shopee",
            "image_url": "https://img/produto-generico.jpg",
            "card_config": {"coupon_offer": {"coupon_code": "ABC123"}},
        }
        with mock.patch.dict(os.environ, {
                "CANALTOPFY_PUBLIC_BASE_URL": "https://web.exemplo"}):
            self.assertEqual(
                pipeline.imagem_cupom_url(produto),
                "https://web.exemplo/cupons/shopee.png")
            self.assertEqual(
                pipeline.imagem_para_post(produto),
                "https://web.exemplo/cupons/shopee.png")

    def test_produto_comum_nao_usa_selo_de_cupom(self):
        produto = {
            "source_name": "shopee",
            "image_url": "https://img/produto-real.jpg",
            "card_config": {"deal_highlight": {"level": "MUST_SEE"}},
        }
        with mock.patch.dict(os.environ, {
                "CANALTOPFY_PUBLIC_BASE_URL": "https://web.exemplo"}):
            self.assertIsNone(pipeline.imagem_cupom_url(produto))
            self.assertEqual(
                pipeline.imagem_para_post(produto), "https://img/produto-real.jpg")

    def test_sem_base_url_configurada_cai_na_foto_normal(self):
        produto = {
            "source_name": "shopee",
            "image_url": "https://img/produto-real.jpg",
            "card_config": {"coupon_offer": {"coupon_code": "ABC123"}},
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(pipeline.imagem_cupom_url(produto))
            self.assertEqual(
                pipeline.imagem_para_post(produto), "https://img/produto-real.jpg")

    def test_fonte_sem_selo_cadastrado_cai_na_foto_normal(self):
        produto = {
            "source_name": "aliexpress",
            "image_url": "https://img/produto-real.jpg",
            "card_config": {"coupon_offer": {"coupon_code": "ABC123"}},
        }
        with mock.patch.dict(os.environ, {
                "CANALTOPFY_PUBLIC_BASE_URL": "https://web.exemplo"}):
            self.assertIsNone(pipeline.imagem_cupom_url(produto))
            self.assertEqual(
                pipeline.imagem_para_post(produto), "https://img/produto-real.jpg")


class PublishToTelegramUsaFotoRealTests(unittest.TestCase):
    """Regressão: publicação manda a foto real do produto direto na
    mensagem — sem card renderizado (/og/card) por cima, formato mais
    simples usado pela concorrência (referência: post benchmark do GTA VI:
    foto real + legenda em texto). O link mostrado/clicado é o link final
    de afiliado (loja real), não mais o redirect /r/<id> do Topfy — pedido
    explícito do usuário."""

    CAMPANHA = {"id": "c1", "product_id": "p1", "status": "APPROVED",
                "organization_id": "org1", "slug": "c1"}

    def _publicar(self, produto, **kw):
        capturado = {}

        def fake_publicar(*, copy, chat_id, redirect_url, image_url, **_):
            capturado["image_url"] = image_url
            capturado["redirect_url"] = redirect_url
            return {"external_message_id": "999"}

        with mock.patch.object(db, "get_campaign", return_value=self.CAMPANHA), \
             mock.patch.object(db, "get_product", return_value=produto), \
             mock.patch.object(db, "has_active_publication", return_value=False), \
             mock.patch.object(db, "create_publication",
                               return_value={"id": "pub1"}), \
             mock.patch.object(db, "mark_publication_result"), \
             mock.patch.object(db, "register_audit"), \
             mock.patch.object(db, "get_cta_phrases", return_value=[]), \
             mock.patch.object(pipeline, "_load_content",
                               return_value={"headline": "h", "body": "b",
                                              "cta": "Ver", "disclaimer": "d"}), \
             mock.patch("publishers.telegram.publicar_oferta_telegram",
                        side_effect=fake_publicar), \
             mock.patch.object(db, "update_campaign"):
            pipeline.publish_to_telegram("c1", "content1", chat_id="-100123", **kw)
        return capturado

    def test_image_url_e_a_foto_real_nao_o_card(self):
        produto = {**PRODUTO, "image_url": "https://ae-cdn.example/foto-real.jpg",
                   "affiliate_link": "https://s.click.aliexpress.com/e/_real"}
        capturado = self._publicar(produto)
        self.assertEqual(capturado["image_url"], produto["image_url"])
        self.assertNotIn("/og/card/", capturado["image_url"])

    def test_link_mostrado_e_o_afiliado_final_nao_o_redirect_r(self):
        produto = {**PRODUTO, "affiliate_link": "https://s.click.aliexpress.com/e/_real"}
        capturado = self._publicar(produto)
        self.assertEqual(capturado["redirect_url"], produto["affiliate_link"])
        self.assertNotIn("/r/", capturado["redirect_url"])

    def test_sem_link_de_afiliado_nao_publica(self):
        produto = {**PRODUTO, "affiliate_link": None}
        with self.assertRaises(ValueError) as ctx:
            self._publicar(produto)
        self.assertIn("link de afiliado", str(ctx.exception))

    def test_link_pendente_nao_publica(self):
        produto = {**PRODUTO, "affiliate_link": "PENDING_OFFICIAL_TOOL"}
        with self.assertRaises(ValueError):
            self._publicar(produto)


class JanelaAtivaTests(unittest.TestCase):
    def _fila(self, **kw):
        return {"id": "f1", "window_start": None, "window_end": None, **kw}

    def test_janela_livre_sempre_ativa(self):
        self.assertTrue(pipeline._janela_ativa(self._fila(), datetime.now(timezone.utc)))

    def test_converte_utc_para_brasilia(self):
        # 17:00 UTC = 14:00 em Brasília (UTC-3), dentro de 09:00–18:00.
        fila = self._fila(window_start="09:00:00", window_end="18:00:00")
        decisao = pipeline._janela_ativa(fila, datetime(2026, 8, 2, 17, 0, tzinfo=timezone.utc))
        self.assertTrue(decisao)

    def test_fora_da_janela_em_brasilia(self):
        # 23:00 UTC = 20:00 BRT, fora de 09:00–18:00.
        fila = self._fila(window_start="09:00:00", window_end="18:00:00")
        decisao = pipeline._janela_ativa(fila, datetime(2026, 8, 2, 23, 0, tzinfo=timezone.utc))
        self.assertFalse(decisao)

    def test_momento_sem_tz_tratado_como_utc(self):
        fila = self._fila(window_start="09:00:00", window_end="18:00:00")
        decisao = pipeline._janela_ativa(fila, datetime(2026, 8, 2, 8, 0))
        self.assertFalse(decisao)  # 08:00 UTC = 05:00 BRT, fora da janela

    def test_janela_noturna_cruza_meia_noite(self):
        fila = self._fila(window_start="22:00:00", window_end="06:00:00")
        # 03:00 UTC = 00:00 BRT, dentro da noturna 22:00–06:00.
        self.assertTrue(pipeline._janela_ativa(fila, datetime(2026, 8, 2, 3, 0, tzinfo=timezone.utc)))
        # 14:00 UTC = 11:00 BRT, fora.
        self.assertFalse(pipeline._janela_ativa(fila, datetime(2026, 8, 2, 14, 0, tzinfo=timezone.utc)))


class GetLastDispatchedAtTests(unittest.TestCase):
    """Regressão: .neq('dispatched_at', None) manda a STRING "None" pro
    Postgres (coluna é timestamptz) — só .not_.is_(col, 'null') funciona.
    Isso só quebrava contra um Postgres de verdade; os testes de
    dispatch_queues mockam get_last_dispatched_at inteiro, então nunca
    pegavam esse bug — por isso o teste aqui olha a query construída."""

    def test_usa_not_is_null_em_vez_de_neq_none(self):
        tabela = FakeTable(rows=[{"dispatched_at": "2026-08-02T12:00:00+00:00"}])
        client = mock.MagicMock()
        client.table.return_value = tabela
        with mock.patch.object(db, "_get", return_value=client):
            resultado = db.get_last_dispatched_at("f1")
        self.assertEqual(resultado, "2026-08-02T12:00:00+00:00")
        nomes_chamados = [nome for nome, _a, _k in tabela.calls]
        self.assertIn("not_", nomes_chamados)
        self.assertIn("is_", nomes_chamados)
        self.assertNotIn("neq", nomes_chamados,
                         "neq('dispatched_at', None) quebra no Postgres real")
        chamada_is = next(c for c in tabela.calls if c[0] == "is_")
        self.assertEqual(chamada_is[1], ("dispatched_at", "null"))

    def test_sem_despacho_anterior_devolve_none(self):
        tabela = FakeTable(rows=[])
        client = mock.MagicMock()
        client.table.return_value = tabela
        with mock.patch.object(db, "_get", return_value=client):
            self.assertIsNone(db.get_last_dispatched_at("f1"))


class DispatchQueuesTests(unittest.TestCase):
    def _fila(self, **kwargs):
        fila = {"id": "f1", "interval_minutes": 5,
                "window_start": None, "window_end": None}
        fila.update(kwargs)
        return fila

    def test_fora_da_janela_nao_despacha(self):
        fila = self._fila(window_start="09:00:00", window_end="18:00:00")
        agora = datetime(2026, 8, 2, 23, 0, tzinfo=timezone.utc)  # 20:00 BRT
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_pending_queue_items") as itens_mock:
                pipeline.dispatch_queues(now=agora)
                itens_mock.assert_not_called()

    def test_dentro_da_janela_em_brasilia_despacha(self):
        # interval 09:00–18:00 (BRT): 17:00 UTC = 14:00 BRT, dentro.
        fila = self._fila(window_start="09:00:00", window_end="18:00:00")
        itens = [{"id": "i1", "campaign_id": "c1", "content_id": "co1",
                  "attempts": 0}]
        grupos = [{"group_id": "g1"}]
        agora = datetime(2026, 8, 2, 17, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_last_dispatched_at",
                                   return_value=None):
                with mock.patch.object(db, "get_pending_queue_items",
                                       return_value=itens):
                    with mock.patch.object(db, "get_queue_groups",
                                           return_value=grupos):
                        with mock.patch.object(db, "mark_queue_item") as marca:
                            with mock.patch.object(
                                    pipeline, "publish_to_telegram",
                                    return_value={"publication_id": "pub1"}) as pub:
                                despachados = pipeline.dispatch_queues(now=agora)
        self.assertEqual(pub.call_count, 1)
        self.assertEqual(len(despachados), 1)

    def test_pula_categoria_igual_e_publica_alternativa(self):
        fila = self._fila(organization_id="org1")
        itens = [
            {"id": "i1", "campaign_id": "c1", "content_id": "co1",
             "attempts": 0, "campaign": {"product": {
                 "category": "Eletrônicos", "title": "Carregador USB-C"}}},
            {"id": "i2", "campaign_id": "c2", "content_id": "co2",
             "attempts": 0, "campaign": {"product": {
                 "category": "Informática", "title": "Monitor 24"}}},
        ]
        with mock.patch.object(db, "get_active_queues", return_value=[fila]), \
             mock.patch.object(db, "get_last_dispatched_at", return_value=None), \
             mock.patch.object(db, "get_pending_queue_items", return_value=itens), \
             mock.patch.object(db, "get_last_done_queue_product", return_value={
                 "category": "Acessórios", "title": "Carregador rápido"}), \
             mock.patch.object(db, "get_queue_groups", return_value=[{"group_id": "g1"}]), \
             mock.patch.object(db, "mark_queue_item") as mark, \
             mock.patch.object(pipeline, "publish_to_telegram",
                               return_value={"publication_id": "p1"}) as publish:
            pipeline.dispatch_queues(now=datetime(2026, 8, 2, 17, tzinfo=timezone.utc))
        self.assertEqual(publish.call_args.args[:2], ("c2", "co2"))
        self.assertEqual(mark.call_args_list[0].args[0], "i2")

    def test_aguarda_quando_so_ha_mesma_categoria(self):
        fila = self._fila(organization_id="org1")
        item = {"id": "i1", "campaign_id": "c1", "content_id": "co1",
                "attempts": 0, "campaign": {"product": {
                    "category": "Eletrônicos", "title": "Carregador USB-C"}}}
        with mock.patch.object(db, "get_active_queues", return_value=[fila]), \
             mock.patch.object(db, "get_last_dispatched_at", return_value=None), \
             mock.patch.object(db, "get_pending_queue_items", return_value=[item]), \
             mock.patch.object(db, "get_last_done_queue_product", return_value={
                 "category": "Acessórios", "title": "Carregador rápido"}), \
             mock.patch.object(db, "get_queue_groups", return_value=[{"group_id": "g1"}]), \
             mock.patch.object(db, "register_audit"), \
             mock.patch.object(pipeline, "publish_to_telegram") as publish:
            result = pipeline.dispatch_queues(
                now=datetime(2026, 8, 2, 17, tzinfo=timezone.utc))
        self.assertEqual(result, [])
        publish.assert_not_called()

    def test_sem_janela_despacha_de_madrugada_24h(self):
        """Fila sem window_start/window_end (24h) tem que despachar em
        qualquer horário — inclusive de madrugada, sem janela nenhuma
        bloqueando. Cobre o caso de posts contínuos 24h a cada 5min."""
        fila = self._fila()  # window_start/window_end None por padrão
        itens = [{"id": "i1", "campaign_id": "c1", "content_id": "co1",
                  "attempts": 0}]
        grupos = [{"group_id": "g1"}]
        madrugada = datetime(2026, 8, 2, 6, 0, 0, tzinfo=timezone.utc)  # 03:00 BRT
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_last_dispatched_at",
                                   return_value=None):
                with mock.patch.object(db, "get_pending_queue_items",
                                       return_value=itens):
                    with mock.patch.object(db, "get_queue_groups",
                                           return_value=grupos):
                        with mock.patch.object(db, "mark_queue_item"):
                            with mock.patch.object(
                                    pipeline, "publish_to_telegram",
                                    return_value={"publication_id": "pub1"}) as pub:
                                despachados = pipeline.dispatch_queues(now=madrugada)
        self.assertEqual(pub.call_count, 1)
        self.assertEqual(len(despachados), 1)

    def test_intervalo_respeitado(self):
        fila = self._fila()
        agora = datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc)
        ultimo = "2026-08-02T13:59:30+00:00"  # 30s atrás < 5min
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_last_dispatched_at",
                                   return_value=ultimo):
                with mock.patch.object(db, "get_pending_queue_items") as itens:
                    pipeline.dispatch_queues(now=agora)
                    itens.assert_not_called()

    def test_publica_em_todos_os_grupos_e_marca_done(self):
        fila = self._fila()
        itens = [{"id": "i1", "campaign_id": "c1", "content_id": "co1",
                  "attempts": 0}]
        grupos = [{"group_id": "g1"}, {"group_id": "g2"}]
        agora = datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_last_dispatched_at",
                                   return_value=None):
                with mock.patch.object(db, "get_pending_queue_items",
                                       return_value=itens):
                    with mock.patch.object(db, "get_queue_groups",
                                           return_value=grupos):
                        with mock.patch.object(db, "mark_queue_item") as marca:
                            with mock.patch.object(
                                    pipeline, "publish_to_telegram",
                                    return_value={"publication_id": "pub1"}) as pub:
                                despachados = pipeline.dispatch_queues(now=agora)
        self.assertEqual(pub.call_count, 2)
        self.assertEqual(len(despachados), 1)
        states = [m.args[1]["status"] for m in marca.call_args_list]
        self.assertIn("DISPATCHED", states)
        self.assertIn("DONE", states)

    def test_item_sem_content_id_cancela(self):
        fila = self._fila()
        itens = [{"id": "i1", "campaign_id": "c1", "content_id": None,
                  "attempts": 0}]
        grupos = [{"group_id": "g1"}]
        agora = datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_last_dispatched_at",
                                   return_value=None):
                with mock.patch.object(db, "get_pending_queue_items",
                                       return_value=itens):
                    with mock.patch.object(db, "get_queue_groups",
                                           return_value=grupos):
                        with mock.patch.object(db, "mark_queue_item") as marca:
                            pipeline.dispatch_queues(now=agora)
        cancelados = [m.args[1] for m in marca.call_args_list
                      if m.args[0] == "i1"]
        self.assertEqual(cancelados[0]["status"], "CANCELLED")

    def test_ja_publicada_e_tratada_como_sucesso(self):
        fila = self._fila()
        itens = [{"id": "i1", "campaign_id": "c1", "content_id": "co1",
                  "attempts": 0}]
        grupos = [{"group_id": "g1"}]
        agora = datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_last_dispatched_at",
                                   return_value=None):
                with mock.patch.object(db, "get_pending_queue_items",
                                       return_value=itens):
                    with mock.patch.object(db, "get_queue_groups",
                                           return_value=grupos):
                        with mock.patch.object(db, "mark_queue_item") as marca:
                            with mock.patch.object(
                                    pipeline, "publish_to_telegram",
                                    side_effect=ValueError(
                                        "já foi publicada neste grupo")):
                                despachados = pipeline.dispatch_queues(now=agora)
        self.assertEqual(len(despachados), 1)
        states = [m.args[1]["status"] for m in marca.call_args_list]
        self.assertIn("DONE", states)

    def test_falha_volta_pending_e_cancela_no_limite(self):
        fila = self._fila()
        itens = [{"id": "i1", "campaign_id": "c1", "content_id": "co1",
                  "attempts": 2}]
        grupos = [{"group_id": "g1"}]
        agora = datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(db, "get_active_queues", return_value=[fila]):
            with mock.patch.object(db, "get_last_dispatched_at",
                                   return_value=None):
                with mock.patch.object(db, "get_pending_queue_items",
                                       return_value=itens):
                    with mock.patch.object(db, "get_queue_groups",
                                           return_value=grupos):
                        with mock.patch.object(db, "mark_queue_item") as marca:
                            with mock.patch.object(
                                    pipeline, "publish_to_telegram",
                                    side_effect=RuntimeError("FloodWait")):
                                pipeline.dispatch_queues(now=agora)
        final = [m.args[1] for m in marca.call_args_list
                 if m.args[0] == "i1"][-1]
        self.assertEqual(final["status"], "CANCELLED")
        self.assertEqual(final["attempts"], 3)


class RegenerateCopiesTests(unittest.TestCase):
    def test_regenera_campanha_com_nova_versao(self):
        campanha = {"id": "c1", "organization_id": "org1",
                    "product_id": "p1", "status": "APPROVED"}
        produto = dict(PRODUTO)

        contents = FakeTable(rows=[{"version": 2}])
        client = mock.MagicMock()
        client.table.side_effect = lambda nome: contents if nome == "contents" else FakeTable()
        _get = mock.patch.object(db, "_get", return_value=client)
        with _get, mock.patch.object(db, "get_campaign",
                                     return_value=campanha), \
                mock.patch.object(db, "get_product", return_value=produto), \
                mock.patch.object(db, "update_campaign") as upd, \
                mock.patch.object(db, "register_audit") as audit:
            resultado = pipeline.regenerate_copies("c1", seed=10)

        self.assertEqual(resultado["total"], 3)
        self.assertEqual(resultado["version"], 3)
        self.assertEqual(len(contents.inserts), 3)
        self.assertTrue(all(i["version"] == 3 for i in contents.inserts))
        upd.assert_called_once_with("c1", {"status": "REVIEW_REQUIRED"})
        audit.assert_called_once()

    def test_campanha_inexistente_levanta(self):
        with mock.patch.object(db, "get_campaign", return_value=None):
            with self.assertRaises(ValueError):
                pipeline.regenerate_copies("c1")


class GetMlAccessTokenTests(unittest.TestCase):
    """access_token do Mercado Livre já conectado (ml_credentials) — só
    devolvido se ainda não tiver expirado. Sem refresh (best-effort)."""

    def _fake_client(self, single):
        client = mock.MagicMock()
        client.table.return_value = FakeTable(single=single)
        return client

    def test_token_valido_e_devolvido(self):
        client = self._fake_client(
            {"access_token": "tok-abc", "expires_at": "2999-01-01T00:00:00+00:00"})
        with mock.patch.object(db, "_get", return_value=client):
            self.assertEqual(db.get_ml_access_token("org-1"), "tok-abc")

    def test_token_expirado_devolve_none(self):
        client = self._fake_client(
            {"access_token": "tok-abc", "expires_at": "2000-01-01T00:00:00+00:00"})
        with mock.patch.object(db, "_get", return_value=client):
            self.assertIsNone(db.get_ml_access_token("org-1"))

    def test_sem_credencial_devolve_none(self):
        client = self._fake_client(None)
        with mock.patch.object(db, "_get", return_value=client):
            self.assertIsNone(db.get_ml_access_token("org-1"))

    def test_sem_expires_at_e_devolvido(self):
        """expires_at nulo (nunca setado) não deve bloquear o token."""
        client = self._fake_client({"access_token": "tok-abc", "expires_at": None})
        with mock.patch.object(db, "_get", return_value=client):
            self.assertEqual(db.get_ml_access_token("org-1"), "tok-abc")


class GetConnectorMercadoLivreTokenTests(unittest.TestCase):
    """get_connector/import_product repassam organization_id -> token OAuth
    já conectado pro conector do Mercado Livre (best-effort contra o 403
    anônimo da API pública)."""

    def test_get_connector_busca_token_da_org(self):
        with mock.patch.object(db, "get_ml_access_token",
                               return_value="tok-xyz") as buscar:
            conector = pipeline.get_connector("mercadolivre", "org-1")
        buscar.assert_called_once_with("org-1")
        self.assertEqual(conector.access_token, "tok-xyz")

    def test_get_connector_sem_organization_id_fica_anonimo(self):
        with mock.patch.object(db, "get_ml_access_token") as buscar:
            conector = pipeline.get_connector("mercadolivre")
        buscar.assert_not_called()
        self.assertIsNone(conector.access_token)

    def test_get_connector_outro_source_ignora_organization_id(self):
        with mock.patch.object(db, "get_ml_access_token") as buscar:
            conector = pipeline.get_connector("aliexpress", "org-1")
        buscar.assert_not_called()
        self.assertEqual(conector.code, "aliexpress")

    def test_import_product_repassa_organization_id(self):
        url = "https://produto.mercadolivre.com.br/MLB-1000000-x"
        produto_bruto = {
            "external_product_id": "MLB1000000", "canonical_url": url,
            "title": "Produto X", "method": "API", "source_confidence": "VERIFIED",
        }
        with mock.patch.object(db, "get_ml_access_token",
                               return_value="tok-xyz") as buscar, \
             mock.patch.object(pipeline.MercadoLivreConnector, "get_product",
                              return_value=produto_bruto):
            pipeline.import_product("mercadolivre", url,
                                    organization_id="org-1")
        buscar.assert_called_once_with("org-1")


class MercadoLivreHermesFlowTests(unittest.TestCase):
    def test_valida_apenas_https_do_mercado_livre(self):
        self.assertEqual(
            pipeline.validar_link_afiliado_ml("https://meli.la/2TtPTtD"),
            "https://meli.la/2TtPTtD",
        )
        for invalido in ("http://meli.la/x", "https://evil.example/x", "javascript:x"):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                pipeline.validar_link_afiliado_ml(invalido)

    def test_link_oficial_gera_copy_aprova_e_enfileira_sem_revisao(self):
        campanha = {"id": "c1", "product_id": "p1", "organization_id": "org1"}
        produto = {
            "id": "p1", "source_name": "mercadolivre", "title": "Air Fryer",
            "discounted_price_brl": 299.90, "original_price_brl": 399.90,
            "image_url": "https://http2.mlstatic.com/x.jpg", "confidence": "VERIFIED",
        }
        conteudo = {"id": "co1", "status": "PENDING_REVIEW"}
        table = FakeTable(rows=[])
        client = mock.MagicMock()
        client.table.return_value = table
        copy = {
            "headline": "Air Fryer", "body": "por R$ 299,90",
            "cta": "Ver oferta", "disclaimer": "Link de afiliado.",
            "provider": "fallback", "model": None,
        }
        score = {"score_total": 80, "reason_summary": [], "warnings": [],
                 "bloqueios": [], "desconto_real": 20}

        with mock.patch.object(db, "get_campaign", return_value=campanha), \
             mock.patch.object(db, "get_product", return_value=produto), \
             mock.patch.object(db, "update_product") as update_product, \
             mock.patch.object(db, "update_campaign") as update_campaign, \
             mock.patch.object(db, "register_audit") as audit, \
             mock.patch.object(db, "get_active_coupons", return_value=[]), \
             mock.patch.object(db, "get_campaign_contents",
                               side_effect=[[], [conteudo]]), \
             mock.patch.object(db, "create_content") as create_content, \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(pipeline, "generate_copies", return_value=[copy]), \
             mock.patch.object(pipeline, "compute_score", return_value=score), \
             mock.patch.object(pipeline, "approve_campaign") as approve:
            resultado = pipeline.completar_link_mercadolivre_assistido(
                "c1", "https://meli.la/2TtPTtD",
                official_tool_confirmed=True, auto_approve=True, queue_id="q1")

        self.assertEqual(resultado["status"], "SCHEDULED")
        self.assertEqual(resultado["content_id"], "co1")
        self.assertTrue(any(
            call.args[1].get("affiliate_link_status") == "VERIFIED"
            for call in update_product.call_args_list
        ))
        create_content.assert_called_once()
        approve.assert_called_once_with("c1", ["co1"], actor_type="worker")
        self.assertTrue(any(row.get("queue_id") == "q1" for row in table.inserts))
        self.assertIn(mock.call("c1", {"status": "SCHEDULED"}),
                      update_campaign.call_args_list)
        self.assertGreaterEqual(audit.call_count, 2)


class TitulosParecidosTests(unittest.TestCase):
    """Regressão real: 3 anúncios do "mesmo" iPhone 16e (vendedores
    diferentes, URLs diferentes) publicados ao mesmo tempo — dedupe por
    source_url não pega isso porque a URL do anúncio é mesmo diferente.
    Limiares calibrados empiricamente contra títulos reais de anúncio."""

    def test_titulos_do_mesmo_aparelho_sao_parecidos(self):
        self.assertTrue(pipeline._titulos_parecidos(
            "iPhone 16e Apple 128GB Novo Lacrado Original Preto",
            "iPhone 16e Apple 128GB Original Lacrado - Cor Preta"))
        self.assertTrue(pipeline._titulos_parecidos(
            "Apple iPhone 16e 128GB Novo Original Preto Lacrado",
            "iPhone 16e Apple 128GB Novo Lacrado Original Preto"))

    def test_titulos_de_produtos_diferentes_nao_sao_parecidos(self):
        self.assertFalse(pipeline._titulos_parecidos(
            "iPhone 16e Apple 128GB Novo Lacrado",
            "Samsung Galaxy S24 256GB Novo Lacrado"))
        self.assertFalse(pipeline._titulos_parecidos(
            "Fone Bluetooth XYZ TWS", "Mouse Sem Fio K7 Ultra Branco"))

    def test_variantes_diferentes_do_mesmo_modelo_nao_sao_parecidas(self):
        """Cor/armazenamento diferentes contam como produto diferente —
        a trava é só contra publicar a MESMA oferta repetida, não contra
        mostrar variantes distintas de um mesmo modelo."""
        self.assertFalse(pipeline._titulos_parecidos(
            "iPhone 16e 128GB Preto", "iPhone 16e 256GB Azul"))

    def test_titulo_vazio_nunca_e_parecido(self):
        self.assertFalse(pipeline._titulos_parecidos("", "iPhone 16e"))
        self.assertFalse(pipeline._titulos_parecidos("iPhone 16e", ""))


class ManterSoMaisBaratoPorProdutoTests(unittest.TestCase):
    def test_mantem_so_o_mais_barato_entre_titulos_parecidos(self):
        produtos = [
            {"title": "iPhone 16e Apple 128GB Novo Lacrado Original Preto",
             "current_price": 3200.0, "canonical_url": "https://x/1"},
            {"title": "iPhone 16e Apple 128GB Original Lacrado - Cor Preta",
             "current_price": 2950.0, "canonical_url": "https://x/2"},
            {"title": "Apple iPhone 16e 128GB Novo Original Preto Lacrado",
             "current_price": 3100.0, "canonical_url": "https://x/3"},
        ]
        resultado = pipeline._manter_so_mais_barato_por_produto(produtos)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["current_price"], 2950.0)

    def test_produtos_diferentes_nao_sao_agrupados(self):
        produtos = [
            {"title": "iPhone 16e Apple 128GB Novo Lacrado", "current_price": 3200.0},
            {"title": "Samsung Galaxy S24 256GB Novo Lacrado", "current_price": 2500.0},
        ]
        resultado = pipeline._manter_so_mais_barato_por_produto(produtos)
        self.assertEqual(len(resultado), 2)

    def test_sem_preco_no_duplicado_mantem_o_que_ja_tinha_preco(self):
        produtos = [
            {"title": "iPhone 16e 128GB Novo Lacrado", "current_price": 3000.0},
            {"title": "iPhone 16e 128GB Novo Lacrado Original", "current_price": None},
        ]
        resultado = pipeline._manter_so_mais_barato_por_produto(produtos)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["current_price"], 3000.0)


class ExisteProdutoSimilarRecenteTests(unittest.TestCase):
    """Trava contra publicar o "mesmo" aparelho de novo em ciclos
    seguintes, mesmo com product_id/URL diferentes (outro vendedor)."""

    def test_encontra_titulo_parecido_recente(self):
        table = FakeTable(rows=[{"title": "iPhone 16e Apple 128GB Original Lacrado"}])
        client = mock.MagicMock()
        client.table.return_value = table
        with mock.patch.object(db, "_get", return_value=client):
            resultado = pipeline._existe_produto_similar_recente(
                "org1", "iPhone 16e Apple 128GB Novo Lacrado Original Preto")
        self.assertTrue(resultado)

    def test_sem_titulo_parecido_devolve_false(self):
        table = FakeTable(rows=[{"title": "Samsung Galaxy S24"}])
        client = mock.MagicMock()
        client.table.return_value = table
        with mock.patch.object(db, "_get", return_value=client):
            resultado = pipeline._existe_produto_similar_recente("org1", "iPhone 16e 128GB")
        self.assertFalse(resultado)

    def test_titulo_vazio_nao_consulta_banco(self):
        with mock.patch.object(db, "_get") as get_mock:
            resultado = pipeline._existe_produto_similar_recente("org1", "")
        self.assertFalse(resultado)
        get_mock.assert_not_called()


class CategoriaRecenteDemaisTests(unittest.TestCase):
    """Espaçamento por categoria: depois de publicar um fone de ouvido,
    espera pelo menos CATEGORIA_JANELA_MINIMA campanhas de outra
    categoria antes de publicar outro fone de ouvido."""

    def test_mesma_categoria_dentro_da_janela_bloqueia(self):
        rows = [{"id": str(i), "product": {"category": "Eletrônicos > Fones de Ouvido"}}
                for i in range(3)]
        table = FakeTable(rows=rows)
        client = mock.MagicMock()
        client.table.return_value = table
        with mock.patch.object(db, "_get", return_value=client):
            resultado = pipeline._categoria_recente_demais(
                "org1", "Eletrônicos > Fones de Ouvido")
        self.assertTrue(resultado)

    def test_categoria_diferente_nao_bloqueia(self):
        rows = [{"id": "1", "product": {"category": "Celulares > Smartphones"}}]
        table = FakeTable(rows=rows)
        client = mock.MagicMock()
        client.table.return_value = table
        with mock.patch.object(db, "_get", return_value=client):
            resultado = pipeline._categoria_recente_demais(
                "org1", "Eletrônicos > Fones de Ouvido")
        self.assertFalse(resultado)

    def test_sem_categoria_nunca_bloqueia_e_nao_consulta_banco(self):
        with mock.patch.object(db, "_get") as get_mock:
            resultado = pipeline._categoria_recente_demais("org1", None)
        self.assertFalse(resultado)
        get_mock.assert_not_called()


class DescobrirProdutosAliexpressTests(unittest.TestCase):
    """Regressão: sem paginação, o modo automático sempre via o mesmo
    topo do resultado (já importado pelo dedupe) e "esgotava" rápido —
    12 ofertas publicadas e depois nada de novo. Paginar garante que
    ciclos seguintes cavam mais fundo no catálogo em vez de tropeçar
    sempre nos mesmos produtos já vistos."""

    def test_busca_varias_paginas_por_termo(self):
        pagina1 = [{"canonical_url": f"https://x/{i}"} for i in range(20)]
        pagina2 = [{"canonical_url": f"https://x/p2-{i}"} for i in range(20)]
        pagina3: list = []  # AliExpress acabou os resultados

        chamadas = []

        def fake_search(self, termo, *, page_no=1):
            chamadas.append((termo, page_no))
            return {1: pagina1, 2: pagina2, 3: pagina3}[page_no]

        with mock.patch("connectors.aliexpress.AliExpressConnector.search_offers",
                        fake_search):
            resultado = pipeline.descobrir_produtos_aliexpress(
                ["fone"], max_por_termo=20, paginas=5,
                sortear_pagina=lambda a, b: 1)

        self.assertEqual(len(resultado), 40)  # página 1 + página 2
        self.assertEqual(chamadas, [("fone", 1), ("fone", 2), ("fone", 3)])

    def test_para_no_limite_sem_esgotar_paginas_restantes(self):
        pagina1 = [{"canonical_url": f"https://x/{i}"} for i in range(20)]
        chamadas = []

        def fake_search(self, termo, *, page_no=1):
            chamadas.append(page_no)
            return pagina1

        with mock.patch("connectors.aliexpress.AliExpressConnector.search_offers",
                        fake_search):
            pipeline.descobrir_produtos_aliexpress(
                ["fone"], max_por_termo=10, paginas=5,
                sortear_pagina=lambda a, b: 1)

        # max_por_termo(10) * paginas(5) = 50 -> para depois de 3 páginas (60 >= 50)
        self.assertEqual(chamadas, [1, 2, 3])

    def test_falha_de_credencial_num_termo_nao_derruba_outros(self):
        from connectors import CredencialNaoConfigurada

        def fake_search(self, termo, *, page_no=1):
            if termo == "quebrado":
                raise CredencialNaoConfigurada("sem chave")
            return [{"canonical_url": "https://x/ok"}]

        with mock.patch("connectors.aliexpress.AliExpressConnector.search_offers",
                        fake_search):
            resultado = pipeline.descobrir_produtos_aliexpress(
                ["quebrado", "fone"], paginas=1, sortear_pagina=lambda a, b: 1)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["canonical_url"], "https://x/ok")

    def test_sorteia_pagina_inicial_por_termo_dentro_do_limite(self):
        """Sem isso, todo ciclo automático re-varre sempre a página 1 —
        os mesmos produtos de sempre (já dedupados) — e "esgota" rápido."""
        paginas_pedidas = []

        def fake_search(self, termo, *, page_no=1):
            paginas_pedidas.append(page_no)
            return []  # não importa o conteúdo aqui, só a página pedida

        with mock.patch("connectors.aliexpress.AliExpressConnector.search_offers",
                        fake_search):
            pipeline.descobrir_produtos_aliexpress(
                ["a", "b", "c"], paginas=1, pagina_maxima=30)

        self.assertEqual(len(paginas_pedidas), 3)
        for pagina in paginas_pedidas:
            self.assertGreaterEqual(pagina, 1)
            self.assertLessEqual(pagina, 30)
        # com 3 termos e faixa 1-30, dificilimo sortear o mesmo valor pros 3
        self.assertGreater(len(set(paginas_pedidas)), 1)


class MontarCopyTextTests(unittest.TestCase):
    def test_monta_texto_completo(self):
        copia = {"headline": "H", "body": "B", "cta": "C", "disclaimer": "D"}
        texto = pipeline.montar_copy_text(copia)
        self.assertEqual(texto, "H\n\nB\n\nC\n\nD")


class LoadContentTests(unittest.TestCase):
    """Regressão: _load_content precisa reconstruir cta E disclaimer do
    copy_text persistido — antes desta correção os dois vinham hardcoded
    como "" (mesmo com o texto guardando os dois certinho), então toda
    publicação real saía sem CTA e sem disclaimer no final da mensagem."""

    def test_reconstroi_cta_e_disclaimer(self):
        copia_original = {
            "headline": "🔥 Produto X - R$ 49,90 🔥 #anúncio",
            # body com várias linhas internas separadas por "\n\n", como
            # o corpo real gerado por _gerar_fallback (specs/cupom/preço).
            "body": "🔴 A | B 🔴\n\n🎟 Cupom: X\n\n💸 R$ 49,90",
            "cta": "Corre que acaba!",
            "disclaimer": "👇 Clique no link... 💙",
        }
        copy_text = pipeline.montar_copy_text(copia_original)
        table = FakeTable(single={"id": "co1", "copy_text": copy_text})
        client = mock.MagicMock()
        client.table.return_value = table

        with mock.patch.object(db, "_get", return_value=client):
            reconstruido = pipeline._load_content("co1")

        self.assertEqual(reconstruido["headline"], copia_original["headline"])
        self.assertEqual(reconstruido["body"], copia_original["body"])
        self.assertEqual(reconstruido["cta"], copia_original["cta"])
        self.assertEqual(reconstruido["disclaimer"], copia_original["disclaimer"])


if __name__ == "__main__":
    unittest.main()
