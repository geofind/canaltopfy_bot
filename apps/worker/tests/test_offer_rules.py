"""Testes das regras de curadoria do Laboratório de Captura
(/campanhas): bloqueio de palavras e travamento de categoria."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from offer_rules import (category_lock_reason, is_blocked_by_word,  # noqa: E402
                         redistribute_by_category_targets)


class IsBlockedByWordTests(unittest.TestCase):
    def test_bate_no_titulo(self):
        termo = is_blocked_by_word(
            "Fone Bluetooth XYZ", "Eletrônicos > Fones",
            [{"term": "fone", "expires_at": None}])
        self.assertEqual(termo, "fone")

    def test_bate_em_frase_com_varias_palavras(self):
        termo = is_blocked_by_word(
            "Fone de Ouvido Bluetooth", None,
            [{"term": "fone de ouvido", "expires_at": None}])
        self.assertEqual(termo, "fone de ouvido")

    def test_sem_bloqueio_correspondente_devolve_none(self):
        termo = is_blocked_by_word(
            "Notebook Gamer", "Informática",
            [{"term": "fone", "expires_at": None}])
        self.assertIsNone(termo)

    def test_bloqueio_temporario_expirado_e_ignorado(self):
        expirado = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        termo = is_blocked_by_word(
            "Fone Bluetooth XYZ", None,
            [{"term": "fone", "expires_at": expirado}])
        self.assertIsNone(termo)

    def test_bloqueio_temporario_ainda_valido_bloqueia(self):
        no_futuro = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        termo = is_blocked_by_word(
            "Fone Bluetooth XYZ", None,
            [{"term": "fone", "expires_at": no_futuro}])
        self.assertEqual(termo, "fone")

    def test_lista_vazia_nunca_bloqueia(self):
        self.assertIsNone(is_blocked_by_word("Fone Bluetooth", None, []))


class CategoryLockReasonTests(unittest.TestCase):
    def test_sem_config_nunca_bloqueia(self):
        self.assertIsNone(category_lock_reason(None))

    def test_categoria_pausada_bloqueia(self):
        motivo = category_lock_reason({"active": False})
        self.assertIsNotNone(motivo)

    def test_categoria_ativa_sem_trava_libera(self):
        self.assertIsNone(category_lock_reason({"active": True, "locked_until": None}))

    def test_categoria_travada_no_futuro_bloqueia(self):
        no_futuro = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        motivo = category_lock_reason({"active": True, "locked_until": no_futuro})
        self.assertIsNotNone(motivo)

    def test_trava_ja_expirada_libera(self):
        expirado = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        motivo = category_lock_reason({"active": True, "locked_until": expirado})
        self.assertIsNone(motivo)


class RedistributeByCategoryTargetsTests(unittest.TestCase):
    """Laboratório de Captura (/campanhas): meta de percentual por
    categoria usada pelo botão "forçar aplicação e redistribuição"."""

    ITENS = [
        {"id": "1", "category_family": "notebooks"},
        {"id": "2", "category_family": "notebooks"},
        {"id": "3", "category_family": "fones"},
        {"id": "4", "category_family": "fones"},
    ]

    def test_sem_metas_devolve_lista_original(self):
        resultado = redistribute_by_category_targets(self.ITENS, {})
        self.assertEqual(resultado, self.ITENS)

    def test_preserva_todos_os_itens(self):
        resultado = redistribute_by_category_targets(
            self.ITENS, {"fones": 70, "notebooks": 30})
        self.assertEqual(
            {item["id"] for item in resultado}, {"1", "2", "3", "4"})
        self.assertEqual(len(resultado), 4)

    def test_prioriza_categoria_com_meta_maior_primeiro(self):
        resultado = redistribute_by_category_targets(
            self.ITENS, {"fones": 70, "notebooks": 30})
        self.assertEqual(resultado[0]["category_family"], "fones")

    def test_categoria_sem_meta_cai_em_outros(self):
        itens = [
            {"id": "1", "category_family": "fones"},
            {"id": "2", "category_family": "smartwatches"},
            {"id": "3", "category_family": "fones"},
            {"id": "4", "category_family": "smartwatches"},
        ]
        resultado = redistribute_by_category_targets(itens, {"fones": 100})
        self.assertEqual({item["id"] for item in resultado},
                         {"1", "2", "3", "4"})

    def test_grupo_unico_nao_reordena(self):
        itens = [{"id": "1", "category_family": "fones"},
                 {"id": "2", "category_family": "fones"}]
        resultado = redistribute_by_category_targets(itens, {"fones": 100})
        self.assertEqual(resultado, itens)

    def test_categoria_real_chamada_outros_nao_colide_com_bucket_interno(self):
        """Regressão: `redistribute_by_category_targets` usava a string
        literal "outros" como chave interna do bucket "sem meta" — uma
        categoria de verdade cadastrada pelo usuário com esse nome
        (family_key "outros") ficava misturada com itens sem meta nenhuma.
        Com a meta hoje só o item da família "outros" deve ser priorizado;
        o item "sem-meta-nenhuma" cai no bucket interno."""
        itens = [
            {"id": "1", "category_family": "sem-meta-nenhuma"},
            {"id": "2", "category_family": "outros"},
            {"id": "3", "category_family": "sem-meta-nenhuma"},
            {"id": "4", "category_family": "outros"},
        ]
        resultado = redistribute_by_category_targets(itens, {"outros": 100})
        self.assertEqual({item["id"] for item in resultado}, {"1", "2", "3", "4"})
        self.assertEqual(resultado[0]["category_family"], "outros")


if __name__ == "__main__":
    unittest.main()
