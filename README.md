# Topfy Affiliate OS

Sistema operacional de afiliados internacionais: do produto à publicação, com
inteligência — um funil supervisionado de ponta a ponta.

```
oportunidade → validação → ficha do produto → landing + copy → sugestão de propaganda → acompanhamento automático → decisão
```

## Fase atual

**Fase 1 — MVP (fluxo vertical).** Colar URL de produto (AliExpress) →
extração via API oficial → link de afiliado verificado → Topfy Score →
3 cópias (OpenRouter + fallback) → card (next/og) → página pública →
publicação (Telegram real + WhatsApp assistido) → clique rastreado → analytics.

## Monorepo

```
apps/web     Next.js 16 + TypeScript + Tailwind + shadcn/ui (dashboard, vitrine, /r/<id>)
apps/worker  Python 3.11 — conectores, score, copy, fila, publicações
packages/db  Migrations PostgreSQL (Supabase)
docs         Decisões, arquitetura, roadmap, segurança
```

## Como rodar

### 1. Banco (Supabase cloud)

1. Crie um projeto em https://supabase.com (plano free).
2. Rode as migrations de `packages/db/migrations/` no SQL Editor, em ordem
   (`0001_schema.sql` até `0005_provider_openrouter.sql`) — ou o script
   consolidado `packages/db/reset-e-migrate.sql` de uma vez só.
3. Copie `.env.example` para `.env` e preencha `SUPABASE_URL`,
   `SUPABASE_ANON_KEY` e `SUPABASE_SERVICE_ROLE_KEY`.

### 2. Web

```bash
npm install
npm run build --workspace apps/web
npm run dev --workspace apps/web
```

### 3. Worker

```bash
cd apps/worker
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python -m main                # consome a fila de jobs
```

### 4. IA (opcional)

Crie uma key grátis em [openrouter.ai/keys](https://openrouter.ai/keys) e
preencha `OPENROUTER_API_KEY` no `.env` (confirme o slug de modelo grátis
vigente em `openrouter.ai/models` antes de trocar `OPENROUTER_MODEL`).

Sem `OPENROUTER_API_KEY`, o worker gera copy determinística (nunca inventa
fato) — nunca quebra por falta de credencial.

### 5. Testes E2E (Playwright)

Cobrem login/erro de credencial, guarda de rota autenticada, criação de
campanha (feliz e validação de URL), e as rotas públicas sem sessão
(`/c/<slug>`, `/og/card/<id>`, `/r/<id>`). Usam o Supabase configurado no
`.env` — o `global-setup` provisiona um usuário/organização de teste fixos
via Admin API (idempotente, não passa pelo formulário de signup).

```bash
cd apps/web
npm run dev            # em outro terminal — ou deixa o Playwright subir sozinho
npm run test:e2e
```

## Regras de segurança

- Nenhuma automação publica conteúdo, ativa anúncios ou aumenta orçamento
  sem aprovação humana explícita.
- Toda integração tem modo `simulated`; `production` exige credencial
  configurada e confirmação explícita.
- Nada é inventado: preço, comissão, desconto, tendência e rank só entram
  com fonte verificada (API oficial) ou marcação manual explícita.
- O banco é a fonte da verdade; toda automação gera `audit_log`.

## Documentação

| O quê | Arquivo |
| --- | --- |
| Arquitetura | `docs/ARCHITECTURE.md` |
| Roadmap | `docs/ROADMAP.md` |
| Banco de dados | `docs/DATABASE.md` |
| Segurança | `docs/SECURITY.md` |
| Integrações | `docs/API_INTEGRATIONS.md` |
| Deploy | `docs/DEPLOY.md` |
