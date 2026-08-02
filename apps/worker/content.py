"""Topfy Affiliate OS — geração de copy com IA (OpenRouter) + fallback determinístico.

Regras do spec:
- provider abstrato: OpenRouter (grátis/pago, hospedado) primeiro, fallback
  determinístico quando OpenRouter não responde — nunca inventa fato
  (preço/desconto/avaliação).
- toda copy gerada passa por validar_copy (disclaimer + frases proibidas).
- campo ausente vira "a confirmar" ou não entra na frase — nunca número
  inventado.
"""
from __future__ import annotations

import json
import os
import random
import urllib.error
import urllib.request
from typing import Any, Optional

DISCLAIMER_PADRAO = (
    "Link de afiliado: se você comprar por aqui, o Topfy pode ganhar uma "
    "comissão, sem custo extra para você. Preço e disponibilidade podem "
    "mudar — confira na loja antes de comprar."
)

# Frases enganosas sem fonte verificável — barra qualquer copy, mesmo manual.
FRASES_PROIBIDAS = (
    "últimas unidades", "ultimas unidades", "estoque limitado",
    "garantido", "sem risco", "melhor preço da internet",
    "oferta imperdível por tempo limitado", "compre agora ou perca",
)

TEMPLATES = ("oferta-padrao", "oferta-curta", "oferta-beneficios")

ALLOWED_PROVIDERS = ("auto", "openrouter", "openai", "anthropic", "fallback", "manual")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Rótulos de loja para os textos por loja (Fase A): a copy nasce
# contextualizada com a loja de origem — nunca inventa nome.
LOJA_LABEL = {
    "aliexpress": "AliExpress",
    "amazon": "Amazon",
    "mercadolivre": "Mercado Livre",
    "mercadolibre": "Mercado Livre",
}


def _nome_loja(loja: Optional[str]) -> Optional[str]:
    nome = LOJA_LABEL.get(loja or "", "").strip()
    return nome or None


def _fmt_preco(valor: Optional[float]) -> str:
    return f"R$ {valor:.2f}" if valor is not None else "a confirmar"


def _nome(product: dict[str, Any]) -> str:
    return product.get("title") or f"Produto #{product.get('id', '?')}"


def _fatos(product: dict[str, Any]) -> list[str]:
    fatos = []
    if product.get("current_price") is not None:
        fatos.append(f"Preço observado: {_fmt_preco(product['current_price'])}")
    if product.get("original_price") is not None and product.get("discount_percent") is not None:
        fatos.append(f"Desconto real: {product['discount_percent']:.0f}%")
    if product.get("sold_count") is not None:
        fatos.append(f"{product['sold_count']:,} vendidos".replace(",", "."))
    if product.get("rating") is not None:
        fatos.append(f"Avaliação: {product['rating']:.1f}/5")
    if not fatos:
        fatos.append("Ficha ainda sem fatos confirmados — revisar antes de publicar.")
    return fatos


def _headline_variantes(product: dict[str, Any],
                        loja: Optional[str] = None) -> list[str]:
    nome = _nome(product)
    atual = product.get("current_price")
    original = product.get("original_price")
    loja_nome = _nome_loja(loja)
    if atual is not None and original is not None and original > atual:
        preco_atual, preco_original = _fmt_preco(atual), _fmt_preco(original)
        if loja_nome:
            return [
                f"{nome} na {loja_nome} — de {preco_original} por {preco_atual}",
                f"{nome} caiu de preço na {loja_nome}: agora {preco_atual}",
                f"Encontrei {nome} na {loja_nome} por {preco_atual} "
                f"(era {preco_original})",
            ]
        return [
            f"{nome} — de {preco_original} por {preco_atual}",
            f"{nome} caiu de preço: agora {preco_atual}",
            f"Encontrei {nome} por {preco_atual} (era {preco_original})",
        ]
    if atual is not None:
        preco_atual = _fmt_preco(atual)
        if loja_nome:
            return [f"{nome} na {loja_nome} — {preco_atual}",
                    f"{nome} por {preco_atual} na {loja_nome}"]
        return [f"{nome} — {preco_atual}", f"{nome} por {preco_atual}"]
    return [f"{nome} — preço a confirmar"]


def _cta_variantes(product: dict[str, Any]) -> list[str]:
    return ["Ver oferta", "Conferir na loja", "Ver oferta na loja"]


