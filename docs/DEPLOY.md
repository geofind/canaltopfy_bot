# Deploy

## Web (apps/web) — Vercel

Na raiz do repo existe `vercel.json` apontando o framework `nextjs` com
`root: apps/web`. O monorepo usa npm workspaces, então o install padrão da
Vercel resolve as deps de apps/web normalmente.

### Passo a passo

1. Subir o repo para o GitHub e importar na Vercel (ou `npx vercel` na raiz,
   CLI da Vercel suporta o `vercel.json`).
2. Definir as env vars do projeto na Vercel (Settings → Environment Variables):

   | Var                          | Valor                                                        |
   | ---------------------------- | ------------------------------------------------------------ |
   | `NEXT_PUBLIC_SUPABASE_URL`   | URL do projeto Supabase (mesma do `.env` local)              |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key pública (mesma do `.env` local)                  |
   | `ML_CLIENT_ID`               | Client ID do app Mercado Livre                               |
   | `ML_CLIENT_SECRET`           | Client Secret do app Mercado Livre                           |
   | `ML_REDIRECT_URI`            | `https://<domínio>/callback` (sem "localhost")               |
   | `CANALTOPFY_PUBLIC_BASE_URL` | `https://<domínio>` (raiz, sem `/callback` — usado nos links `/r/<id>` e no card og) |

3. Cadastrar `https://<domínio>/callback` em
   [mercadolivre.com.br/developers](https://mercadolivre.com.br/developers)
   → app → Redirection URI. O ML rejeita URIs com "localhost".
4. Implantar. O proxy (`apps/web/src/proxy.ts`) protege as rotas autenticadas
   (`/campanhas`, `/sistema`, `/integracoes`, `/callback`) e mantém públicas
   `/login`, `/c/*`, `/r/*` e `/og/*`.

### Testar no domínio final
- O card do Telegram (`/og/card/<id>`) e os links de afiliado (`/r/<id>`)
  dependem de `CANALTOPFY_PUBLIC_BASE_URL` apontando para o domínio público —
  localhost/lvh.me não funciona porque o Telegram baixa as imagens pelos
  servidores dele.
- A suíte E2E (`apps/web/e2e/`) roda contra qualquer domínio já implantado:
  `E2E_BASE_URL=https://<domínio> npm run test:e2e` (sem essa env var, sobe
  um dev server local como sempre). Cobre login, guarda de rota, criação de
  campanha (AliExpress/ML) e as rotas públicas — não cobre OAuth do ML nem
  publicação real no Telegram, que exigem consentimento humano no navegador.

## Worker (apps/worker) — contêiner

Imagem Python 3.14-slim, stdlib + `supabase` (única dep runtime, para a fila
via PostgREST). Nenhum segredo vai na imagem: env vars vêm do runtime.

### Build e execução

```bash
# do diretório do repo
docker build -t topfy-worker apps/worker

# rodar com as variáveis do .env (ou do seu provedor)
docker run --rm --env-file .env topfy-worker
```

O worker entra em loop: a cada 5s busca o próximo job pendente no Supabase
(`db.get_next_job`), processa (`product.import` e `publication.telegram`) e
marca `done`/`failed` com o erro em `jobs.error`. Os eventos vão para
`audit_log` e aparecem em `/sistema` no site.

### Env vars usadas pelo worker

| Var                  | Uso                                             |
| -------------------- | ----------------------------------------------- |
| `SUPABASE_URL`       | URL do projeto (mesma do web)                   |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role (worker opera fora do RLS)   |
| `ALIEXPRESS_APP_KEY` / `ALIEXPRESS_APP_SECRET` | API oficial AliExpress |
| `OPENROUTER_API_KEY` | Geração de copy via IA                          |
| `TELEGRAM_BOT_TOKEN` | Publicação no grupo/canal                       |
| `TELEGRAM_CHAT_ID`   | Chat padrão das publicações (ex.: `-1004362453366`) |
| `CANALTOPFY_PUBLIC_BASE_URL` | Base dos links de afiliado no post       |

### Provedores sugeridos
- Railway: `npx @railway/cli up` com `Dockerfile` no `apps/worker` (ou
  serviço apontando a pasta); definir as env vars acima.
- VPS: `docker run --env-file .env topfy-worker` em qualquer máquina com
  Docker; supervisionar com `docker restart unless-stopped` ou systemd.
- Fly.io: `fly launch` apontando para `apps/worker` com `build.dockerfile`.

O worker não expõe porta HTTP — ele é um consumidor de fila. Rode **uma
réplica**: o `get_next_job` (apps/worker/db.py) faz select→marca running
sem lock atômico, então duas réplicas podem disputar o mesmo job. Se no
futuro precisar escalar, troque por `select ... for update skip locked`.

## Checklist pós-deploy (web + worker)

Fazer nesta ordem, logo após o primeiro deploy:

1. **Login** — `/login` entra com a conta existente; rotas autenticadas
   (`/campanhas`, `/sistema`, `/integracoes`) redirecionam para `/login`
   sem sessão.
2. **Campanha AliExpress** — em `/campanhas/nova`, colar URL de produto.
   Com o worker rodando, o status passa IMPORTED → READY →
   CONTENT_GENERATING → REVIEW_REQUIRED (confira em `/sistema` os jobs).
3. **Campanha Mercado Livre** — mesma coisa com URL
   `produto.mercadolivre.com.br/MLB-...`; o conector usa a API pública
   (sem token). Se a API pública continuar dando 403 de produção,
   investigar antes de confiar no modo API (ver docs/API_INTEGRATIONS.md).
4. **Rastreamento** — abrir o detalhe da campanha: seção "Rastreamento"
   mostra cliques/conversões (pode estar zerada no início, é normal).
5. **ML OAuth** — em `/integracoes`, Conectar → autorizar no ML → voltar
   ao `/callback` → badge "Conectado" (e token com data de expiração).
6. **Telegram** — em `/integracoes`, conferir `@canaltopfy_bot` e o
   chat id; agendar/liberar publicação e conferir a mensagem no grupo:
   foto + texto + link de afiliado. O card do link (`/og/card/<id>`) só
   renderiza em URL pública (o Telegram baixa a imagem pelos servidores
   dele — localhost/lvh.me não funcionam).
7. **Links públicos** — `/c/<slug>` (vitrine), `/r/<id>` (redirect) e
   `/og/card/<id>` acessíveis sem sessão; `/r/<id>` inexistente manda
   para `/`.
8. **Worker de pé** — `docker ps` mostrando o contêiner; em `/sistema`,
   "Atividade do worker" atualizando conforme jobs são processados.
