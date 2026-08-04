from __future__ import annotations

import sys
import random
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

import replenisher  # noqa: E402
from offer_rules import (avoid_consecutive_categories, category_family,
                         deal_highlight)  # noqa: E402


def config(**overrides):
    values = {
        "organization_id": "org-1",
        "queue_id": "queue-1",
        "terms": ("smartwatch", "power bank"),
        "min_items": 24,
        "target_items": 72,
        "max_new_per_cycle": 4,
    }
    values.update(overrides)
    return replenisher.ReplenisherConfig(**values)


class ReplenisherConfigTests(unittest.TestCase):
    def test_saved_mix_overrides_environment_targets(self):
        query = mock.MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.limit.return_value = query
        query.execute.return_value.data = [{
            "shopee_target_percent": 40,
            "aliexpress_target_percent": 25,
            "mercadolivre_target_percent": 25,
            "magalu_target_percent": 10,
        }]
        client = mock.MagicMock()
        client.table.return_value = query
        with mock.patch.object(replenisher.db, "_get", return_value=client):
            saved = replenisher._config_with_saved_mix(config(
                enforce_source_mix=True,
                shopee_target_percent=50,
                aliexpress_target_percent=20,
                ml_target_percent=30,
            ))
        self.assertEqual(saved.source_target_percentages(), {
            "shopee": 40, "aliexpress": 25, "mercadolivre": 25, "magalu": 10,
        })

    def test_invalid_saved_mix_keeps_environment_targets(self):
        query = mock.MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.limit.return_value = query
        query.execute.return_value.data = [{
            "shopee_target_percent": 80,
            "aliexpress_target_percent": 80,
            "mercadolivre_target_percent": 80,
            "magalu_target_percent": 80,
        }]
        client = mock.MagicMock()
        client.table.return_value = query
        original = config(enforce_source_mix=True)
        with mock.patch.object(replenisher.db, "_get", return_value=client):
            saved = replenisher._config_with_saved_mix(original)
        self.assertIs(saved, original)

    def test_saved_min_score_overrides_environment_default(self):
        query = mock.MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.maybe_single.return_value = query
        query.execute.return_value.data = {"min_score": 42.5}
        client = mock.MagicMock()
        client.table.return_value = query
        with mock.patch.object(replenisher.db, "_get", return_value=client):
            saved = replenisher._config_with_saved_min_score(config(min_score=35.0))
        self.assertEqual(saved.min_score, 42.5)

    def test_missing_discovery_settings_keeps_environment_default(self):
        query = mock.MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.maybe_single.return_value = query
        query.execute.return_value.data = None
        client = mock.MagicMock()
        client.table.return_value = query
        original = config(min_score=35.0)
        with mock.patch.object(replenisher.db, "_get", return_value=client):
            saved = replenisher._config_with_saved_min_score(original)
        self.assertIs(saved, original)

    def test_manual_order_prevents_worker_from_reshuffling(self):
        query = mock.MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.limit.return_value = query
        query.execute.return_value.data = [{"manual_order_locked": True}]
        client = mock.MagicMock()
        client.table.return_value = query
        with mock.patch.object(replenisher.db, "_get", return_value=client):
            result = replenisher.randomize_pending_schedule(config())
        self.assertEqual(result, {
            "randomized": 0, "reason": "manual_order_locked",
        })
        self.assertEqual(client.table.call_count, 1)

    def test_target_must_be_greater_than_minimum(self):
        with self.assertRaises(ValueError):
            config(min_items=24, target_items=24).validate()

    def test_requires_terms(self):
        with self.assertRaises(ValueError):
            config(terms=()).validate()

    def test_randomized_items_preserves_every_item(self):
        items = [{"id": index} for index in range(20)]
        shuffled = replenisher._randomized_items(
            items, rng=random.Random(42))
        self.assertCountEqual(shuffled, items)
        self.assertNotEqual(shuffled, items)

    def test_randomized_items_spreads_minority_source(self):
        items = [
            {"id": f"ali-{index}", "source_name": "aliexpress"}
            for index in range(85)
        ] + [
            {"id": f"ml-{index}", "source_name": "mercadolivre"}
            for index in range(10)
        ]
        shuffled = replenisher._randomized_items(
            items, rng=random.Random(42))
        longest_ali = longest = 0
        for item in shuffled:
            if item["source_name"] == "aliexpress":
                longest += 1
                longest_ali = max(longest_ali, longest)
            else:
                longest = 0
        self.assertLessEqual(longest_ali, 12)
        self.assertCountEqual(shuffled, items)

    def test_randomized_items_aplica_mix_50_20_30(self):
        items = (
            [{"id": f"shopee-{i}", "source_name": "shopee"} for i in range(50)]
            + [{"id": f"ali-{i}", "source_name": "aliexpress"} for i in range(20)]
            + [{"id": f"ml-{i}", "source_name": "mercadolivre"} for i in range(30)]
        )
        shuffled = replenisher._randomized_items(
            items,
            rng=random.Random(42),
            target_percentages={
                "shopee": 50, "aliexpress": 20, "mercadolivre": 30,
            },
        )
        self.assertCountEqual(shuffled, items)
        first_twenty = [item["source_name"] for item in shuffled[:20]]
        self.assertEqual(first_twenty.count("shopee"), 10)
        self.assertEqual(first_twenty.count("aliexpress"), 4)
        self.assertEqual(first_twenty.count("mercadolivre"), 6)

    def test_weighted_order_prioritizes_high_scores_without_losing_items(self):
        items = [
            {"id": f"high-{index}", "score": 90}
            for index in range(40)
        ] + [
            {"id": f"low-{index}", "score": 10}
            for index in range(40)
        ]
        ordered = replenisher._weighted_score_order(
            items, rng=random.Random(42))
        high_positions = [
            index for index, item in enumerate(ordered)
            if item["id"].startswith("high-")]
        low_positions = [
            index for index, item in enumerate(ordered)
            if item["id"].startswith("low-")]
        self.assertLess(
            sum(high_positions) / len(high_positions),
            sum(low_positions) / len(low_positions))
        self.assertCountEqual(ordered, items)

    def test_familias_equivalentes_reconhecem_exemplos_do_canal(self):
        self.assertEqual(category_family("Eletrônicos", "Carregador USB-C 65W"),
                         "carregadores")
        self.assertEqual(category_family("Telefonia", "Smartphone Galaxy"),
                         "celulares")
        self.assertEqual(category_family("Informática > Monitores", "Tela 24"),
                         "monitores")

    def test_reordena_sem_duas_categorias_iguais_seguidas(self):
        items = [
            {"id": "c1", "category_family": "carregadores"},
            {"id": "c2", "category_family": "carregadores"},
            {"id": "m1", "category_family": "monitores"},
            {"id": "s1", "category_family": "celulares"},
        ]
        ordered = avoid_consecutive_categories(items)
        self.assertCountEqual(ordered, items)
        self.assertTrue(all(
            ordered[i - 1]["category_family"] != ordered[i]["category_family"]
            for i in range(1, len(ordered))))

    def test_destaque_exige_mais_de_cinquenta_por_cento_real(self):
        self.assertEqual(
            deal_highlight(current_price=49, original_price=100)["reason"],
            "DISCOUNT_OVER_50")
        self.assertIsNone(deal_highlight(current_price=50, original_price=100))

    def test_menor_preco_recente_exige_historico_e_valor_estritamente_menor(self):
        result = deal_highlight(
            current_price=89, original_price=None,
            historical_prices=[100, 95], lookback_days=30)
        self.assertEqual(result["reason"], "RECENT_LOW")
        self.assertIsNone(deal_highlight(
            current_price=95, original_price=None, historical_prices=[95, 100]))
        self.assertIsNone(deal_highlight(
            current_price=89, original_price=None, historical_prices=[]))


