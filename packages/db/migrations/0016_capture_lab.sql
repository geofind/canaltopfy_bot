-- Laboratório de Captura: configuração de descoberta editável pela tela
-- (categorias, palavras-chave por fonte, corte de score, bloqueio de
-- palavras), substituindo o que hoje só existe em variável de ambiente do
-- worker. RLS segue o mesmo padrão de 0011_queues.sql.

create table if not exists discovery_settings (
    organization_id uuid primary key references organizations(id) on delete cascade,
    min_score       numeric not null default 60,
    updated_at      timestamptz not null default now()
);

create table if not exists discovery_categories (
    id              uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    family_key      text not null,
    label           text not null,
    active          boolean not null default true,
    min_score       numeric,
    locked_until    timestamptz,
    locked_reason   text,
    created_at      timestamptz not null default now(),
    unique (organization_id, family_key)
);

create table if not exists discovery_keywords (
    id              uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    source_name     text not null
        check (source_name in ('aliexpress', 'shopee', 'mercadolivre')),
    term            text not null,
    active          boolean not null default true,
    created_at      timestamptz not null default now(),
    unique (organization_id, source_name, term)
);

create table if not exists discovery_blocklist (
    id              uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    term            text not null,
    is_permanent    boolean not null default true,
    expires_at      timestamptz,
    reason          text,
    created_at      timestamptz not null default now(),
    check (is_permanent or expires_at is not null)
);

alter table discovery_settings enable row level security;
alter table discovery_categories enable row level security;
alter table discovery_keywords enable row level security;
alter table discovery_blocklist enable row level security;

create policy "discovery_settings_org" on discovery_settings
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

create policy "discovery_categories_org" on discovery_categories
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

create policy "discovery_keywords_org" on discovery_keywords
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

create policy "discovery_blocklist_org" on discovery_blocklist
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());

-- Seed: uma linha por família já reconhecida em
-- apps/worker/offer_rules.py (CATEGORY_FAMILY_TERMS), pra toda
-- organização existente. Famílias nunca vistas continuam liberadas por
-- padrão (ausência na tabela nunca bloqueia) — isso só dá um ponto de
-- partida pra curadoria, não é uma lista fechada.
insert into discovery_categories (organization_id, family_key, label)
select o.id, v.family_key, v.label
from organizations o
cross join (values
    ('carregadores', 'Carregadores'),
    ('power-banks', 'Power banks'),
    ('celulares', 'Celulares'),
    ('monitores', 'Monitores'),
    ('notebooks', 'Notebooks'),
    ('tablets', 'Tablets'),
    ('fones', 'Fones de ouvido'),
    ('smartwatches', 'Smartwatches'),
    ('televisores', 'Televisores'),
    ('consoles', 'Consoles'),
    ('controles', 'Controles'),
    ('teclados', 'Teclados'),
    ('mouses', 'Mouses'),
    ('ssds', 'SSDs'),
    ('air-fryers', 'Air fryers'),
    ('aspiradores', 'Aspiradores')
) as v(family_key, label)
on conflict (organization_id, family_key) do nothing;
