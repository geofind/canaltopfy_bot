# Integrações (API)

Regra do spec: confirmar a API oficial ANTES de escrever integração; toda
integração tem modo simulado + produção; nada publica sem autorização.

## Mercado Livre — descoberta oficial supervisionada

- `/trends/MLB` fornece termos em alta; o worker limita a quantidade e
  atualiza essa fonte no maximo a cada 6 horas.
- `/highlights/MLB/category/{CATEGORY_ID}` fornece os mais vendidos de uma
  categoria-folha; o worker resolve somente entradas `ITEM` e `PRODUCT` por
  endpoints oficiais e ignora `USER_PRODUCT` quando nao ha oferta publica
  verificavel.
- `/products/search` + `/products/{PRODUCT_ID}/items` localizam ofertas de
  catalogo quando `/sites/MLB/search` responde 403.
- `/sites/MLB/domain_discovery/search` restringe a busca ao dominio previsto
  e evita homonimos, como um livro com "smartphone" no titulo.
- `/items/{ITEM_ID}/sale_price?context=channel_marketplace` confirma o preco
  vigente e o preco regular antes de calcular o desconto.
- Limites por ciclo, deduplicacao por `external_id` e fallbacks de rede evitam
  rajadas, duplicatas e descontos inventados. Nenhuma dessas etapas gera ou
  valida comissao; o `meli.la` continua vindo do Link Builder oficial.

## VALIDADO AO VIVO (Fase 1)

### AliExpress Affiliate API — REAL

- Endpoint: `https://api-sg.aliexpress.com/sync` (POST form-urlencoded)
- Métodos usados: `aliexpress.affiliate.productdetail.get`,
  `aliexpress.affiliate.product.query`, `aliexpress.affiliate.link.generate`
- Autenticação: app_key + app_secret (HMAC-SHA256 sobre parâmetros em ordem
  alfabética, `sign_method=sha256`), `tracking_id` para vincular comissões
- Validação no lab (app 541338): resp_code 200 nos três métodos;
  `hotproduct.query` → `InsufficientPermission` (não usar)
- `generate_affiliate_link` marca `VERIFIED` **só** com resp_code 200 +
  `promotion_link` real — não prova clique/conversão
- Modo manual sem credencial: extrai só o ID da URL, campos `UNKNOWN`

### Telegram Bot API — REAL

- `https://api.telegram.org/bot<token>/<metodo>` (JSON POST)
- Usados: `getMe`, `sendMessage`, `sendPhoto` (HTML parse mode)
- Robustez: retry com `retry_after` em FloodWait/429; token nunca em erro
- CTA usa redirect first-party `/r/<id>` (domínio via
  `CANALTOPFY_PUBLIC_BASE_URL`)

## SIMULADO (mock até credencial/elegibilidade)

### Amazon Creators API — mock

PA-API descontinuada em 15/05/2026. Creators API usa OAuth2 e exige
elegibilidade: **10 vendas qualificadas nos últimos 30 dias**. Até lá,
`verification_status=NOT_AVAILABLE` e link manual do portal.

### WhatsApp Business Platform Cloud API — Fase 2

Regras: opt-in do usuário, templates aprovados, janela de 24h para
respostas livres. **On-Premise API descontinuada em out/2025** — não usar.
MVP usa link assistido `wa.me` (envio manual pelo dono do negócio).

### TikTok Content Posting API — Fase 2

`POST /v2/post/publish/creator_info/init` + `post/publish/creator_info/upload`
(precisa auditoria da plataforma para Direct Post). Sem auditoria: usar
"Upload to Inbox"/rascunho. Mock até lá.

### Instagram Graph API Content Publishing — Fase 2

Exige conta Business/Creator + App Review da Meta
(`/me/media_publish` + container). Mock até App Review.

### YouTube Data API v3 — Fase 2

`youtube.activities.insert` (requer OAuth + escopo). Mock até lá.

### Mercado Livre — importação manual (API pública de dados)

- Leitura de anúncio: `GET https://api.mercadolibre.com/items/{id}` — API
  **oficial e pública** (sem autenticação); id no formato `MLB<digits>`
  (extraído da URL `produto.mercadolivre.com.br/MLB-<digits>-...`).
  Campos: título, permalink, thumbnail/pictures, price, original_price,
  sold_quantity, seller, category_id. Nome de categoria via
  `GET /categories/{id}` (path_from_root); vendedor via `GET /users/{id}`
  quando necessário.
- Método `API` + `source_confidence=VERIFIED` (dados vêm da API oficial).
  Moeda: a API pública não converte — anúncios fora do Brasil ficam com
  aviso e preço local.
- **Link de afiliado**: o programa "Mercado Livre Afiliados" não tem API
  pública de geração — o usuário cola o link do painel oficial;
  `verification_status` fica `UNKNOWN` até confirmação manual (nunca
  `VERIFIED` sem evidência).
- OAuth2 (seção acima) é só para dados da conta do usuário.

## Importação manual (sem automação)

- **Mercado Livre**: automação de compra proibida pela plataforma — só
  importação manual de URL/dados (dados lidos da API pública oficial,
  link de afiliado colado do painel). OAuth2 do app (web) para obter o token
  da conta do usuário:

  - Autorização: `https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=<ML_CLIENT_ID>&redirect_uri=<ML_REDIRECT_URI>&state=<uuid>`
    (state random em cookie httpOnly de 10min, validado no callback — CSRF)
  - Callback: `/callback` no web troca o code por token em
    `POST https://api.mercadolibre.com/oauth/token`
    (`grant_type=authorization_code`, form-urlencoded) e guarda em
    `ml_credentials` (uma linha por organização, RLS por org).
  - `ML_REDIRECT_URI` deve ser exatamente a URL cadastrada no app em
    developers.mercadolivre.com.br — em produção, HTTPS obrigatório. O ML
    **rejeita qualquer endereço que contenha "localhost"**, mesmo com TLD
    válido (testado: `https://localhost.rip:3000/callback` falhou). No dev
    local usar domínio de loopback sem essa palavra — `https://lvh.me:3000/callback`
    passou na validação (resolve para 127.0.0.1) — ou URL do Vercel; o app
    aceita vários URIs.
  - `refresh_token` guardado para renovação futura
    (`grant_type=refresh_token`).
- **Shopee**: sem API pública de afiliados para o caso — manual.

## Adiado

- GA4 (Measurement Protocol/`gtag`) — Fase 4
- Google Ads API (campanhas rascunho; aprovação humana) — Fase 4
- Meta Marketing API — somente conta autorizada; sem automação financeira

## Card de produto (imagem para as publicações)

- **`next/og` (`ImageResponse`)** — embutido no Next.js desde a v14 (usa
  `@vercel/og`/Satori/Resvg por baixo), MIT, custo zero, sem conta/credencial
  externa, roda como rota própria em `apps/web`. Confirmado ainda a opção
  atual contra a documentação oficial do Next.js (`nextjs.org/docs`).
  Limitações: só subconjunto flexbox de CSS, bundle máx. 500KB, fontes
  ttf/otf/woff.
- Rejeitados: **Pictify** (free tier só 50 imagens/mês, depois US$15/mês —
  correção registrada aqui: era a escolha original, substituída por
  priorizar built-in/open source sobre serviço pago de terceiro, regra do
  projeto), Bannerbear (US$49+/mês), Placid (marca d'água no free tier),
  Cloudinary (US$89+/mês).
