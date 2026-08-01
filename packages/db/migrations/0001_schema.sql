-- ============================================================
-- Topfy Affiliate OS — migração 0001: schema base
-- Estado máquina de campanha:
-- IMPORTED -> VALIDATING -> READY -> CONTENT_GENERATING
-- -> REVIEW_REQUIRED -> APPROVED -> SCHEDULED -> PUBLISHING
-- -> PUBLISHED -> MONITORING -> SCALE / REWORK / ARCHIVED / FAILED
-- ============================================================

-- uuid + soft delete
create extension if not exists "pgcrypto";

-- ------------------------------------------------------------
-- organizações (multiusuário: tudo pertence a uma org)
-- ------------------------------------------------------------
create table if not exists organizations (
    id           uuid primary key default gen_random_uuid(),
    name         text not null,
    slug         text unique not null,
    plan         text not null default 'free',
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create table if not exists profiles (
    id              uuid primary key references auth.users(id) on delete cascade,
    organization_id uuid not null references organizations(id) on delete cascade,
    full_name       text,
    role            text not null default 'owner'
        check (role in ('owner', 'editor', 'viewer')),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ------------------------------------------------------------
-- produtos / oportunidades
-- ------------------------------------------------------------
create table if not exists products (
    id                uuid primary key default gen_random_uuid(),
    organization_id   uuid not null references organizations(id) on delete cascade,
    status            text not null default 'IMPORTED'
        check (status in (
            'IMPORTED', 'VALIDATING', 'READY', 'REJECTED',
            'CONTENT_GENERATING', 'REVIEW_REQUIRED', 'APPROVED',
            'SCHEDULED', 'PUBLISHING', 'PUBLISHED', 'MONITORING',
            'SCALE', 'REWORK', 'ARCHIVED', 'FAILED'
        )),
    source_name       text not null,
    source_url        text not null,
    external_id       text,
    collected_at      timestamptz,
    method            text not null default 'MANUAL'
        check (method in ('API', 'SDK', 'MCP', 'CSV', 'MANUAL')),

    -- dados do produto
    title             text not null,
    description       text,
    image_url         text,
    original_price_brl numeric(12,2),
    discounted_price_brl numeric(12,2),
    currency          text not null default 'BRL',
    discount_pct      numeric(5,2),
    commission_pct    numeric(5,2),
    commission_brl    numeric(12,2),
    affiliate_link    text,
    affiliate_link_status text not null default 'UNKNOWN'
        check (affiliate_link_status in ('VERIFIED', 'UNKNOWN', 'NOT_AVAILABLE', 'NOT_SUPPORTED', 'FAILED')),
    seller            text,
    category          text,
    rating            numeric(3,2),
    sales_count       integer,
    reviews_count     integer,

    -- metadados de dado (princípio AGENTS.md)
    confidence        text not null default 'UNKNOWN'
        check (confidence in ('VERIFIED', 'UNKNOWN', 'NOT_AVAILABLE', 'NOT_SUPPORTED', 'STALE')),

    -- topfy score
    score             numeric(5,2),
    score_breakdown   jsonb not null default '{}'::jsonb,
    score_updated_at  timestamptz,

    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

-- ------------------------------------------------------------
-- campanhas (unidade de trabalho do funil)
-- ------------------------------------------------------------
create table if not exists campaigns (
    id              uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    product_id      uuid not null references products(id) on delete cascade,
    status          text not null default 'IMPORTED'
        check (status in (
            'IMPORTED', 'VALIDATING', 'READY', 'CONTENT_GENERATING',
            'REVIEW_REQUIRED', 'APPROVED', 'SCHEDULED', 'PUBLISHING',
            'PUBLISHED', 'MONITORING', 'SCALE', 'REWORK', 'ARCHIVED', 'FAILED'
        )),
    platform        text not null default 'telegram'
        check (platform in ('telegram', 'whatsapp', 'tiktok', 'instagram', 'youtube', 'amazon')),
    mode            text not null default 'simulated'
        check (mode in ('simulated', 'production')),
    title           text,
    slug            text unique,
    public_page     boolean not null default true,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ------------------------------------------------------------
-- conteúdos gerados (3 cópias por campanha)
-- ------------------------------------------------------------
create table if not exists contents (
    id              uuid primary key default gen_random_uuid(),
    campaign_id     uuid not null references campaigns(id) on delete cascade,
    version         integer not null default 1,
    status          text not null default 'DRAFT'
        check (status in ('DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED')),
    provider        text not null default 'fallback'
        check (provider in ('ollama', 'openai', 'anthropic', 'fallback', 'manual')),
    model           text,
    copy_text       text not null,
    hooks           jsonb not null default '[]'::jsonb,
    compliance      jsonb not null default '{}'::jsonb,
    reviewed_at     timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ------------------------------------------------------------
-- publicações (uma por canal/plataforma)
-- ------------------------------------------------------------
create table if not exists publications (
    id              uuid primary key default gen_random_uuid(),
    campaign_id     uuid not null references campaigns(id) on delete cascade,
    content_id      uuid references contents(id) on delete set null,
    channel         text not null check (channel in ('telegram', 'whatsapp', 'tiktok', 'instagram', 'youtube', 'amazon', 'web')),
    mode            text not null default 'simulated'
        check (mode in ('simulated', 'production')),
    status          text not null default 'SCHEDULED'
        check (status in ('SCHEDULED', 'PENDING_APPROVAL', 'PUBLISHING', 'PUBLISHED', 'FAILED', 'CANCELLED')),
    external_id     text,
    external_url    text,
    scheduled_at    timestamptz,
    published_at    timestamptz,
    approved_by     uuid references auth.users(id),
    approved_at     timestamptz,
    error           text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ------------------------------------------------------------
-- rastreamento first-party (/r/<id> -> redireciona ao link afiliado)
-- ------------------------------------------------------------
create table if not exists affiliate_clicks (
    id            bigint generated always as identity primary key,
    publication_id uuid references publications(id) on delete set null,
    campaign_id   uuid references campaigns(id) on delete set null,
    product_id    uuid references products(id) on delete set null,
    clicked_at    timestamptz not null default now(),
    referrer      text,
    user_agent    text,
    ip_hash       text,
    utm_source    text,
    utm_medium    text,
    utm_campaign  text,
    utm_content   text,
    utm_term      text,
    gclid         text,
    fbclid        text
);

create table if not exists conversions (
    id                    uuid primary key default gen_random_uuid(),
    campaign_id           uuid references campaigns(id) on delete set null,
    affiliate_click_id    bigint references affiliate_clicks(id) on delete set null,
    external_conversion_id text,
    amount_brl            numeric(12,2),
    commission_brl        numeric(12,2),
    currency              text not null default 'BRL',
    occurred_at           timestamptz not null default now(),
    status                text not null default 'VERIFIED'
        check (status in ('VERIFIED', 'UNKNOWN', 'NOT_AVAILABLE', 'NOT_SUPPORTED', 'PENDING')),
    source_name           text,
    collected_at          timestamptz,
    method                text not null default 'MANUAL'
        check (method in ('API', 'SDK', 'MCP', 'CSV', 'MANUAL'))
);

-- ------------------------------------------------------------
-- fila de trabalho (Postgres como fila no MVP, sem Redis)
-- ------------------------------------------------------------
create table if not exists jobs (
    id              bigint generated always as identity primary key,
    organization_id uuid references organizations(id) on delete cascade,
    type            text not null,
    payload         jsonb not null default '{}'::jsonb,
    status          text not null default 'pending'
        check (status in ('pending', 'running', 'done', 'failed', 'cancelled')),
    attempts        integer not null default 0,
    max_attempts    integer not null default 3,
    scheduled_for   timestamptz not null default now(),
    started_at      timestamptz,
    finished_at     timestamptz,
    error           text,
    created_at      timestamptz not null default now()
);

-- ------------------------------------------------------------
-- trilha de auditoria (toda automação é registrada)
-- ------------------------------------------------------------
create table if not exists audit_log (
    id              bigint generated always as identity primary key,
    organization_id uuid references organizations(id) on delete cascade,
    actor_type      text not null check (actor_type in ('user', 'worker', 'system')),
    actor_id        text,
    action          text not null,
    entity_type     text,
    entity_id       text,
    metadata        jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now()
);

create index if not exists idx_products_org_status      on products (organization_id, status);
create index if not exists idx_campaigns_org_status     on campaigns (organization_id, status);
create index if not exists idx_campaigns_product        on campaigns (product_id);
create index if not exists idx_contents_campaign        on contents (campaign_id);
create index if not exists idx_publications_campaign    on publications (campaign_id);
create index if not exists idx_clicks_publication       on affiliate_clicks (publication_id);
create index if not exists idx_clicks_campaign_created  on affiliate_clicks (campaign_id, clicked_at);
create index if not exists idx_jobs_status_scheduled    on jobs (status, scheduled_for);
create index if not exists idx_audit_org_created        on audit_log (organization_id, created_at desc);
