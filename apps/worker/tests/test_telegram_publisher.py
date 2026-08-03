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


class MontarMensagemTests(unittest.TestCase):
    """Link do redirect first-party agora vai por EXTENSO na mensagem
    (texto visível com 🔗), não mais escondido atrás do texto do CTA."""

    def test_link_aparece_por_extenso(self):
        msg = telegram._montar_mensagem(COPY, "https://x/r/1")
        self.assertIn("🔗 https://x/r/1", msg)
        self.assertNotIn("<a href", msg)

    def test_cta_aparece_como_linha_separada_antes_do_link(self):
        msg = telegram._montar_mensagem(COPY, "https://x/r/1")
        pos_cta = msg.find(COPY["cta"])
        pos_link = msg.find("🔗 https://x/r/1")
        self.assertGreater(pos_cta, -1)
        self.assertLess(pos_cta, pos_link)

    def test_cta_vazio_nao_deixa_linha_em_branco_sobrando(self):
        copy_sem_cta = {**COPY, "cta": ""}
        msg = telegram._montar_mensagem(copy_sem_cta, "https://x/r/1")
        self.assertNotIn("\n\n\n", msg)

    def test_disclaimer_aparece_no_final(self):
        msg = telegram._montar_mensagem(COPY, "https://x/r/1")
        self.assertTrue(msg.rstrip().endswith(f"<i>{COPY['disclaimer']}</i>"))


class LimiteLegendaTests(unittest.TestCase):
    """Regressão: o sendPhoto do Telegram rejeita caption com mais de 1024
    caracteres (HTTP 400 "message caption is too long"); a legenda tem que
    ser reduzida sempre preservando o link de afiliado (onde o clique
    acontece) e o disclaimer."""

    COPY_LONGA = {
        "headline": "Headline muito longa " * 10,
        "body": " ".join([f"palavra{m}" for m in range(400)]),
        "cta": "Aproveite essa oferta incrível agora! " * 20,
        "disclaimer": "Parceria com a loja via link de afiliado.",
    }

    def test_legenda_limita_a_1024(self):
        msg = telegram._montar_mensagem(self.COPY_LONGA, "https://x/r/1")
        self.assertLessEqual(len(msg), telegram.MAX_CAPTION_CHARS)

    def test_link_e_disclaimer_preservados(self):
        msg = telegram._montar_mensagem(self.COPY_LONGA, "https://x/r/link-final")
        self.assertIn("🔗 https://x/r/link-final", msg)
        self.assertTrue(msg.rstrip().endswith(
            f"<i>{self.COPY_LONGA['disclaimer']}</i>"))

    def test_texto_curto_nao_e_cortado(self):
        msg = telegram._montar_mensagem(COPY, "https://x/r/1")
        self.assertIn("Produto X", msg)
        self.assertIn(COPY["body"], msg)
        self.assertLessEqual(len(msg), telegram.MAX_CAPTION_CHARS)

    def test_truncar_nao_deixa_entidade_html_cortada(self):
        texto = "&amp;" * 300  # 1200 chars escapados — quebra depois do &amp; do meio
        corpo = telegram._truncar_html_seguro(texto, 200)
        self.assertFalse(corpo.rstrip("…").endswith("&"))
        self.assertLessEqual(len(corpo), 200)


class DetectarTipoImagemTests(unittest.TestCase):
    """Foto real do produto (sem card renderizado) pode vir em qualquer
    formato da CDN da loja — o multipart do sendPhoto precisa declarar o
    tipo certo, não mais assumir 'card.png' fixo."""

    def test_detecta_jpeg(self):
        self.assertEqual(
            telegram._detectar_tipo_imagem(b"\xff\xd8\xff\xe0resto"),
            ("jpg", "image/jpeg"))

    def test_detecta_png(self):
        self.assertEqual(
            telegram._detectar_tipo_imagem(b"\x89PNG\r\n\x1a\nresto"),
            ("png", "image/png"))

    def test_detecta_webp(self):
        self.assertEqual(
            telegram._detectar_tipo_imagem(b"RIFF\x00\x00\x00\x00WEBPresto"),
            ("webp", "image/webp"))

    def test_desconhecido_cai_em_jpeg(self):
        self.assertEqual(
            telegram._detectar_tipo_imagem(b"lixo qualquer"),
            ("jpg", "image/jpeg"))


class BaixarImagemTests(unittest.TestCase):
    """A foto real do produto (não mais o card /og/card) é baixada sem
    'image/webp' no Accept — mesma razão do og/card: sem isso, a CDN da
    loja pode servir webp, que quebraria a publicação no Telegram."""

    def test_accept_nao_pede_webp(self):
        capturado = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"fake-bytes"

        def fake_urlopen(req, timeout=None):
            capturado["accept"] = req.get_header("Accept")
            return FakeResp()

        with mock.patch.object(telegram.urllib.request, "urlopen", side_effect=fake_urlopen):
            resultado = telegram._baixar_imagem("https://loja.example/foto.jpg")

        self.assertEqual(resultado, b"fake-bytes")
        self.assertNotIn("webp", capturado["accept"])


if __name__ == "__main__":
    unittest.main()
