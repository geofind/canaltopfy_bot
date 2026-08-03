-- ============================================================
-- Topfy Affiliate OS — migração 0012: cupons cadastráveis
-- Cupom nunca é inventado pela copy — só aparece no post se estiver
-- cadastrado aqui pelo usuário (cupons de loja/site-wide, ex.:
-- "OFERTAMELI15"). source_name nulo = vale para qualquer loja.
-- ============================================================

create table if not exists coupon_codes (
    id              uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    source_name     text,
    code            text not null,
    label           text,
    is_active       boolean not null default true,
    created_at      timestamptz not null default now()
);

alter table coupon_codes enable row level security;

create policy "coupon_codes_org" on coupon_codes
    for all using (organization_id = public.current_org_id())
    with check (organization_id = public.current_org_id());
