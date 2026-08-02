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
