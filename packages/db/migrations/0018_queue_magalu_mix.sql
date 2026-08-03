-- Inclui Magalu no mix editorial das filas.
-- O valor inicial zero preserva filas existentes; a escolha do novo mix e
-- feita separadamente, por organizacao, depois da migration.

alter table public.queues
    add column if not exists magalu_target_percent integer not null default 0;

alter table public.queues
    drop constraint if exists queues_source_mix_valid;

alter table public.queues
    add constraint queues_source_mix_valid check (
        shopee_target_percent between 0 and 100
        and aliexpress_target_percent between 0 and 100
        and mercadolivre_target_percent between 0 and 100
        and magalu_target_percent between 0 and 100
        and shopee_target_percent
            + aliexpress_target_percent
            + mercadolivre_target_percent
            + magalu_target_percent = 100
    );
