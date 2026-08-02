# Topfy Affiliate OS — instruções de trabalho para Claude

## Projeto
Sistema de affiliate marketing: importa produtos (AliExpress, Mercado Livre),
gera conteúdo com IA (OpenRouter), publica ofertas em grupo/canal do Telegram
com link de afiliado rastreado. MVP funcional, em pt-BR.

## Stack e estrutura (monorepo)
- apps/web — Next.js 16.2.12 (Turbopack, src dir, Tailwind v4, shadcn).
  ATENÇÃO: versão nova do Next; leia node_modules/next/dist/docs/ antes de
  escrever código. proxy.ts (não middleware.ts), cacheComponents DESLIGADO
  (export const dynamic = "force-dynamic" continua válido).
- apps/worker — Python stdlib puro (sem deps instaláveis; não usar pip,
  requests, etc.). Fila no Postgres via Supabase, poll de 5s.
- packages/db/migrations — SQL (0001..0006), RLS por organização.
- docs/ — ROADMAP, DECISIONS, API_INTEGRATIONS.

## Estado (já feito, NÃO refazer)
- Importação AliExpress (site oficial: é proibido automatizar) e ML (manual:
  automação de importação é proibida pelo ML; OAuth com código de afiliado).
- OAuth Mercado Livre completo: migração 0006 (ml_credentials), rota
  /callback (valida state em cookie httpOnly, troca code→token), action
  connectMercadoLivre, páginas /integracoes, /sistema, dashboard.
- Publicação Telegram real: TELEGRAM_CHAT_ID=-1004362453366 (grupo "Canaltopfy -
  Tech promo", bot @canaltopfy_bot é admin), sendPhoto+HTML, cards next/og.
- Site de controle: /sistema (jobs, falhas, atividade do worker), /integracoes
  (ML conectar/desconectar, status Telegram), detalhe da campanha com
  cliques/conversões/comissão (últimos 20).
- Testes: worker 28/28 (py 3.14.6 e 3.11); E2E Playwright 9/9 (chromium).
- Build, lint e tsc limpos. Último commit: f38f44d1.

## Regras NÃO-NEGOCIÁVEIS
1. NUNCA commitar o .env (tem tokens reais: Supabase, Telegram, OpenRouter).
2. .env fica na raiz; worker lê com loader stdlib (sem dotenv).
3. Python 3.14.6 tem bug no re: literal+classe+classe não casa. Regex de ID
   ML precisa de alternância explícita: r"\bML(?:B|A|C|M|U|T|V|P|EC|CO)-?(\d{7,15})\b".
4. ML rejeita qualquer redirect_uri que contenha "localhost" (mesmo
   localhost.rip). ML_REDIRECT_URI=https://lvh.me:3000/callback (dev).
5. Telegram baixa imagens pelos servidores: para testar publicação use
   imagem de URL pública; localhost/lvh.me não funciona.
6. API pública do ML retorna 403 em /items e /sites/MLB/search (pendente de
   investigação: pode ser bloqueio de IP/datacenter). Não "consertar"
   inventando autenticação.
7. Endpoints do Next 16 mudam (redirect/rewrites → proxy, cache → cache
   components). Sempre confirmar no docs local antes de mexer.

## Próxima tarefa (única pendente): DEPLOY
1. Vercel para apps/web: vercel.json (framework nextjs, root apps/web), env
   vars (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY,
   ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI do domínio final,
   CANALTOPFY_PUBLIC_BASE_URL=https://<domínio>), checar se pode
   rodar `vercel` CLI (peça permissão antes).
2. Worker: Dockerfile (python:3.14-slim, stdlib only) + docs de execução
   (poll de jobs no Supabase).
3. Atualizar docs/ROADMAP.md (Fase 1 100%) e canetar o que mudar.

## Verificação
- Web: cd apps/web; npm run lint; npx tsc --noEmit; npm run build.
- E2E: npm run test:e2e (reusa dev server na 3000; requer SUPABASE_SERVICE_ROLE_KEY no .env).
- Worker: cd apps/worker; python -m unittest discover -s tests -v.

## Comunicação
Responder em pt-BR, explicar decisões, não commitar sem pedir.
