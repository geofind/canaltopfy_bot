# Benchmark — Achadinho Pro

Estudo realizado em 2 de agosto de 2026 a partir do conteúdo público de
<https://achadinhopro.com.br/>. O objetivo é orientar decisões do Topfy, não
copiar marca, textos, identidade visual ou alegações comerciais do concorrente.

## Leitura do produto

O Achadinho Pro se apresenta como uma plataforma B2B de automação para
afiliados. A landing page conduz o visitante por uma narrativa direta:

1. problema do trabalho manual;
2. fontes de produtos e marketplaces;
3. configuração em quatro passos;
4. recursos de automação e distribuição;
5. comparação de planos, prova social e conversão para teste grátis.

Os pilares comunicados são garimpo próprio, múltiplos marketplaces, geração de
links, distribuição em grupos, segmentação por hashtags, ofertas relâmpago,
deduplicação e reciclagem de produtos. Números de clientes, conversão, comissão
e satisfação exibidos na página são alegações do próprio site e não devem ser
usados como referência factual para o Topfy sem evidência independente.

## O que o Topfy já possui

| Capacidade observada | Situação no Topfy |
| --- | --- |
| Múltiplas fontes | AliExpress, Mercado Livre e Amazon manual |
| Curadoria | Topfy Score com bloqueios de dados incompletos |
| Conteúdo | Copy por IA com fallback e revisão humana |
| Grupos | Cadastro reutilizável de grupos/canais Telegram |
| Cadência | Filas com intervalo mínimo e janela diária |
| Deduplicação | Bloqueio por campanha, canal e grupo |
| Variação de CTA | Frases cadastráveis e sorteadas pelo worker |
| Mensuração | Redirect próprio, cliques, conversões e comissão importada |
| Vitrine | `/ofertas` e landing individual `/c/<slug>` |

## O que foi implementado agora

O dashboard ganhou um ciclo operacional em quatro etapas — **Garimpar,
Aprovar, Distribuir e Medir** — com links para as telas existentes e contagens
reais de produtos, revisões, fila e cliques. A ideia útil absorvida do benchmark
é a clareza do fluxo, não a estética ou o texto do concorrente.

## Próximos diferenciais recomendados

### Prioridade 1 — relevância antes de volume

- tags/nichos em produtos, grupos e filas;
- regra de compatibilidade entre categoria da oferta e público do grupo;
- relatório por categoria, grupo e horário;
- lista de produtos personalizados com origem e prazo de validade.

### Prioridade 2 — re-commerce supervisionado

- cooldown configurável por grupo;
- republicação apenas quando houver regra explícita;
- candidatos a reciclagem baseados em sinais first-party;
- revisão humana antes de reativar uma campanha;
- trilha completa em `audit_log`.

### Prioridade 3 — expansão de canais

- WhatsApp Business Cloud API com opt-in e templates aprovados;
- Instagram, TikTok e YouTube somente após aprovação oficial dos aplicativos;
- métricas normalizadas por canal, sem comparar números incompatíveis.

## O que não deve ser reproduzido

- alegações de conversão, comissão ou economia sem dados verificáveis;
- automação baseada em captura proibida pelos marketplaces;
- sessões não oficiais do WhatsApp ou promessas de “anti-ban”;
- geração de link tratada como prova de atribuição ou comissão;
- reciclagem automática sem cooldown, relevância e aprovação humana.

## Decisão de posicionamento

O Topfy deve se diferenciar como **sistema operacional supervisionado de
afiliados**: menos promessa de volume e mais rastreabilidade, curadoria própria,
transparência de dados e controle humano. O fluxo recomendado é:

```text
produto com fonte → score e bloqueios → aprovação → fila segmentada
→ publicação rastreada → aprendizado → manter, ajustar ou arquivar
```
