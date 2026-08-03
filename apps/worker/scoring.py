"""Topfy Affiliate OS — motor de score (spec do usuário, Topfy Score).

Pesos aprovados no spec (somam 100):
- desconto real     20%
- vendas            15%
- avaliação         15%
- comissão          15%
- tendência         10%
- apelo visual      10%
- concorrência      10%
- confiabilidade     5%

Score decomposto e explicável (nunca só um número). Dimensões alimentadas
por evidência real — nenhum componente é inventado; quando o dado falta,
a dimensão zera com aviso explícito.
"""
from __future__ import annotations

import math
from typing import Any, Optional

PESO_MAXIMO = {
    "desconto_real": 20,
    "vendas": 15,
    "avaliacao": 15,
    "comissao": 15,
    "tendencia": 10,
    "apelo_visual": 10,
    "concorrencia": 10,
    "confiabilidade": 5,
}
assert sum(PESO_MAXIMO.values()) == 100

# Referência de comissão alta para afiliados (a maioria dos produtos
# AliExpress fica entre 3% e 9%) — acima disso satura no teto do peso.
TETO_COMISSAO_PCT = 20.0


def _desconto_real(product: dict[str, Any]) -> tuple[float, Optional[str]]:
    """Desconto REAL (20%): compara o preço atual com o preço original
    confirmado pela fonte — nunca usa percentual declarado pelo vendedor
    sem cruzamento com preços reais."""
    atual = product.get("current_price")
    original = product.get("original_price")
    if atual is None or original is None or original <= 0:
        return 0.0, "Sem preços confirmados (atual/original) para calcular desconto real."
    desconto = max(0.0, (original - atual) / original)
    return round(min(desconto, 1.0) * PESO_MAXIMO["desconto_real"], 1), None


#  Categoria marcada como "priorizar mais vendidos" na curadoria
#  (/campanhas) multiplica o teto da dimensão "vendas" por isso — reforça
#  o peso sem alterar PESO_MAXIMO (spec aprovado, some 100) pros produtos
#  de categorias sem essa prioridade.
BONUS_VENDAS_CATEGORIA_PRIORIZADA = 2.0


def _vendas(product: dict[str, Any], *, prioritize_bestsellers: bool = False,
           ) -> tuple[float, Optional[str]]:
    """Vendas (15%, dobra pra categorias marcadas como prioridade de mais
    vendidos): contagem de vendas da fonte, escala logarítmica — 10
    vendas já pontua algo, milhares satura."""
    sold = product.get("sold_count")
    if sold is None:
        return 0.0, "Sem contagem de vendas confirmada — dimensão zerada."
    teto = PESO_MAXIMO["vendas"] * (
        BONUS_VENDAS_CATEGORIA_PRIORIZADA if prioritize_bestsellers else 1.0)
    pontos = min(teto, math.log10(max(sold, 1) + 1) * 3.5)
    return round(pontos, 1), None


def _avaliacao(product: dict[str, Any]) -> tuple[float, Optional[str]]:
    """Avaliação (15%): nota 0-5 ou taxa de feedback positivo (0-100%),
    conforme a fonte devolver — sempre dado real, nunca convertido às cegas."""
    rating = product.get("rating")
    if rating is not None:
        pontos = max(0.0, min(float(rating), 5.0)) / 5.0 * PESO_MAXIMO["avaliacao"]
        return round(pontos, 1), None
    positivo = product.get("positive_feedback_percent")
    if positivo is not None:
        pontos = max(0.0, min(float(positivo), 100.0)) / 100.0 * PESO_MAXIMO["avaliacao"]
        return round(pontos, 1), (
            "Sem avaliação 1-5 estrelas — usando taxa de feedback positivo "
            "da fonte como aproximação.")
    return 0.0, "Sem avaliação confirmada — dimensão zerada."


def _comissao(product: dict[str, Any], affiliate_link: Optional[dict[str, Any]]) -> tuple[float, Optional[str]]:
    """Comissão (15%): percentual de comissão confirmado pela fonte."""
    if not affiliate_link:
        return 0.0, "Sem link de afiliado ainda — comissão zerada."
    comissao = product.get("commission_percent")
    if comissao is None:
        return 0.0, "Percentual de comissão não disponível — confirmar manualmente."
    pontos = min(
        PESO_MAXIMO["comissao"],
        (max(float(comissao), 0.0) / TETO_COMISSAO_PCT) * PESO_MAXIMO["comissao"],
    )
    return round(pontos, 1), None


