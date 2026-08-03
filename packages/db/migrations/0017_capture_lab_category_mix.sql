-- Laboratório de Captura: meta de distribuição (%) por categoria, com
-- redistribuição forçada da fila pendente sob pedido do usuário
-- (independente da fonte/loja — complementa o mix por marketplace que já
-- existe em queues.*_target_percent).

alter table discovery_categories
    add column if not exists target_percent integer;

alter table discovery_categories
    drop constraint if exists discovery_categories_target_percent_valid;

alter table discovery_categories
    add constraint discovery_categories_target_percent_valid
        check (target_percent is null or target_percent between 0 and 100);