class ReplenishOnceTests(unittest.TestCase):
    @mock.patch.object(replenisher, "_active_items")
    def test_does_nothing_while_reserve_is_healthy(self, active):
        active.return_value = [{"id": index} for index in range(25)]
        with mock.patch.object(replenisher, "ciclo_automatico") as cycle:
            result = replenisher.replenish_once(config())
        self.assertFalse(result["triggered"])
        self.assertEqual(result["reason"], "reserve_ok")
        cycle.assert_not_called()

    @mock.patch.object(replenisher.db, "register_audit")
    @mock.patch.object(replenisher, "randomize_pending_schedule",
                       return_value={"randomized": 12})
    @mock.patch.object(replenisher, "_request_hermes_links", return_value=1)
    @mock.patch.object(replenisher, "_ml_candidates", return_value=[])
    @mock.patch.object(replenisher, "ciclo_automatico")
    @mock.patch.object(replenisher, "_enqueue_campaigns")
    @mock.patch.object(replenisher, "_ready_inventory")
    @mock.patch.object(replenisher, "_active_items")
    def test_refill_is_bounded_and_uses_inventory_before_capture(
            self, active, inventory, enqueue, cycle, ml_candidates,
            request_hermes, randomize, register_audit):
        active.side_effect = [
            [{"id": index} for index in range(10)],
            [{"id": index} for index in range(14)],
        ]
        inventory.return_value = [
            {"campaign_id": "ready-1"}, {"campaign_id": "ready-2"}]
        enqueue.side_effect = [
            ["ready-1", "ready-2"], ["new-1", "new-2"]]
        cycle.return_value = {"campanhas": [
            {"campaign_id": "new-1"}, {"campaign_id": "new-2"}]}

        result = replenisher.replenish_once(
            config(), now=datetime(2026, 8, 3, tzinfo=timezone.utc))

        self.assertTrue(result["triggered"])
        self.assertEqual(result["inventory_queued"], 2)
        self.assertEqual(result["captured_queued"], 2)
        self.assertEqual(result["hermes_jobs"], 1)
        self.assertEqual(result["randomized"], 12)
        self.assertEqual(
            sum(call.kwargs["max_novos"] for call in cycle.call_args_list), 2)
        self.assertTrue(all(
            call.kwargs["queue_id"] is None for call in cycle.call_args_list))
        self.assertEqual(
            {call.kwargs["source_name"] for call in cycle.call_args_list},
            {"shopee", "magalu"},
        )
        self.assertEqual(enqueue.call_count, 2)
        register_audit.assert_called_once()

    @mock.patch.object(replenisher.db, "register_audit")
    @mock.patch.object(replenisher, "randomize_pending_schedule",
                       return_value={"randomized": 0})
    @mock.patch.object(replenisher, "_request_hermes_links", return_value=0)
    @mock.patch.object(replenisher, "_ml_candidates", return_value=[])
    @mock.patch.object(replenisher, "ciclo_automatico")
    @mock.patch.object(replenisher, "_enqueue_campaigns", return_value=[])
    @mock.patch.object(replenisher, "_ready_inventory", return_value=[])
    @mock.patch.object(replenisher, "_active_items")
    def test_limita_termos_de_rede_mas_nao_o_catalogo_local_do_magalu(
            self, active, inventory, enqueue, cycle, ml_candidates,
            request_hermes, randomize, register_audit):
        """AliExpress/Shopee fazem 1 request real por página por termo —
        com dezenas de termos e a API lenta, um ciclo já ficou preso por
        muito tempo e travou o reabastecimento inteiro. Magalu é local
        (catálogo em disco), não tem esse risco e continua recebendo a
        lista inteira."""
        active.side_effect = [
            [{"id": index} for index in range(10)],
            [{"id": index} for index in range(10)],
        ]
        cycle.return_value = {"campanhas": []}
        muitos_termos = tuple(f"termo{i}" for i in range(60))

        replenisher.replenish_once(
            config(terms=muitos_termos),
            now=datetime(2026, 8, 3, tzinfo=timezone.utc))

        chamadas_por_fonte = {
            call.kwargs["source_name"]: call.kwargs["termos"]
            for call in cycle.call_args_list
        }
        for fonte in ("shopee", "aliexpress"):
            if fonte in chamadas_por_fonte:
                self.assertLessEqual(
                    len(chamadas_por_fonte[fonte]),
                    replenisher.REDE_TERMOS_POR_CICLO)
        if "magalu" in chamadas_por_fonte:
            self.assertEqual(len(chamadas_por_fonte["magalu"]), len(muitos_termos))


