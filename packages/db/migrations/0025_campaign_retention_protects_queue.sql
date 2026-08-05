-- Bug real observado em produção: a retenção de 200 campanhas (migração
-- 0013) apaga estritamente pela mais recente `created_at`, sem checar se a
-- campanha ainda está PENDING/DISPATCHED numa fila — e queue_items é
-- ON DELETE CASCADE de campaigns. Com a captura rodando rápido (reabaste-
-- cedor + auto_pipeline), campanhas novas empurram pra fora do limite de
-- 200 campanhas que ainda não foram publicadas mas já estão agendadas até
-- 7-8h à frente — o cascade apaga o queue_item junto e a fila de
-- publicação esvazia sozinha, sem nenhum erro nem log.
--
-- Correção: campanhas com queue_item ativo (PENDING/DISPATCHED) nunca
-- entram no cálculo do "offset 200" nem são apagadas por esta rotina —
-- elas só saem de circulação quando o worker as publica (status DONE/
-- CANCELLED no queue_item) ou quando são removidas manualmente da fila.

create or replace function public.enforce_campaign_retention()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    perform pg_advisory_xact_lock(
        hashtext('campaign_retention'),
        hashtext(new.organization_id::text)
    );

    delete from public.campaigns
    where id in (
        select id
        from public.campaigns
        where organization_id = new.organization_id
          and not exists (
              select 1 from public.queue_items qi
              where qi.campaign_id = campaigns.id
                and qi.status in ('PENDING', 'DISPATCHED')
          )
        order by created_at desc, id desc
        offset 200
    );

    return new;
end;
$$;
