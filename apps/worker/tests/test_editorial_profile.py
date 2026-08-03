from __future__ import annotations

import sys
import unittest
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from editorial_profile import (  # noqa: E402
    PROFILE_KEY, TECH_EDITORIAL_TARGETS, editorial_affinity,
    editorial_bucket, redistribute_by_editorial_mix,
    sort_by_editorial_affinity)


class EditorialProfileTests(unittest.TestCase):
    def test_prioritizes_pc_and_gaming_signals(self):
        gpu = editorial_affinity("Placa de Vídeo RTX 5060 8GB")
        controller = editorial_affinity("Controle 8BitDo Hall Effect")
        generic = editorial_affinity("Capa decorativa para celular")
        self.assertEqual(gpu["profile"], PROFILE_KEY)
        self.assertEqual(gpu["priority"], 5)
        self.assertEqual(controller["priority"], 5)
        self.assertEqual(generic["priority"], 0)

    def test_sort_is_editorial_then_discount(self):
        candidates = [
            {"title": "Fone Bluetooth", "discount_percent": 90},
            {"title": "Monitor Gamer 180Hz", "discount_percent": 20},
            {"title": "Placa mãe B550", "discount_percent": 25},
            {"title": "Placa de vídeo RTX 5060", "discount_percent": 40},
        ]
        ordered = sort_by_editorial_affinity(candidates)
        self.assertEqual(ordered[0]["title"], "Placa de vídeo RTX 5060")
        self.assertEqual(ordered[1]["title"], "Placa mãe B550")
        self.assertEqual(ordered[2]["title"], "Monitor Gamer 180Hz")
        self.assertEqual(ordered[3]["title"], "Fone Bluetooth")

    def test_sort_preserves_every_candidate(self):
        candidates = [{"title": str(index)} for index in range(10)]
        self.assertCountEqual(sort_by_editorial_affinity(candidates), candidates)

    def test_third_channel_signals_are_classified(self):
        self.assertEqual(
            editorial_bucket("Notebook ASUS TUF Gaming RTX 4050"),
            "notebooks")
        self.assertEqual(
            editorial_bucket("Headset sem fio Corsair HS80"), "audio")
        self.assertEqual(
            editorial_bucket("Mouse sem fio Attack Shark V6"), "perifericos")
        self.assertEqual(
            editorial_affinity("Monitor QHD 180Hz")["priority"], 5)

    def test_editorial_targets_sum_one_hundred(self):
        self.assertEqual(sum(TECH_EDITORIAL_TARGETS.values()), 100)
        self.assertEqual(TECH_EDITORIAL_TARGETS["cupons"], 10)

    def test_coupon_is_its_own_distribution_bucket(self):
        self.assertEqual(
            editorial_bucket("Cupom Shopee Tecnologia"), "cupons")

    def test_redistribution_preserves_items_and_spreads_pillars(self):
        items = (
            [{"id": f"coupon-{i}", "title": "Cupom Shopee"}
             for i in range(10)]
            + [{"id": f"pc-{i}", "title": "SSD NVMe 1TB"}
               for i in range(20)]
            + [{"id": f"game-{i}", "title": "Controle gamer 8BitDo"}
               for i in range(20)]
            + [{"id": f"monitor-{i}", "title": "Monitor gamer 180Hz"}
               for i in range(14)]
            + [{"id": f"note-{i}", "title": "Notebook gamer RTX 4050"}
               for i in range(14)]
            + [{"id": f"mouse-{i}", "title": "Mouse gamer"}
               for i in range(9)]
            + [{"id": f"audio-{i}", "title": "Headset gamer"}
               for i in range(8)]
            + [{"id": f"phone-{i}", "title": "Smartphone Galaxy"}
               for i in range(4)]
            + [{"id": f"other-{i}", "title": "Hub USB-C"}
               for i in range(1)]
        )
        ordered = redistribute_by_editorial_mix(items)
        self.assertCountEqual(ordered, items)
        first_twenty = [editorial_bucket(item["title"]) for item in ordered[:20]]
        self.assertGreaterEqual(len(set(first_twenty)), 6)
        self.assertEqual(first_twenty.count("cupons"), 2)


if __name__ == "__main__":
    unittest.main()