class _ProductsQueryVerified:
    """Fake da tabela `products` pro cenário de _ready_inventory: aceita a
    cadeia select/eq/eq/not_.is_ usada de verdade e devolve uma lista fixa
    de produtos "verificados", sem filtrar (os filtros reais são no banco;
    aqui só interessa o volume pra testar o particionamento)."""

    def __init__(self, produtos):
        self._produtos = produtos

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self

    @property
    def not_(self):
        return self

    def is_(self, *a, **k): return self

    def execute(self):
        resp = mock.MagicMock()
        resp.data = self._produtos
        return resp


class _CampaignsQueryRecordsChunks:
    """Fake da tabela `campaigns`: grava cada bloco de product_id recebido
    via `.in_("product_id", bloco)` pra provar que nenhum bloco passa de
    IN_CHUNK — o bug real (issue "JSON could not be generated" do
    PostgREST) só aparece quando um único IN carrega centenas de UUIDs."""

    def __init__(self):
        self.chunks_recebidos: list[list[str]] = []

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self

    def in_(self, campo, valores):
        if campo == "product_id":
            self.chunks_recebidos.append(list(valores))
        return self

    def execute(self):
        resp = mock.MagicMock()
        resp.data = []
        return resp


class ReadyInventoryChunkingTests(unittest.TestCase):
    """_ready_inventory alimenta o reabastecedor com campanhas já
    verificadas — em produção, sem retenção nos produtos, essa lista já
    passou de 600 e um `.in_("product_id", [...])` com todos de uma vez
    estourava o limite de tamanho de URL da API do Supabase (erro cru
    "JSON could not be generated"/400, travando o reabastecedor inteiro
    em todo ciclo). A correção quebra a consulta em blocos de IN_CHUNK."""

    def test_particiona_produtos_verificados_em_blocos_de_ate_in_chunk(self):
        total_produtos = replenisher.IN_CHUNK + 50
        produtos = [
            {"id": f"p{i}", "source_name": "aliexpress", "score": 10,
             "created_at": "2026-01-01T00:00:00+00:00", "title": f"Produto {i}",
             "category": "Cat"}
            for i in range(total_produtos)
        ]
        campanhas_query = _CampaignsQueryRecordsChunks()
        tabelas = {
            "products": _ProductsQueryVerified(produtos),
            "campaigns": campanhas_query,
        }
        client = mock.MagicMock()
        client.table.side_effect = lambda nome: tabelas[nome]

        cfg = replenisher.ReplenisherConfig(
            organization_id="org1", queue_id="queue1", terms=("x",))
        with mock.patch.object(replenisher.db, "_get", return_value=client):
            resultado = replenisher._ready_inventory(cfg, 5)

        self.assertEqual(resultado, [])
        self.assertGreater(len(campanhas_query.chunks_recebidos), 1)
        self.assertTrue(all(
            len(bloco) <= replenisher.IN_CHUNK
            for bloco in campanhas_query.chunks_recebidos))
        ids_recebidos = sum(len(bloco) for bloco in campanhas_query.chunks_recebidos)
        self.assertEqual(ids_recebidos, total_produtos)


