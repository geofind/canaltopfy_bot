-- Galeria de imagens do produto: guarda as fotos extras que o conector já
-- devolve (image_urls, hoje descartado no import) pra permitir trocar a
-- foto exibida na fila (QueueEditor) sem depender de banco de imagens
-- próprio. products.image_url continua sendo a foto usada no post (worker
-- lê na hora da publicação, pipeline.py imagem_para_post/publish_to_
-- telegram) — a galeria só alimenta a troca manual antes de publicar.

alter table products
    add column if not exists image_urls jsonb not null default '[]'::jsonb;
