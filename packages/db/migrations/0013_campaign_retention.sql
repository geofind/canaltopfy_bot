-- Mantém no máximo as 200 campanhas mais recentes de cada organização.
-- Contents, publications e queue_items são removidos pelos FKs ON DELETE
-- CASCADE; clicks e conversions preservam o histórico com campaign_id nulo.

create or replace function public.enforce_campaign_retention()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    -- Serializa inserções da mesma organização para o teto continuar estrito
    -- mesmo se dois capturadores criarem campanhas simultaneamente.
    perform pg_advisory_xact_lock(
        hashtext('campaign_retention'),
        hashtext(new.organization_id::text)
    );

    delete from public.campaigns
    where id in (
        select id
        from public.campaigns
        where organization_id = new.organization_id
        order by created_at desc, id desc
        offset 200
    );

    return new;
end;
$$;

revoke all on function public.enforce_campaign_retention() from public;
revoke all on function public.enforce_campaign_retention() from anon;
revoke all on function public.enforce_campaign_retention() from authenticated;

drop trigger if exists campaigns_enforce_retention on public.campaigns;
create trigger campaigns_enforce_retention
after insert on public.campaigns
for each row execute function public.enforce_campaign_retention();

-- Aplica a mesma retenção caso a base já esteja acima do limite ao instalar.
with ranked as (
    select id,
           row_number() over (
               partition by organization_id
               order by created_at desc, id desc
           ) as position
    from public.campaigns
)
delete from public.campaigns
where id in (select id from ranked where position > 200);
