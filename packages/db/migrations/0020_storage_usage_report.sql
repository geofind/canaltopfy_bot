-- Monitor de armazenamento (/sistema): tamanho ocupado na nuvem (Supabase).
-- Só leitura de estatísticas de catálogo — nenhuma linha de tabela é
-- exposta, então não há dado de organização vazando por aqui.

create or replace function public.database_size_bytes()
returns bigint
language sql
security definer
set search_path = ''
as $$
    select pg_database_size(current_database());
$$;

create or replace function public.storage_usage_report()
returns table (table_name text, total_bytes bigint, row_estimate bigint)
language sql
security definer
set search_path = ''
as $$
    select
        c.relname::text as table_name,
        pg_total_relation_size(c.oid) as total_bytes,
        greatest(c.reltuples, 0)::bigint as row_estimate
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r'
    order by pg_total_relation_size(c.oid) desc;
$$;

revoke all on function public.database_size_bytes() from public;
revoke all on function public.database_size_bytes() from anon;
grant execute on function public.database_size_bytes() to authenticated;
grant execute on function public.database_size_bytes() to service_role;

revoke all on function public.storage_usage_report() from public;
revoke all on function public.storage_usage_report() from anon;
grant execute on function public.storage_usage_report() to authenticated;
grant execute on function public.storage_usage_report() to service_role;
