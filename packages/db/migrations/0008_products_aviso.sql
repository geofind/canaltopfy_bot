-- ============================================================
-- Topfy Affiliate OS — migração 0008: products.aviso
-- Os conectores (aliexpress.py, mercadolivre.py) já preenchem um
-- campo "aviso" explicando degradação (sem credencial, API
-- recusou, product_id não encontrado) — faltava a coluna, e o
-- insert falhava com PGRST204 sempre que havia aviso.
-- ============================================================

alter table products
    add column if not exists aviso text;