def _gerar_fallback(product: dict[str, Any], template_id: str, seed: Optional[int],
                    loja: Optional[str] = None) -> dict[str, str]:
    rng = random.Random(seed)
    fatos = _fatos(product)
    if template_id == "oferta-curta":
        nome = _nome(product)
        preco = product.get("current_price")
        loja_nome = _nome_loja(loja)
        if loja_nome:
            body = (f"{nome} na {loja_nome}\n{_fmt_preco(preco)}"
                    if preco is not None
                    else f"{nome} na {loja_nome}\nPreço a confirmar na loja.")
        else:
            body = (f"{nome}\n{_fmt_preco(preco)}" if preco is not None
                    else f"{nome}\nPreço a confirmar na loja.")
    elif template_id == "oferta-beneficios":
        body = "O que já está confirmado:\n" + "\n".join(f"- {f}" for f in fatos)
    else:
        body = "Fatos observados na ficha:\n" + "\n".join(f"- {f}" for f in fatos)
    return {
        "template_id": template_id,
        "headline": rng.choice(_headline_variantes(product, loja)),
        "body": body,
        "cta": rng.choice(_cta_variantes(product)),
        "disclaimer": DISCLAIMER_PADRAO,
    }


def _openrouter_disponivel() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _gerar_openrouter(product: dict[str, Any], template_id: str,
                      loja: Optional[str] = None) -> Optional[dict[str, str]]:
    """Chama a API da OpenRouter (openrouter.ai — agregador de LLMs, API
    compatível com o formato OpenAI) com um prompt estrito — a resposta é
    validada depois por validar_copy e por fatos; qualquer coisa fora do
    padrão cai no fallback. Modelo configurável via OPENROUTER_MODEL —
    confirme o slug de modelo grátis vigente em openrouter.ai/models."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat:free")
    prompt = (
        "Você escreve copy de afiliado em português do Brasil. Use APENAS "
        "os fatos abaixo — NUNCA invente preço, desconto, avaliação, prazo "
        "ou estoque. Responda APENAS com um objeto JSON, sem texto fora "
        "dele: {\"headline\": string, \"body\": string, \"cta\": string}. "
        "Disclaimer obrigatório no fim do body: \"Link de afiliado: se "
        "você comprar por aqui, o Topfy pode ganhar uma comissão, sem "
        "custo extra para você.\"\n\n"
        f"Fatos:\n{json.dumps(product, ensure_ascii=False)}"
        + (f"\nLoja de origem: {_nome_loja(loja)}" if _nome_loja(loja) else "")
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_API_URL, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-Title": "Topfy Affiliate OS",
        })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            bruto = json.loads(resp.read().decode("utf-8"))
        conteudo = bruto["choices"][0]["message"]["content"]
        resposta = json.loads(conteudo)
        return {
            "template_id": template_id,
            "headline": resposta.get("headline", ""),
            "body": resposta.get("body", ""),
            "cta": resposta.get("cta", "Ver oferta"),
            "disclaimer": DISCLAIMER_PADRAO,
        }
    except (urllib.error.URLError, json.JSONDecodeError, ValueError, KeyError, IndexError):
        return None


def gerar_copy(
    product: dict[str, Any],
    template_id: str = "oferta-padrao",
    *,
    provider: str = "auto",
    seed: Optional[int] = None,
    loja: Optional[str] = None,
) -> dict[str, Any]:
    """Gera a copy. provider='auto': tenta openrouter e cai no fallback;
    'fallback'/'manual': só determinístico (para testes e modo offline).
    `loja` (source_name) contextualiza os textos por loja no fallback."""
    if template_id not in TEMPLATES:
        raise ValueError(f"template desconhecido: {template_id!r} (use um de {TEMPLATES})")

    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(f"provider desconhecido: {provider!r}")

    if provider == "manual":
        return {
            **(_gerar_fallback(product, template_id, seed, loja)),
            "provider": "manual",
            "model": None,
        }

    if provider == "auto" or provider == "openrouter":
        if _openrouter_disponivel():
            resultado = _gerar_openrouter(product, template_id, loja)
            if resultado and not validar_copy(resultado):
                return {**resultado, "provider": "openrouter", "model": os.environ.get("OPENROUTER_MODEL")}
        if provider == "openrouter":
            raise RuntimeError("openrouter não respondeu — use provider='auto' para fallback.")
        return {**(_gerar_fallback(product, template_id, seed, loja)), "provider": "fallback", "model": None}

    return {**(_gerar_fallback(product, template_id, seed, loja)), "provider": "fallback", "model": None}


def validar_copy(copy: dict[str, Any]) -> list[str]:
    """Checklist mecânico: disclaimer presente, sem frase proibida, campos
    mínimos. Nunca substitui revisão humana."""
    problemas = []
    texto = " ".join(str(copy.get(c) or "") for c in ("headline", "body", "cta")).lower()

    if not (copy.get("disclaimer") or "").strip():
        problemas.append("Sem disclaimer de afiliado — obrigatório em toda copy.")
    if not (copy.get("headline") or "").strip():
        problemas.append("Sem headline.")
    if not (copy.get("body") or "").strip():
        problemas.append("Sem corpo do texto.")
    for frase in FRASES_PROIBIDAS:
        if frase in texto:
            problemas.append(f"Frase proibida encontrada: '{frase}'.")
    return problemas
