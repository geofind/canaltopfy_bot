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
    """R$ no padrão brasileiro (vírgula decimal, ponto de milhar) — ex.:
    R$ 1.799,00, não R$ 1799.00."""
    if valor is None:
        return "a confirmar"
    txt = f"{valor:,.2f}"  # "1,799.00" (formato US: vírgula=milhar, ponto=decimal)
    txt = txt.replace(",", "@").replace(".", ",").replace("@", ".")
    return f"R$ {txt}"


def _nome(product: dict[str, Any]) -> str:
    return product.get("title") or f"Produto #{product.get('id', '?')}"


# "vendidos" só ajuda a vender quando é um número que impressiona — "0
# vendidos" ou "2 vendidos" passa a impressão contrária. Sem fonte pra
# definir "muitos" de forma objetiva, usa um piso conservador.
VENDAS_MINIMO_PARA_EXIBIR = 20


def _fatos_extras(product: dict[str, Any]) -> list[str]:
    """Fatos além do preço (que já vai na linha ❌/💸) — usado só no
    template "oferta-beneficios" como complemento."""
    fatos = []
    if (product.get("sold_count") is not None
            and product["sold_count"] >= VENDAS_MINIMO_PARA_EXIBIR):
        fatos.append(f"{product['sold_count']:,} vendidos".replace(",", "."))
    if product.get("rating") is not None:
        fatos.append(f"Avaliação: {product['rating']:.1f}/5")
    return fatos


def _linha_preco(product: dict[str, Any]) -> Optional[str]:
    """Linha "❌de R$ X | 💸por R$ Y 🔥" — nunca inventa desconto: o preço
    original só entra se vier confirmado E for maior que o atual."""
    atual = product.get("current_price")
    if atual is None:
        return None
    original = product.get("original_price")
    nota = (product.get("payment_note") or "").strip()
    partes = []
    if original is not None and original > atual:
        partes.append(f"❌de {_fmt_preco(original)}")
    partes.append(f"💸por {_fmt_preco(atual)} 🔥" + (f" {nota}" if nota else ""))
    return " | ".join(partes)


def _linhas_cupom(product: dict[str, Any]) -> list[str]:
    """Linha(s) de cupom — só aparece se um cupom real estiver cadastrado
    (product['coupons'] ou coupon_code); nunca inventado. Mais de um
    cupom vira uma linha "ou" por cupom extra, como nos canais de
    ofertas (ex.: cupom exclusivo Meli+ + cupom geral)."""
    cupons = product.get("coupons") or (
        [{"code": product["coupon_code"], "label": product.get("coupon_label")}]
        if product.get("coupon_code") else [])
    linhas = []
    for i, cupom in enumerate(cupons):
        codigo = cupom.get("code") if isinstance(cupom, dict) else cupom
        if not codigo:
            continue
        rotulo = cupom.get("label") if isinstance(cupom, dict) else None
        prefixo = "🎟️Use o cupom: " if i == 0 else "🎟️ou "
        sufixo = f" ({rotulo})" if rotulo else ""
        linhas.append(f"{prefixo}{codigo}{sufixo}")
    return linhas


def _headline_variantes(product: dict[str, Any],
                        loja: Optional[str] = None) -> list[str]:
    """🚨 chama atenção — o gancho engraçado/irônico de verdade fica a
    cargo da IA (prompt em _gerar_openrouter); o fallback determinístico
    (sem IA) fica no formato simples e honesto de sempre."""
    nome = _nome(product)
    sufixo = f" na {loja_nome}" if (loja_nome := _nome_loja(loja)) else ""
    return [f"🚨 {nome}{sufixo}", f"🔥 {nome}{sufixo}", f"👀 {nome}{sufixo}"]


def _cta_variantes(product: dict[str, Any]) -> list[str]:
    return ["Ver oferta", "Conferir na loja", "Ver oferta na loja"]


