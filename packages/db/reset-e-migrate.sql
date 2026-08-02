-- ============================================================
-- Topfy Affiliate OS — RESET + migrations (colar no SQL Editor)
-- ATENÇÃO: apaga TODAS as tabelas/funções do schema public deste
-- projeto. Usado apenas porque o projeto tinha schema de outro app.
-- ============================================================

-- 1) Remove tudo do schema public (tabelas, views, funções, policies)
--    Funções de extensão (ex.: unaccent, pg_trgm de um projeto anterior)
--    são ignoradas via pg_depend (deptype='e'); as demais são dropadas
--    por oid::regprocedure (assinatura completa) para não falhar em
--    função sobrecarregada (ex.: unaccent(text) vs unaccent(regdictionary,
--    text)) — nome sozinho é ambíguo nesse caso. `when others` no loop
--    garante que uma função problemática isolada não aborta o reset
--    inteiro (fica só um `notice` no log).
do $$
declare
    r record;
begin
    for r in select tablename
             from pg_tables
             where schemaname = 'public'
    loop
        execute format('drop table if exists public.%I cascade', r.tablename);
    end loop;
    for r in select p.oid::regprocedure as sig
             from pg_proc p
             join pg_namespace n on n.oid = p.pronamespace
             where n.nspname = 'public'
               and not exists (
                   select 1 from pg_depend d
                   where d.objid = p.oid and d.deptype = 'e'
               )
    loop
        begin
            execute format('drop function if exists %s cascade', r.sig);
        exception when others then
            raise notice 'pulei função % (provável dependência de extensão): %', r.sig, sqlerrm;
        end;
    end loop;
end $$;

-- ============================================================
-- 0001 — schema base
-- ============================================================
create extension if not exists "pgcrypto";

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

    confidence        text not null default 'UNKNOWN'
        check (confidence in ('VERIFIED', 'UNKNOWN', 'NOT_AVAILABLE', 'NOT_SUPPORTED', 'STALE')),

    score             numeric(5,2),
    score_breakdown   jsonb not null default '{}'::jsonb,
    score_updated_at  timestamptz,

    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

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
    channel_config  jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create table if not exists contents (
    id              uuid primary key default gen_random_uuid(),
    campaign_id     uuid not null references campaigns(id) on delete cascade,
    version         integer not null default 1,
    status          text not null default 'DRAFT'
        check (status in ('DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED')),
    provider        text not null default 'fallback'
        check (provider in ('openrouter', 'openai', 'anthropic', 'fallback', 'manual')),
    model           text,
    copy_text       text not null,
    hooks           jsonb not null default '[]'::jsonb,
    compliance      jsonb not null default '{}'::jsonb,
    reviewed_at     timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

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
create index if not exists idx_contents_campaign_status on contents (campaign_id, status);
create index if not exists idx_publications_channel     on publications (channel);

-- ============================================================
-- 0002 — RLS
-- ============================================================
alter table organizations       enable row level security;
alter table profiles            enable row level security;
alter table products            enable row level security;
alter table campaigns           enable row level security;
alter table contents            enable row level security;
alter table publications        enable row level security;
alter table affiliate_clicks    enable row level security;
alter table conversions         enable row level security;
alter table jobs                enable row level security;
alter table audit_log           enable row level security;

create or replace function public.current_org_id()
returns uuid
language sql stable security definer
set search_path = public
as $$
    select organization_id from profiles where id = auth.uid()
$$;

create or replace function public.is_owner()
returns boolean
language sql stable security definer
set search_path = public
as $$
    select coalesce(
        (select role = 'owner' from profiles where id = auth.uid()),
        false
    )
$$;

create policy "orgs_select_member" on organizations
    for select using (id = public.current_org_id());
create policy "orgs_insert_auth" on organizations
    for insert with check (auth.uid() is not null);
create policy "orgs_update_owner" on organizations
    for update using (public.is_owner());

create policy "profiles_select_self" on profiles
    for select using (id = auth.uid() or organization_id = public.current_org_id());
create policy "profiles_insert_self" on profiles
    for insert with check (id = auth.uid());
create policy "profiles_update_self" on profiles
    for update using (id = auth.uid() or public.is_owner());

create policy "products_org" on products
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

create policy "campaigns_org" on campaigns
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

create policy "contents_via_campaign" on contents
    for all using (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ))
    with check (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ));

create policy "publications_via_campaign" on publications
    for all using (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ))
    with check (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ));

create policy "clicks_read_org" on affiliate_clicks
    for select using (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ));

create policy "clicks_insert_anon" on affiliate_clicks
    for insert with check (true);

create policy "conversions_read_org" on conversions
    for select using (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ));

create policy "jobs_read_org" on jobs
    for select using (organization_id = public.current_org_id());
create policy "jobs_insert_org" on jobs
    for insert with check (organization_id = public.current_org_id());

create policy "audit_read_org" on audit_log
    for select using (organization_id = public.current_org_id());
create policy "audit_insert_org" on audit_log
    for insert with check (organization_id = public.current_org_id());

-- ============================================================
-- 0003 — suporte às actions da web
-- ============================================================
alter table campaigns
    add column if not exists channel_config jsonb not null default '{}'::jsonb;

create index if not exists idx_contents_campaign_status
    on contents (campaign_id, status);
create index if not exists idx_publications_channel
    on publications (channel);

-- ============================================================
-- 0004 — leitura pública da vitrine (anon: vitrine/redirect/card)
-- ============================================================
create policy "campaigns_public_read" on campaigns
    for select using (public_page = true);

create policy "products_public_read" on products
    for select using (exists (
        select 1 from campaigns c
        where c.product_id = products.id
          and c.public_page = true
    ));

create policy "contents_public_read" on contents
    for select using (
        status = 'APPROVED'
        and exists (
            select 1 from campaigns c
            where c.id = contents.campaign_id
              and c.public_page = true
        )
    );

create policy "publications_public_read" on publications
    for select using (
        status = 'PUBLISHED'
        and exists (
            select 1 from campaigns c
            where c.id = publications.campaign_id
              and c.public_page = true
        )
    );
