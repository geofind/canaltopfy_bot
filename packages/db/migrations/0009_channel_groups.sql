-- ============================================================
-- Topfy Affiliate OS — migração 0009: grupos de canais
-- Múltiplos destinos de publicação (Telegram) por organização:
-- um grupo/canal cadastrado uma vez, reutilizável em filas,
-- agendamentos e no disparo manual. RLS por org.
-- ============================================================

create table if not exists channel_groups (
    id                  uuid primary key default gen_random_uuid(),
    organization_id     uuid not null references organizations(id) on delete cascade,
    name                text not null,
    telegram_chat_id    text not null,
    telegram_chat_title text,
    is_active           boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (organization_id, telegram_chat_id)
);

alter table channel_groups enable row level security;

create policy "channel_groups_org" on channel_groups
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());
