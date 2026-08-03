"""Testes do cache local de imagens (fundação preventiva, limpeza manual)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

import image_cache  # noqa: E402


class ImageCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cache_dir = Path(self._tmp.name) / "cache"
        self._patch = mock.patch.object(image_cache, "CACHE_DIR", self.cache_dir)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_usage_sem_diretorio_devolve_zero(self):
        self.assertEqual(image_cache.usage(), {"files": 0, "bytes": 0})

    def test_save_grava_e_usage_reflete(self):
        image_cache.save("a.jpg", b"1234")
        image_cache.save("b.jpg", b"12345678")
        resultado = image_cache.usage()
        self.assertEqual(resultado["files"], 2)
        self.assertEqual(resultado["bytes"], 12)

    def test_cleanup_all_remove_tudo_e_devolve_bytes_liberados(self):
        image_cache.save("a.jpg", b"1234")
        image_cache.save("b.jpg", b"12345678")
        resultado = image_cache.cleanup_all()
        self.assertEqual(resultado, {"removed": 2, "freed_bytes": 12})
        self.assertEqual(image_cache.usage(), {"files": 0, "bytes": 0})

    def test_cleanup_all_sem_diretorio_nao_falha(self):
        self.assertEqual(image_cache.cleanup_all(), {"removed": 0, "freed_bytes": 0})

    def test_disk_usage_devolve_totais_positivos(self):
        resultado = image_cache.disk_usage(".")
        self.assertGreater(resultado["total_bytes"], 0)
        self.assertGreaterEqual(resultado["free_bytes"], 0)
        self.assertIn("used_bytes", resultado)


if __name__ == "__main__":
    unittest.main()
