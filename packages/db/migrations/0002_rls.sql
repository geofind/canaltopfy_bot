-- ============================================================
-- Topfy Affiliate OS — migração 0002: Row Level Security
-- Todo acesso é mediado pela organização do usuário autenticado.
-- ============================================================

-- habilita RLS em todas as tabelas
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

-- helper: org do usuário logado
create or replace function public.current_org_id()
returns uuid
language sql stable security definer
set search_path = public
as $$
    select organization_id from profiles where id = auth.uid()
$$;

-- helper: usuário é owner da org
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

-- ------------------------------------------------------------
-- organizations: dono lê/edita; demais membros leem
-- ------------------------------------------------------------
create policy "orgs_select_member" on organizations
    for select using (id = public.current_org_id());
create policy "orgs_update_owner" on organizations
    for update using (public.is_owner());

-- ------------------------------------------------------------
-- profiles: usuário gerencia o próprio perfil; owner vê a org
-- ------------------------------------------------------------
create policy "profiles_select_self" on profiles
    for select using (id = auth.uid() or organization_id = public.current_org_id());
create policy "profiles_insert_self" on profiles
    for insert with check (id = auth.uid());
create policy "profiles_update_self" on profiles
    for update using (id = auth.uid() or public.is_owner());

-- ------------------------------------------------------------
-- produtos/campanhas/conteúdos/publicações: por org
-- ------------------------------------------------------------
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

-- ------------------------------------------------------------
-- clicks/conversions: somente escrita via service role (worker);
-- leitura para membros da org da campanha
-- ------------------------------------------------------------
create policy "clicks_read_org" on affiliate_clicks
    for select using (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ));

create policy "conversions_read_org" on conversions
    for select using (campaign_id in (
        select id from campaigns where organization_id = public.current_org_id()
    ));

-- ------------------------------------------------------------
-- jobs/audit_log: membros leem; escrita do worker via service role
-- ------------------------------------------------------------
create policy "jobs_read_org" on jobs
    for select using (organization_id = public.current_org_id());

create policy "audit_read_org" on audit_log
    for select using (organization_id = public.current_org_id());
