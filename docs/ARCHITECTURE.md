# Arquitetura

## Visão geral

Monorepo com três componentes:

1. **apps/web** — Next.js 16 (App Router, SSR), Tailwind + shadcn/ui.
   - Dashboard autenticado (Supabase Auth) para o dono do negócio;
   - Vitrine pública `/c/<slug>` (landing do produto) e redirect first-party `/r/<id>`;
   - Card de produto via `next/og` (`ImageResponse`, embutido no Next.js) —
     rota própria, sem serviço externo nem conta/credencial;
   - Server Actions / API routes chamam o Postgres (Supabase) com RLS;
   - **Nenhum segredo no frontend** — chaves de integração ficam no worker.
2. **apps/worker** — Python 3.11, consome a fila `jobs` (Postgres, sem Redis
   no MVP) e executa: importação, geração de link de afiliado, Topfy Score,
   copy (OpenRouter + fallback), publicação.
3. **packages/db** — migrations PostgreSQL aplicadas no Supabase.

## Fluxo da campanha (Fase 1)

```
[web] cola URL -> INSERT products (IMPORTED) + job product.import
[worker] valida via conector (API oficial ou MANUAL) -> READY
[worker] gera link de afiliado (VERIFIED só com API) -> atualiza products
[worker] Topfy Score -> score + score_breakdown
[worker] 3 cópias (openrouter -> fallback) -> contents PENDING_REVIEW
[web] humana aprova (REVIEW_REQUIRED -> APPROVED)
[web] agenda publicação -> job publication.telegram
[worker] publica -> publications PUBLISHED -> campaigns PUBLISHED
[web] /r/<id> registra affiliate_clicks; vitrine /c/<slug> pública
```

## Fila

Tabela `jobs` no Postgres (MVP): `status pending/running/done/failed`,
`attempts`, `max_attempts`, `scheduled_for`. O worker dá polling a cada 5s.
Requer service_role key (escrita no banco pelo worker).

## Integrações (todas com modo simulated)

| Plataforma | Fase | Status |
| --- | --- | --- |
| AliExpress Affiliate API | 1 | **REAL** (validada ao vivo no lab) |
| Telegram Bot API | 1 | **REAL** (validada ao vivo no lab) |
| WhatsApp (wa.me + Cloud API) | 1/2 | assistido no MVP; Cloud API na Fase 2 |
| `next/og` (cards) | 1 | embutido no Next.js, MIT, custo zero |
| OpenRouter (copy) | 1 | modelo grátis (DeepSeek); sem key cai no fallback |
| Amazon Creators API | 2 | mock até elegibilidade (10 vendas/30 dias) |
| TikTok Content Posting | 2 | mock (exige auditoria) |
| Instagram Graph API | 2 | mock (exige App Review) |
| YouTube Data API | 2 | mock |
| GA4 / Google Ads | 4 | adiado |

## Decisões-chave

- **Fila no Postgres** em vez de Redis: menos peças no MVP; migração para
  Redis/Temporal quando houver volume.
- **OpenRouter (hospedado, modelos grátis) + fallback determinístico**: copy
  nunca trava sem credencial (cai no fallback) nem inventa fato; provider
  abstrato, troca de modelo é só variável de ambiente.
- **RLS no banco**: cada org só enxerga os próprios dados; o worker usa
  service_role, o frontend usa anon + RLS.
- **CTA sempre pelo redirect first-party** `/r/<id>`: clique medido e
  domínio controlado, nunca link de afiliado bruto na mensagem.
