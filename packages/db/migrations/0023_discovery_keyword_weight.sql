-- Laboratório de Captura: prioridade/peso por palavra-chave do Finder.
-- Candidatos achados por um termo de peso maior são avaliados antes dos
-- demais em cada ciclo de captura (ciclo_automatico em pipeline.py) — sem
-- isso, a única forma de "priorizar" um termo era editar a env var do
-- worker. Escala simples de 3 níveis (1=baixa, 2=normal, 3=alta) em vez de
-- um número livre, pra não virar um campo difícil de calibrar pela tela.

alter table discovery_keywords
    add column if not exists weight smallint not null default 2;

alter table discovery_keywords
    drop constraint if exists discovery_keywords_weight_range;

alter table discovery_keywords
    add constraint discovery_keywords_weight_range check (weight between 1 and 3);
