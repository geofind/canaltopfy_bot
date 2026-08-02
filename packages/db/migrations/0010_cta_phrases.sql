-- ============================================================
-- Topfy Affiliate OS — migração 0010: gatilhos/CTAs cadastráveis
-- Frases de chamada para ação sorteadas pelo worker na hora da
-- publicação (ex.: "Aproveita essa antes que acabe" é PROIBIDO —
-- validação do worker filtra frases enganosas). RLS por org.
-- ============================================================

create table if not exists cta_phrases (
    id              uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    phrase          text not null,
    is_active       boolean not null default true,
    created_at      timestamptz not null default now()
);

alter table cta_phrases enable row level security;

create policy "cta_phrases_org" on cta_phrases
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());
