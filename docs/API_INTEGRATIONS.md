# Integrações (API)

Regra do spec: confirmar a API oficial ANTES de escrever integração; toda
integração tem modo simulado + produção; nada publica sem autorização.

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

## Importação manual (sem automação)

- **Mercado Livre**: automação de compra proibida pela plataforma — só
  importação manual de URL/dados.
- **Shopee**: sem API pública de afiliados para o caso — manual.

## Adiado

- GA4 (Measurement Protocol/`gtag`) — Fase 4
- Google Ads API (campanhas rascunho; aprovação humana) — Fase 4
- Meta Marketing API — somente conta autorizada; sem automação financeira

## Card de produto (imagem para as publicações)

- **Pictify** — free tier 50 imagens/mês; plano US$15/mês quando crescer
- Rejeitados: Bannerbear (US$49+/mês), Placid (marca d'água), Cloudinary
  (US$89+/mês); alternativa futura grátis: `@vercel/og`
