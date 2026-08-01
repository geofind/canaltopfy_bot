# Banco de dados

PostgreSQL no Supabase (cloud). Migrations em `packages/db/migrations/`
(rodar em ordem no SQL Editor). RLS habilitado em todas as tabelas.

## Tabelas

| Tabela | Papel | Estados |
| --- | --- | --- |
| `organizations` | multiusuário | plan: free/pago |
| `profiles` | vínculo auth.users → org | role: owner/editor/viewer |
| `products` | ficha do produto/oportunidade | IMPORTED, VALIDATING, READY, REJECTED, FAILED, ... |
| `campaigns` | unidade de trabalho do funil | mesma máquina do produto + plataforma |
| `contents` | cópias geradas (3 por campanha) | DRAFT, PENDING_REVIEW, APPROVED, REJECTED, PUBLISHED |
| `publications` | publicação por canal | SCHEDULED, PENDING_APPROVAL, PUBLISHING, PUBLISHED, FAILED, CANCELLED |
| `affiliate_clicks` | cliques first-party (`/r/<id>`) | append-only |
| `conversions` | conversões/comissões importadas | VERIFIED, UNKNOWN, NOT_AVAILABLE, NOT_SUPPORTED, PENDING |
| `jobs` | fila de trabalho (Postgres, sem Redis) | pending, running, done, failed, cancelled |
| `audit_log` | trilha de auditoria de toda automação | append-only |

## Máquina de estados da campanha

```
IMPORTED -> VALIDATING -> READY -> CONTENT_GENERATING
-> REVIEW_REQUIRED -> APPROVED -> SCHEDULED -> PUBLISHING
-> PUBLISHED -> MONITORING -> SCALE / REWORK / ARCHIVED / FAILED
```

## Princípio de dados (todo dado externo)

`source_name`, `source_url`, `collected_at`, `method`
(`API`/`SDK`/`MCP`/`CSV`/`MANUAL`), `confidence` (`VERIFIED`/`UNKNOWN`/
`NOT_AVAILABLE`/`NOT_SUPPORTED`), `external_id` quando existir.
Nunca inventar comissão, cookie, CPC, conversão, receita, tendência,
ranking ou regra de tráfego.

## Topfy Score

Decomposto e explicável (`score_breakdown` jsonb), pesos somando 100:

| Dimensão | Peso |
| --- | --- |
| desconto real | 20 |
| vendas | 15 |
| avaliação | 15 |
| comissão | 15 |
| tendência | 10 |
| apelo visual | 10 |
| concorrência | 10 |
| confiabilidade | 5 |

Bloqueios (impedem aprovação, não só reduzem score): link de afiliado não
`VERIFIED`; produto sem preço confirmado.

## Chaves de rastreamento

Preservar `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`,
`utm_term`, `gclid`, `fbclid`, `affiliate_click_id`, `external_conversion_id`,
moeda e taxa de câmbio usada.
