-- Completa a semente de discovery_categories: offer_rules.py cresceu de
-- 16 para 23 famílias (componentes de PC) depois que 0016 rodou, então
-- toda organização ficou sem essas 7 categorias na tela — o worker já as
-- reconhece (category_family), só não apareciam pra curadoria em
-- /campanhas. Idempotente: só insere o que ainda não existe.

insert into discovery_categories (organization_id, family_key, label)
select o.id, v.family_key, v.label
from organizations o
cross join (values
    ('placas-mae', 'Placas-mãe'),
    ('processadores', 'Processadores'),
    ('memorias', 'Memórias RAM'),
    ('placas-video', 'Placas de vídeo'),
    ('fontes-pc', 'Fontes para PC'),
    ('refrigeracao-pc', 'Refrigeração para PC'),
    ('gabinetes-pc', 'Gabinetes')
) as v(family_key, label)
on conflict (organization_id, family_key) do nothing;