class _FakeQuery:
    """Encadeamento de query PostgREST mínimo, uma instância por tabela."""

    def __init__(self, data):
        self._data = data
        self.updates: list[dict] = []

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def gt(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def in_(self, *a, **k): return self

    def update(self, fields):
        self.updates.append(fields)
        return self

    def execute(self):
        resp = mock.MagicMock()
        resp.data = self._data
        return resp


class _FakeClient:
    def __init__(self, tables: dict[str, "_FakeQuery"]):
        self.tables = tables

    def table(self, name):
        return self.tables[name]


class ForceRedistributeByCategoryTests(unittest.TestCase):
    """Laboratório de Captura (/campanhas): meta de percentual por
    categoria + botão "forçar aplicação e redistribuição"."""

    def _client(self, queue_items_data):
        return _FakeClient({
            "queues": _FakeQuery([{"interval_minutes": 5}]),
            "queue_items": _FakeQuery(queue_items_data),
            "campaigns": _FakeQuery([
                {"id": "c1", "product_id": "p1"},
                {"id": "c2", "product_id": "p2"},
                {"id": "c3", "product_id": "p3"},
                {"id": "c4", "product_id": "p4"},
            ]),
            "products": _FakeQuery([
                {"id": "p1", "title": "Notebook Gamer", "category": None},
                {"id": "p2", "title": "Notebook Ultrafino", "category": None},
                {"id": "p3", "title": "Fone Bluetooth", "category": None},
                {"id": "p4", "title": "Fone Sem Fio", "category": None},
            ]),
        })

    def test_redistribui_pendentes_pela_meta_por_categoria(self):
        now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        rows = [
            {"id": "qi1", "campaign_id": "c1", "scheduled_at": "2026-01-01T10:00:00+00:00"},
            {"id": "qi2", "campaign_id": "c2", "scheduled_at": "2026-01-01T10:05:00+00:00"},
            {"id": "qi3", "campaign_id": "c3", "scheduled_at": "2026-01-01T10:10:00+00:00"},
            {"id": "qi4", "campaign_id": "c4", "scheduled_at": "2026-01-01T10:15:00+00:00"},
        ]
        client = self._client(rows)
        capture_config = {"categories": {
            "fones": {"target_percent": 70},
            "notebooks": {"target_percent": 30},
        }}
        with mock.patch.object(replenisher.db, "_get", return_value=client), \
             mock.patch.object(replenisher.db, "get_capture_lab_config",
                               return_value=capture_config), \
             mock.patch.object(replenisher.db, "register_audit") as audit:
            result = replenisher.force_redistribute_by_category(
                "org-1", "queue-1", now=now)

        self.assertEqual(result["redistributed"], 4)
        queue_items = client.tables["queue_items"]
        self.assertEqual(len(queue_items.updates), 4)
        slots_originais = {row["scheduled_at"] for row in rows}
        slots_aplicados = {u["scheduled_at"] for u in queue_items.updates}
        self.assertEqual(slots_originais, slots_aplicados)
        audit.assert_called_once()
        self.assertEqual(
            audit.call_args.kwargs["action"], "categoria_redistribuicao_forcada")

    def test_sem_metas_definidas_nao_redistribui(self):
        now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        rows = [
            {"id": "qi1", "campaign_id": "c1", "scheduled_at": "2026-01-01T10:00:00+00:00"},
            {"id": "qi2", "campaign_id": "c2", "scheduled_at": "2026-01-01T10:05:00+00:00"},
        ]
        client = self._client(rows)
        with mock.patch.object(replenisher.db, "_get", return_value=client), \
             mock.patch.object(replenisher.db, "get_capture_lab_config",
                               return_value={"categories": {}}), \
             mock.patch.object(replenisher.db, "register_audit") as audit:
            result = replenisher.force_redistribute_by_category(
                "org-1", "queue-1", now=now)

        self.assertEqual(result, {"redistributed": 0, "reason": "sem_metas_definidas"})
        self.assertEqual(client.tables["queue_items"].updates, [])
        audit.assert_not_called()

    def test_poucos_itens_nao_redistribui(self):
        now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        client = self._client([
            {"id": "qi1", "campaign_id": "c1", "scheduled_at": "2026-01-01T10:00:00+00:00"},
        ])
        with mock.patch.object(replenisher.db, "_get", return_value=client), \
             mock.patch.object(replenisher.db, "register_audit") as audit:
            result = replenisher.force_redistribute_by_category(
                "org-1", "queue-1", now=now)

        self.assertEqual(result, {"redistributed": 0, "reason": "poucos_itens"})
        audit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