def _gerar_fallback(product: dict[str, Any], template_id: str, seed: Optional[int],
                    loja: Optional[str] = None) -> dict[str, str]:
    rng = random.Random(seed)
    linha_preco = _linha_preco(product)
    partes = [linha_preco] if linha_preco else ["Preço a confirmar na loja."]
    partes.extend(_linhas_cupom(product))

    if template_id == "oferta-beneficios":
        extras = _fatos_extras(product)
        if extras:
            partes.append("\n".join(f"- {f}" for f in extras))

    body = "\n\n".join(partes)
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
        "Você escreve legendas de oferta pra um canal de Telegram "
        "brasileiro de achadinhos/cupons — tom direto, informal, com "
        "emojis, no estilo desses canais. Use APENAS os fatos abaixo — "
        "NUNCA invente preço, desconto, avaliação, cupom, prazo ou "
        "estoque; se um dado não estiver nos fatos, simplesmente não "
        "mencione. Responda APENAS com um objeto JSON, sem texto fora "
        "dele: {\"headline\": string, \"body\": string, \"cta\": string}.\n\n"
        "- headline: uma linha curta e chamativa com 1-2 emojis — pode ser "
        "leve, engraçada ou uma dica de uso pra esse produto específico "
        "(ex.: \"🧻 Pra não sair ensopando o banheiro inteiro\"); se não "
        "tiver uma ideia boa e específica pro produto, use só "
        "\"🚨 <nome do produto>\". NUNCA invente um motivo/característica "
        "que não esteja nos fatos ou no nome do produto.\n"
        "- body: se a headline foi uma piada/dica (não o nome do produto), "
        "comece o body com o nome do produto; depois a linha de preço no "
        "formato \"❌de R$ X,XX | 💸por R$ Y,YY 🔥\" (formato brasileiro, "
        "vírgula decimal — inclua o \"❌de\" só se houver preço original "
        "nos fatos, maior que o atual); se os fatos tiverem cupom(ns), "
        "adicione uma linha \"🎟️Use o cupom: CODIGO\" por cupom (a partir "
        "do segundo, use \"🎟️ou CODIGO\"). Só mencione quantidade vendida "
        "(sold_count) se for um número que realmente impressiona (dezenas "
        "ou mais) — nunca escreva \"0 vendidos\" ou uma contagem baixa, "
        "nesse caso simplesmente omita.\n"
        "- cta: chamada curta (ex.: \"Ver oferta\").\n\n"
        "Não inclua o disclaimer de afiliado — ele é adicionado depois "
        "automaticamente.\n\n"
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


def _imagem_quality_check_ativado() -> bool:
    return os.environ.get("IMAGE_QUALITY_CHECK_ENABLED", "").lower() in ("1", "true", "yes")


def _imagem_tem_marca_ou_texto(url: str) -> Optional[bool]:
    """Pergunta pra um modelo de visão (OpenRouter) se a foto tem texto
    sobreposto (banner/chamada de marketing) ou marca/logo estampada —
    best-effort: None se a checagem falhar (sem chave, modelo
    indisponível, timeout, resposta fora do padrão); nunca derruba a
    escolha de imagem por causa disso. Modelo configurável via
    OPENROUTER_VISION_MODEL (precisa suportar entrada de imagem)."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return None
    model = os.environ.get("OPENROUTER_VISION_MODEL", "google/gemini-2.0-flash-exp:free")
    prompt = (
        "Esta é uma foto de produto de e-commerce. Ela tem texto "
        "sobreposto (banners, chamadas tipo \"Wireless Fast Charging\", "
        "preço) ou uma marca/logo do vendedor estampada visivelmente na "
        "imagem (não apenas no produto físico em si)? Responda APENAS "
        "com um JSON: {\"tem_marca_ou_texto\": true ou false}."
    )
    body = json.dumps({
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }],
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            bruto = json.loads(resp.read().decode("utf-8"))
        conteudo = bruto["choices"][0]["message"]["content"]
        resposta = json.loads(conteudo)
        return bool(resposta.get("tem_marca_ou_texto"))
    except (urllib.error.URLError, json.JSONDecodeError, ValueError, KeyError, IndexError):
        return None


def escolher_imagem_limpa(product: dict[str, Any], *,
                         checar: Any = _imagem_tem_marca_ou_texto) -> Optional[str]:
    """Tenta achar, entre as fotos da galeria do produto (image_urls),
    uma sem texto/marca sobreposta — OPT-IN via IMAGE_QUALITY_CHECK_
    ENABLED (custa 1 chamada de IA por foto candidata, então desligado
    por padrão). Sem isso ligado, ou se nenhuma checagem vier False, cai
    na imagem principal de sempre — nunca deixa o produto sem imagem por
    causa disso."""
    principal = product.get("main_image_url") or product.get("image_url")
    if not _imagem_quality_check_ativado():
        return principal

    candidatas: list[str] = [principal] if principal else []
    extra = product.get("image_urls")
    if extra:
        try:
            lista = json.loads(extra) if isinstance(extra, str) else extra
            candidatas.extend(lista)
        except (json.JSONDecodeError, TypeError):
            pass

    vistas: set[str] = set()
    for url in candidatas:
        if not url or url in vistas:
            continue
        vistas.add(url)
        if checar(url) is False:
            return url
    return principal
