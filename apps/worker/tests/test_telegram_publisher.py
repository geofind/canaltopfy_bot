"""Testes do publisher do Telegram — sem rede (urllib mockado)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

for chave in ("TELEGRAM_BOT_TOKEN",):
    os.environ.setdefault(chave, "fake-token")

import publishers.telegram as telegram  # noqa: E402

COPY = {
    "headline": "Produto X",
    "body": "de R$ 10 por R$ 5",
    "cta": "Ver oferta",
    "disclaimer": "Link de afiliado.",
}


class PublicarOfertaSemFotoTests(unittest.TestCase):
    """Regressão: quando o download do card falha (sem foto), a mensagem
    de texto puro tem que ir com preview de link DESLIGADO — senão o
    Telegram gera uma prévia da página de origem (loja) a partir do link
    de afiliado no CTA, expondo o site/texto de terceiro no post."""

    def test_fallback_sem_foto_desliga_preview_de_link(self):
        capturados = []

        def fake_chamar_api(metodo, payload, *, sleep_fn=None):
            capturados.append((metodo, payload))
            return {"ok": True, "result": {"message_id": 42}}

        with mock.patch.object(telegram, "_baixar_imagem", return_value=None), \
             mock.patch.object(telegram, "_chamar_api", side_effect=fake_chamar_api):
            telegram.publicar_oferta_telegram(
                copy=COPY, chat_id="-100123", redirect_url="https://x/r/1",
                image_url="https://x/og/card/1")

        metodo, payload = capturados[0]
        self.assertEqual(metodo, "sendMessage")
        self.assertTrue(payload["disable_web_page_preview"])

    def test_com_foto_usa_sendphoto(self):
        with mock.patch.object(telegram, "_baixar_imagem", return_value=b"fake-bytes"), \
             mock.patch.object(telegram, "_chamar_api_multipart",
                              return_value={"ok": True, "result": {"message_id": 7}}) as multipart:
            telegram.publicar_oferta_telegram(
                copy=COPY, chat_id="-100123", redirect_url="https://x/r/1",
                image_url="https://x/og/card/1")
        multipart.assert_called_once()


if __name__ == "__main__":
    unittest.main()
