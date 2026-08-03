-- Preserva a ordem editorial definida no dashboard entre os ciclos do worker.

alter table public.queues
    add column if not exists manual_order_locked boolean not null default false;

create or replace function public.reorder_queue_items(
    p_queue_id uuid,
    p_item_ids uuid[]
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_expected integer;
    v_received integer := coalesce(cardinality(p_item_ids), 0);
begin
    if public.current_org_id() is null then
        raise exception 'Sessao sem organizacao';
    end if;

    if not exists (
        select 1 from public.queues q
        where q.id = p_queue_id
          and q.organization_id = public.current_org_id()
    ) then
        raise exception 'Fila nao encontrada';
    end if;

    perform 1 from public.queue_items qi
    where qi.queue_id = p_queue_id
      and qi.organization_id = public.current_org_id()
      and qi.status = 'PENDING'
    for update;

    select count(*) into v_expected from public.queue_items qi
    where qi.queue_id = p_queue_id
      and qi.organization_id = public.current_org_id()
      and qi.status = 'PENDING';

    if v_received <> v_expected then
        raise exception 'A fila mudou; recarregue antes de ordenar';
    end if;

    if exists (
        select 1 from unnest(p_item_ids) wanted(id)
        left join public.queue_items qi
          on qi.id = wanted.id
         and qi.queue_id = p_queue_id
         and qi.organization_id = public.current_org_id()
         and qi.status = 'PENDING'
        where qi.id is null
    ) then
        raise exception 'A ordem contem item invalido';
    end if;

    with desired as (
        select id, ordinality as position
        from unnest(p_item_ids) with ordinality as wanted(id, ordinality)
    ), slots as materialized (
        select qi.scheduled_at,
               row_number() over (order by qi.scheduled_at, qi.created_at, qi.id) as position
        from public.queue_items qi
        where qi.queue_id = p_queue_id
          and qi.organization_id = public.current_org_id()
          and qi.status = 'PENDING'
    ), mapping as (
        select desired.id, slots.scheduled_at from desired join slots using (position)
    )
    update public.queue_items qi
    set scheduled_at = mapping.scheduled_at
    from mapping
    where qi.id = mapping.id;

    update public.queues
    set manual_order_locked = true, updated_at = now()
    where id = p_queue_id
      and organization_id = public.current_org_id();
end;
$$;

revoke all on function public.reorder_queue_items(uuid, uuid[]) from public;
revoke all on function public.reorder_queue_items(uuid, uuid[]) from anon;
grant execute on function public.reorder_queue_items(uuid, uuid[]) to authenticated;
grant execute on function public.reorder_queue_items(uuid, uuid[]) to service_role;
