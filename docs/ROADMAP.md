# Roadmap

## Fase 1 — MVP (concluída)

- [x] Monorepo Next.js + worker Python + migrations
- [x] Schema PostgreSQL: products, campaigns, contents, publications,
      clicks, conversions, jobs, audit_log + RLS
- [x] Worker: conector AliExpress (API oficial), score, copy, Telegram,
      adapters simulados
- [x] Testes do worker (28 testes stdlib)
- [x] Telas: dashboard, nova campanha (colar URL), aprovação de copy,
      publicações, cliques
- [x] Vitrine pública `/c/<slug>` + redirect `/r/<id>`
- [x] Card via `next/og` (`/og/card/<id>`, RLS anon para vitrine)
- [x] Testes E2E (Playwright: auth, nova campanha, vitrine/card/redirect
      públicos — `apps/web/e2e/`)
- [x] Importação Mercado Livre (OAuth + conector API pública)
- [x] Publicação Telegram real no grupo padrão (`TELEGRAM_CHAT_ID`)
- [x] Site de controle: `/sistema` (jobs/falhas/atividade do worker),
      `/integracoes` (ML, Telegram), rastreamento por campanha
- [x] Deploy: artefatos prontos — `vercel.json`, Dockerfile do worker
      (`apps/worker/Dockerfile`) e `docs/DEPLOY.md` (executar passo a passo
      no Vercel/Railway/VPS)

## Fase 2 — Canais e conectores

- WhatsApp Business Cloud API (opt-in, templates, janela 24h)
- Amazon Creators API (após elegibilidade — 10 vendas qualificadas/30 dias)
- TikTok Content Posting API (após auditoria)
- Instagram Graph API (conta Business/Creator + App Review)
- YouTube Data API v3

## Fase 3 — Automações supervisionadas

- Agendamento de publicações (jobs recorrentes)
- Monitoramento de cliques e conversões (importação de comissões)
- Re-commerce: reusar produtos PUBLICADO/SCALE em novos canais

## Fase 4 — Tráfego pago

- GA4 (eventos first-party: landing_view, cta_click, affiliate_click,
  conversion_imported)
- Google Ads (campanhas como rascunho; aprovação humana obrigatória)

## Fase 5 — Negócio

- Planos e cobrança (Mercado Pago/Stripe)
- Multi-usuário por organização
- SaaS após validação comercial
