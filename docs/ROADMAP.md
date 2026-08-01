# Roadmap

## Fase 1 — MVP (em andamento)

- [x] Monorepo Next.js + worker Python + migrations
- [x] Schema PostgreSQL: products, campaigns, contents, publications,
      clicks, conversions, jobs, audit_log + RLS
- [x] Worker: conector AliExpress (API oficial), score, copy, Telegram,
      adapters simulados
- [x] Testes do worker (20 testes stdlib)
- [ ] Telas: dashboard, nova campanha (colar URL), aprovação de copy,
      publicações, cliques
- [ ] Vitrine pública `/c/<slug>` + redirect `/r/<id>`
- [ ] Card via Pictify
- [ ] Testes E2E
- [ ] Deploy: Vercel (web) + worker (VPS/RAILWAY)

## Fase 2 — Canais e conectores

- WhatsApp Business Cloud API (opt-in, templates, janela 24h)
- Amazon Creators API (após elegibilidade — 10 vendas qualificadas/30 dias)
- TikTok Content Posting API (após auditoria)
- Instagram Graph API (conta Business/Creator + App Review)
- YouTube Data API v3
- Importação manual Mercado Livre (automação proibida pela plataforma)

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
