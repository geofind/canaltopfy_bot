from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from coupon_discovery import (  # noqa: E402
    _active_now, coupon_copy, extract_verified_code)


class CouponDiscoveryTests(unittest.TestCase):
    def test_codigo_so_e_extraido_quando_declarado(self):
        self.assertEqual(
            extract_verified_code("Cupom: TOPFY20 em tecnologia"), "TOPFY20")
        self.assertIsNone(extract_verified_code("20% OFF em tecnologia"))

    def test_validade_oficial_e_obrigatoria(self):
        moment = datetime(2026, 8, 3, tzinfo=timezone.utc)
        timestamp = int(moment.timestamp())
        self.assertTrue(_active_now({
            "period_start_time": timestamp - 60,
            "period_end_time": timestamp + 60,
        }, moment))
        self.assertFalse(_active_now({
            "period_start_time": timestamp - 120,
            "period_end_time": timestamp - 60,
        }, moment))

    def test_copy_destaca_codigo_regra_app_e_cta(self):
        copy = coupon_copy({
            "source_name": "shopee",
            "title": "R$ 50 OFF em Tecnologia",
            "coupon_code": "TOPFY50",
            "app_only": True,
        })
        self.assertIn("CUPOM SHOPEE", copy["headline"])
        self.assertIn("CÓDIGO: TOPFY50", copy["body"])
        self.assertIn("somente no APP", copy["body"])
        self.assertIn("link Topfy", copy["cta"])

    def test_copy_sem_codigo_orienta_resgate_no_link(self):
        copy = coupon_copy({
            "source_name": "shopee", "title": "Cupom Tecnologia"})
        self.assertIn("Resgate direto pelo link oficial", copy["body"])
        self.assertNotIn("CÓDIGO:", copy["body"])


if __name__ == "__main__":
    unittest.main()
