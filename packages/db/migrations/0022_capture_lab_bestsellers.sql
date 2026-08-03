-- Laboratório de Captura: priorizar produtos mais vendidos por categoria.
-- `prioritize_bestsellers` reforça o peso da dimensão "vendas" do Topfy
-- Score para produtos dessa categoria (scoring.py) e, para Mercado Livre,
-- soma a categoria oficial (`ml_category_id`, formato "MLB1055") à lista
-- de categorias consultadas no endpoint de "mais vendidos" (highlights) —
-- hoje só configurável via variável de ambiente do worker.

alter table discovery_categories
    add column if not exists prioritize_bestsellers boolean not null default false;

alter table discovery_categories
    add column if not exists ml_category_id text;

alter table discovery_categories
    drop constraint if exists discovery_categories_ml_category_id_format;

alter table discovery_categories
    add constraint discovery_categories_ml_category_id_format
        check (ml_category_id is null or ml_category_id ~ '^MLB\d+$');
