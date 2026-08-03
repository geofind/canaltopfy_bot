-- Controles editoriais da fila: mix por marketplace e reordenação atômica.

alter table public.queues
    add column if not exists shopee_target_percent integer not null default 50,
    add column if not exists aliexpress_target_percent integer not null default 20,
    add column if not exists mercadolivre_target_percent integer not null default 30;

alter table public.queues
    drop constraint if exists queues_source_mix_valid;

alter table public.queues
    add constraint queues_source_mix_valid check (
        shopee_target_percent between 0 and 100
        and aliexpress_target_percent between 0 and 100
        and mercadolivre_target_percent between 0 and 100
        and shopee_target_percent
            + aliexpress_target_percent
            + mercadolivre_target_percent = 100
    );

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
        raise exception 'Sessão sem organização';
    end if;

    if not exists (
        select 1
        from public.queues q
        where q.id = p_queue_id
          and q.organization_id = public.current_org_id()
    ) then
        raise exception 'Fila não encontrada';
    end if;

    -- Impede o worker de alterar o mesmo conjunto durante a troca de horários.
    perform 1
    from public.queue_items qi
    where qi.queue_id = p_queue_id
      and qi.organization_id = public.current_org_id()
      and qi.status = 'PENDING'
    for update;

    select count(*) into v_expected
    from public.queue_items qi
    where qi.queue_id = p_queue_id
      and qi.organization_id = public.current_org_id()
      and qi.status = 'PENDING';

    if v_received <> v_expected then
        raise exception 'A fila mudou; recarregue antes de ordenar';
    end if;

    if exists (
        select 1
        from unnest(p_item_ids) wanted(id)
        left join public.queue_items qi
          on qi.id = wanted.id
         and qi.queue_id = p_queue_id
         and qi.organization_id = public.current_org_id()
         and qi.status = 'PENDING'
        where qi.id is null
    ) then
        raise exception 'A ordem contém item inválido';
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
        select desired.id, slots.scheduled_at
        from desired
        join slots using (position)
    )
    update public.queue_items qi
    set scheduled_at = mapping.scheduled_at
    from mapping
    where qi.id = mapping.id;
end;
$$;

revoke all on function public.reorder_queue_items(uuid, uuid[]) from public;
revoke all on function public.reorder_queue_items(uuid, uuid[]) from anon;
grant execute on function public.reorder_queue_items(uuid, uuid[]) to authenticated;
grant execute on function public.reorder_queue_items(uuid, uuid[]) to service_role;
