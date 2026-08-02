-- ============================================================
-- Topfy Affiliate OS — migração 0011: filas de publicação
-- Filas com janela diária e intervalo mínimo entre envios; itens
-- da fila apontam para campanha+cópia e são despachados pelo
-- worker para todos os grupos vinculados. Inclui também:
--  - publications.chat_id (dedup por canal/grupo, não só canal)
--  - products.card_config (card do Telegram customizável: cor/borda)
-- RLS por org nas três tabelas novas.
-- ============================================================

create table if not exists queues (
    id               uuid primary key default gen_random_uuid(),
    organization_id  uuid not null references organizations(id) on delete cascade,
    name             text not null,
    is_active        boolean not null default true,
    interval_minutes integer not null default 5
        check (interval_minutes between 1 and 240),
    window_start     time,
    window_end       time,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create table if not exists queue_groups (
    queue_id uuid not null references queues(id) on delete cascade,
    group_id uuid not null references channel_groups(id) on delete cascade,
    primary key (queue_id, group_id)
);

create table if not exists queue_items (
    id              uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    queue_id        uuid not null references queues(id) on delete cascade,
    campaign_id     uuid not null references campaigns(id) on delete cascade,
    content_id      uuid references contents(id) on delete set null,
    status          text not null default 'PENDING'
        check (status in ('PENDING', 'DISPATCHED', 'DONE', 'CANCELLED')),
    attempts        integer not null default 0,
    error           text,
    scheduled_at    timestamptz not null default now(),
    dispatched_at   timestamptz,
    published_at    timestamptz,
    created_at      timestamptz not null default now()
);

alter table publications add column if not exists chat_id text;

alter table products add column if not exists card_config jsonb not null default '{}'::jsonb;

alter table queues enable row level security;
alter table queue_groups enable row level security;
alter table queue_items enable row level security;

create policy "queues_org" on queues
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

create policy "queue_groups_org" on queue_groups
    for all using (
        queue_id in (select id from queues where organization_id = public.current_org_id())
    )
    with check (
        queue_id in (select id from queues where organization_id = public.current_org_id())
        and group_id in (
            select id from channel_groups where organization_id = public.current_org_id()
        )
    );

create policy "queue_items_org" on queue_items
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

create index if not exists idx_queue_items_status_scheduled
    on queue_items (status, scheduled_at);
create index if not exists idx_publications_chat
    on publications (chat_id);