def _tendencia(product: dict[str, Any]) -> tuple[float, Optional[str]]:
    """Tendência (10%): sinal externo registrado (FlowSpy/Google Trends),
    método MANUAL ou API autorizada. Sem sinal registrado, fica neutro
    (meio da faixa) com aviso — nunca inventa tendência."""
    sinal = product.get("trend_signal")
    if sinal is None:
        return float(PESO_MAXIMO["tendencia"]) / 2, (
            "Sem sinal de tendência registrado (importar manualmente ou via "
            "fonte autorizada).")
    pontos = max(0.0, min(float(sinal), 1.0)) * PESO_MAXIMO["tendencia"]
    return round(pontos, 1), None


def _apelo_visual(product: dict[str, Any]) -> tuple[float, Optional[str]]:
    """Apelo visual (10%): presença e qualidade real da imagem do produto.
    Sem imagem, zera com aviso."""
    imagem = product.get("main_image_url")
    if not imagem:
        return 0.0, "Sem imagem do produto — apelo visual zerado."
    return float(PESO_MAXIMO["apelo_visual"]), None


def _concorrencia(product: dict[str, Any]) -> tuple[float, Optional[str]]:
    """Concorrência (10%): quanto MENOR o total de vendas/avaliações em
    relação à categoria, menor a concorrência percebida — sinal indireto.
    Sem dados suficientes, fica neutro com aviso."""
    vendas = product.get("sold_count")
    if vendas is None:
        return float(PESO_MAXIMO["concorrencia"]) / 2, (
            "Sem dados para medir concorrência — neutro.")
    # Produtos com poucas vendas têm menos concorrência de destaque;
    # satura em ~5k vendas (produto consolidado = concorrência alta).
    concorrencia_percebida = min(vendas / 5000.0, 1.0)
    pontos = (1.0 - concorrencia_percebida) * PESO_MAXIMO["concorrencia"]
    return round(pontos, 1), None


def _confiabilidade(product: dict[str, Any]) -> tuple[float, Optional[str]]:
    """Confiabilidade (5%): confiança da fonte do dado (VERIFIED da API
    oficial vale 100% da dimensão; UNKNOWN/NOT_AVAILABLE pontuam menos)."""
    confidence = product.get("source_confidence")
    mapa = {"VERIFIED": 1.0, "STALE": 0.5, "UNKNOWN": 0.2,
            "NOT_AVAILABLE": 0.0, "NOT_SUPPORTED": 0.0}
    fator = mapa.get(confidence, 0.0)
    aviso = None if confidence == "VERIFIED" else f"Fonte com confiança '{confidence}' — não é VERIFIED."
    return round(fator * PESO_MAXIMO["confiabilidade"], 1), aviso


def calcular_score(
    product: dict[str, Any],
    affiliate_link: Optional[dict[str, Any]] = None,
    *,
    prioritize_bestsellers: bool = False,
) -> dict[str, Any]:
    """Devolve o score decomposto (nunca só o total), avisos e bloqueios.

    `prioritize_bestsellers` vem da curadoria do Laboratório de Captura
    (/campanhas) por categoria — reforça o teto da dimensão "vendas" pra
    esse produto sem mexer no PESO_MAXIMO global.

    Bloqueios (impedem aprovação, não só reduzem score):
    - link de afiliado não VERIFIED;
    - produto sem dados mínimos (sem preço confirmado)."""
    dimensoes: dict[str, float] = {}
    avisos: list[str] = []

    for campo, (valor, aviso) in {
        "desconto_real": _desconto_real(product),
        "vendas": _vendas(product, prioritize_bestsellers=prioritize_bestsellers),
        "avaliacao": _avaliacao(product),
        "comissao": _comissao(product, affiliate_link),
        "tendencia": _tendencia(product),
        "apelo_visual": _apelo_visual(product),
        "concorrencia": _concorrencia(product),
        "confiabilidade": _confiabilidade(product),
    }.items():
        dimensoes[campo] = valor
        if aviso:
            avisos.append(aviso)

    score_total = sum(dimensoes.values())

    bloqueios: list[str] = []
    status_link = (affiliate_link or {}).get("verification_status")
    if status_link != "VERIFIED":
        bloqueios.append(
            "Rastreamento do link de afiliado não verificado "
            f"(status atual: {status_link or 'nenhum link'}) — aprovação bloqueada até validar.")
    if product.get("current_price") is None:
        bloqueios.append("Sem preço confirmado — não é possível aprovar.")

    tetos = dict(PESO_MAXIMO)
    if prioritize_bestsellers:
        tetos["vendas"] *= BONUS_VENDAS_CATEGORIA_PRIORIZADA
    resumo = "; ".join(
        f"{campo} {valor:.0f}/{tetos[campo]:.0f}"
        for campo, valor in dimensoes.items())
    reason_summary = f"Topfy Score {score_total:.0f}: {resumo}."

    return {
        **dimensoes,
        "score_total": round(score_total, 1),
        "reason_summary": reason_summary,
        "warnings": avisos,
        "bloqueios": bloqueios,
    }
