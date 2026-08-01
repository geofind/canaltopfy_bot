# Segurança

## Credenciais

- `.env` jamais commitado; segredos só no ambiente (worker) e variáveis do
  provedor (web). Template em `.env.example` sem valores reais.
- Frontend usa `SUPABASE_ANON_KEY` + RLS; **service_role key só no worker**.
- Token do Telegram e app secret da AliExpress nunca aparecem em log,
  mensagem de erro ou métrica.
- Nenhuma credencial embutida em teste (testes limpam o ambiente).

## Acesso a dados

- RLS habilitado em todas as tabelas (`packages/db/migrations/0002_rls.sql`);
  usuário autenticado só vê dados da própria organização.
- `audit_log` append-only registra toda ação de worker (actor_type=worker)
  e toda aprovação humana (actor_type=user).
- Clicks armazenam `ip_hash`, nunca IP bruto.

## Publicação (regra do produto)

- Nada publica sem aprovação humana explícita (campanha APPROVED + conteúdo
  APPROVED + publicação criada com status explícito).
- Toda integração começa em modo `simulated`; `TOPFY_PRODUCTION=1` é
  exigido explicitamente para qualquer chamada real — e mesmo assim o
  adapter valida a credencial antes.
- Deduplicação: nunca publica a mesma campanha no mesmo canal duas vezes.

## Conteúdo

- Toda copy (IA ou manual) passa por `validar_copy`: disclaimer obrigatório,
  frases enganosas proibidas (últimas unidades, garantido, sem risco,
  melhor preço da internet, oferta imperdível por tempo limitado...).
- Copy nunca cita preço/desconto/avaliação que não existe na ficha
  (dado real da fonte ou "a confirmar").

## Limites e abuso

- O worker dá retry com backoff (FloodWait do Telegram, 429) — nunca burla
  rate limit; CAPTCHA/login nunca são contornados.
- Nenhum scraper anti-bot; dados públicos só via API autorizada ou
  importação manual.
