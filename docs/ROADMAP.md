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

### Vitrine autoral CanalTopfy — referência Amazon Creators

- [x] Estudar a orientação oficial sobre descoberta de ofertas, criação de
      links com ID de Associado e páginas de Mais Vendidos da Amazon Brasil
- [x] Transformar `/ofertas` na página principal de curadoria do CanalTopfy,
      usando logo, paleta e dados reais já disponíveis no Affiliate OS
- [x] Organizar produtos publicados por categoria, destacar a entrada mais
      recente e manter avisos claros sobre afiliados, preço e disponibilidade
- [x] Documentar o roteiro de revisão da página para uso com Claude no Chrome
- [ ] Cadastrar categorias consistentes nos produtos publicados para evitar o
      agrupamento genérico “Achadinhos”
- [ ] Criar IDs de rastreamento Amazon distintos por canal/campanha e importar
      os resultados do relatório oficial sem tratar o parâmetro do link como
      prova de comissão
- [ ] Após elegibilidade, avaliar a Creators API para atualização autorizada de
      catálogo; até lá, manter a entrada Amazon manual e supervisionada

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
