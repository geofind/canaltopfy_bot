-- Inclui Magalu como fonte de palavras-chave do Laboratório de Captura
-- (/campanhas) — ciclo_automatico já aceita source_name="magalu"
-- (connectors/magalu.py: catálogo auditável por página oficial indexada).

alter table discovery_keywords
    drop constraint if exists discovery_keywords_source_name_check;

alter table discovery_keywords
    add constraint discovery_keywords_source_name_check
        check (source_name in ('aliexpress', 'shopee', 'mercadolivre', 'magalu'));
