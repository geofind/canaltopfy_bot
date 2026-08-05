"""Job product.refresh_images — botão "trocar foto" na fila (/filas)
quando a galeria do produto está vazia: re-busca pela API oficial,
best-effort, nunca inventa imagem."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

import db  # noqa: E402
import main as worker_main  # noqa: E402


class RefreshProductImagesJobTests(unittest.TestCase):
    def _job(self, **payload):
        return {"id": "job-1", "type": "product.refresh_images",
                "organization_id": "org-1", "payload": payload}

    def test_sem_product_id_levanta_erro(self):
        with self.assertRaises(ValueError):
            worker_main.process_job(self._job())

    def test_produto_inexistente_levanta_erro(self):
        with mock.patch.object(db, "get_product", return_value=None):
            with self.assertRaises(ValueError):
                worker_main.process_job(self._job(product_id="p1"))

    def test_encontra_foto_nova_atualiza_e_registra_auditoria(self):
        produto_atual = {
            "id": "p1", "source_name": "aliexpress",
            "source_url": "https://pt.aliexpress.com/item/123.html",
        }
        fresh = {
            "title": "Produto X", "image_url": "https://img/nova.jpg",
            "image_urls": ["https://img/nova.jpg", "https://img/outra.jpg"],
        }
        table = mock.MagicMock()
        table.update.return_value = table
        table.eq.return_value = table
        client = mock.MagicMock()
        client.table.return_value = table
        with mock.patch.object(db, "get_product", return_value=produto_atual), \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(worker_main, "import_product", return_value=fresh), \
             mock.patch.object(db, "register_audit") as audit:
            worker_main.process_job(self._job(product_id="p1"))

        table.update.assert_called_once_with({
            "image_url": "https://img/nova.jpg",
            "image_urls": ["https://img/nova.jpg", "https://img/outra.jpg"],
        })
        table.eq.assert_called_once_with("id", "p1")
        audit.assert_called_once()
        self.assertEqual(audit.call_args.kwargs["action"], "produto_imagens_atualizadas")
        self.assertTrue(audit.call_args.kwargs["metadata"]["encontrou_novas"])

    def test_sem_foto_nova_nao_atualiza_mas_registra_tentativa(self):
        produto_atual = {
            "id": "p1", "source_name": "shopee",
            "source_url": "https://shopee.com.br/product/1/1",
        }
        table = mock.MagicMock()
        client = mock.MagicMock()
        client.table.return_value = table
        with mock.patch.object(db, "get_product", return_value=produto_atual), \
             mock.patch.object(db, "_get", return_value=client), \
             mock.patch.object(worker_main, "import_product", return_value={}), \
             mock.patch.object(db, "register_audit") as audit:
            worker_main.process_job(self._job(product_id="p1"))

        table.update.assert_not_called()
        audit.assert_called_once()
        self.assertFalse(audit.call_args.kwargs["metadata"]["encontrou_novas"])


if __name__ == "__main__":
    unittest.main()
