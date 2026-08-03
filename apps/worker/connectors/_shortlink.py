"""Topfy Affiliate OS — resolução de short-links (redirects) compartilhada.

Segue o redirect do link curto só pelos cabeçalhos Location (nunca baixa o
body). Best-effort: falha -> None, e o chamador decide o fallback.
Usado por Mercado Livre (meli.la) e AliExpress (s.click/a.aliexpress).
"""
from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any, Optional

REDIRECT_MAX = 5
REDIRECT_TIMEOUT = 12


class _RedirectCapturado(Exception):
    def __init__(self, url: str) -> None:
        super().__init__(url)
        self.url = url


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    """Captura o Location do redirect sem seguir automaticamente — o
    chamador decide a próxima URL (loop com limite)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl) -> Any:
        raise _RedirectCapturado(newurl)


def resolve_shortlink(url: str, max_redirects: int = REDIRECT_MAX,
                      timeout: int = REDIRECT_TIMEOUT) -> Optional[str]:
    """Segue redirects do link curto e devolve o URL final. Se não houver
    redirect (200 direto) ou a cadeia terminar, retorna o URL final.
    Falha de rede/limite -> None (best-effort)."""
    for _ in range(max_redirects):
        try:
            opener = urllib.request.build_opener(_NoAutoRedirect())
            req = urllib.request.Request(
                url, headers={"User-Agent": "TopfyAffiliateOS/0.1",
                              "Accept": "text/html,*/*"})
            with opener.open(req, timeout=timeout) as resp:
                return resp.geturl()
        except _RedirectCapturado as r:
            url = r.url
            continue
        except (urllib.error.URLError, urllib.error.HTTPError,
                OSError, ValueError):
            return None
    return None