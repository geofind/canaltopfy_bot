-- ============================================================
-- Topfy Affiliate OS — migração 0006: credenciais Mercado Livre
-- OAuth do app (importação manual; automação proibida pela
-- plataforma). Uma linha por organização: o access token trocado
-- no /callback. RLS por org, igual às demais tabelas.
-- ============================================================

create table if not exists ml_credentials (
    organization_id uuid primary key references organizations(id) on delete cascade,
    user_id         uuid references auth.users(id) on delete set null,
    access_token    text not null,
    refresh_token   text not null,
    expires_at      timestamptz,
    scope           text,
    ml_user_id      text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

alter table ml_credentials enable row level security;

create policy "ml_credentials_org" on ml_credentials
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());
