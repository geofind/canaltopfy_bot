"""Topfy Affiliate OS — publicação no Telegram (Bot API oficial).

Portado do CanalTopfy Lab (scripts/cupons/telegram_publisher.py), adaptado
para o schema Supabase (publications). stdlib apenas (urllib), retry com
retry_after em FloodWait/429, token nunca aparece em log/erro.

CTA usa o redirect first-party do Topfy (/r/<id>) — nunca link de afiliado
bruto na mensagem. Nunca publica a mesma campanha duas vezes no mesmo canal.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from connectors import CredencialNaoConfigurada

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_TENTATIVAS = 3


def _token() -> Optional[str]:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def _chamar_api(metodo: str, payload: dict[str, Any], *,
                sleep_fn: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    token = _token()
    if not token:
        raise CredencialNaoConfigurada(
            "telegram: TELEGRAM_BOT_TOKEN não configurado — crie um bot no "
            "@BotFather e defina a variável de ambiente.")
    url = f"{TELEGRAM_API_BASE}/bot{token}/{metodo}"
    body = json.dumps(payload).encode("utf-8")
    ultimo_erro: Optional[Exception] = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            corpo = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                try:
                    retry_after = json.loads(corpo).get(
                        "parameters", {}).get("retry_after", 2 * tentativa)
                except json.JSONDecodeError:
                    retry_after = 2 * tentativa
                ultimo_erro = RuntimeError(
                    f"telegram {metodo}: FloodWait, retry_after={retry_after}s")
                if tentativa < MAX_TENTATIVAS:
                    sleep_fn(retry_after)
                    continue
                raise ultimo_erro
            raise RuntimeError(
                f"telegram {metodo} falhou (HTTP {exc.code}): {corpo[:300]}") from None
        except urllib.error.URLError as exc:
            ultimo_erro = RuntimeError(f"telegram {metodo} inacessível: {exc}")
            if tentativa < MAX_TENTATIVAS:
                sleep_fn(1.5 * tentativa)
                continue
            raise ultimo_erro
    raise ultimo_erro or RuntimeError(f"telegram {metodo}: falha desconhecida")


def testar_bot() -> dict[str, Any]:
    """getMe — confirma token válido sem enviar mensagem."""
    resposta = _chamar_api("getMe", {})
    if not resposta.get("ok"):
        raise RuntimeError(f"telegram getMe respondeu ok=false: {resposta.get('description')}")
    return resposta["result"]


def descobrir_chats(offset: int = -1) -> list[dict[str, Any]]:
    """getUpdates — lista os chats únicos em que o bot está presente.

    Para grupos privados com link de convite (t.me/+...): adicione o bot
    ao grupo e envie UMA mensagem qualquer no grupo (ou adicione um membro);
    o evento aparece aqui com o chat.id numérico (negativo)."""
    resposta = _chamar_api("getUpdates", {
        "offset": offset, "timeout": 1, "allowed_updates": ["message",
                                                            "channel_post",
                                                            "my_chat_member",
                                                            "chat_member"]})
    if not resposta.get("ok"):
        raise RuntimeError(
            f"telegram getUpdates respondeu ok=false: {resposta.get('description')} "
            "(webhook ativo impede getUpdates — remova o webhook primeiro)")
    chats: dict[int, dict[str, Any]] = {}
    for update in resposta.get("result", []):
        for chave in ("message", "channel_post", "edited_message",
                      "my_chat_member", "chat_member"):
            evento = update.get(chave)
            if not isinstance(evento, dict):
                continue
            chat = evento.get("chat")
            if isinstance(chat, dict) and chat.get("id") is not None:
                chats[chat["id"]] = {
                    "id": chat["id"],
                    "type": chat.get("type"),
                    "title": chat.get("title") or chat.get("username") or "",
                }
    return list(chats.values())


def _escapar_html(texto: str) -> str:
    return (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _montar_mensagem(copy: dict[str, Any], redirect_url: str) -> str:
    headline = copy.get("headline") or ""
    body = copy.get("body") or ""
    cta = copy.get("cta") or "Ver oferta"
    disclaimer = copy.get("disclaimer") or ""
    return (f"<b>{_escapar_html(headline)}</b>\n\n{_escapar_html(body)}\n\n"
            f"<a href=\"{redirect_url}\">{_escapar_html(cta)}</a>\n\n"
            f"<i>{_escapar_html(disclaimer)}</i>")


def publicar_oferta_telegram(
    *,
    copy: dict[str, Any],
    chat_id: str,
    redirect_url: str,
    image_url: Optional[str] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Publica a cópia aprovada no canal/grupo `chat_id`. `redirect_url`
    deve ser URL ABSOLUTA do redirect first-party (/r/<id>). Devolve
    {'external_message_id': ...} — a persistência na tabela publications
    é responsabilidade do pipeline."""
    if not chat_id:
        raise ValueError("publicar no Telegram exige 'chat_id' (canal/grupo de destino)")

    mensagem = _montar_mensagem(copy, redirect_url)

    if image_url:
        resposta = _chamar_api("sendPhoto", {
            "chat_id": chat_id, "photo": image_url, "caption": mensagem,
            "parse_mode": "HTML"}, sleep_fn=sleep_fn)
    else:
        resposta = _chamar_api("sendMessage", {
            "chat_id": chat_id, "text": mensagem, "parse_mode": "HTML",
            "disable_web_page_preview": False}, sleep_fn=sleep_fn)

    if not resposta.get("ok"):
        motivo = resposta.get("description") or "resposta sem 'ok'"
        raise RuntimeError(f"telegram recusou a publicação: {motivo}")

    return {"external_message_id": str(resposta["result"]["message_id"])}


if __name__ == "__main__":
    """CLI de diagnóstico: python -m publishers.telegram [find-chat|bot]

    find-chat: lista os chats em que o bot está (grupo privado aparece
    depois que o bot entra nele e alguém manda mensagem).
    bot: confirma o token (getMe)."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if env_path.is_file():
        for linha in env_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip())

    comando = sys.argv[1] if len(sys.argv) > 1 else "find-chat"

    if comando == "bot":
        bot = testar_bot()
        print(f"bot: @{bot.get('username')} ({bot.get('first_name')}) — token OK")
    elif comando == "find-chat":
        chats = descobrir_chats()
        if not chats:
            print("Nenhum chat encontrado. Adicione o bot ao grupo e envie "
                  "uma mensagem nele (ou adicione um membro), depois rode "
                  "de novo.")
        for chat in chats:
            print(f"{chat['id']}  [{chat['type']}]  {chat['title']}")
    else:
        print(f"comando desconhecido: {comando}")
        sys.exit(1)
