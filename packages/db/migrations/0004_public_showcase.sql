-- ============================================================
-- Topfy Affiliate OS — migração 0004: leitura pública da vitrine
-- Anônimos (visitantes e bots do Telegram) leem só o que é
-- público: campanhas com public_page, produtos delas, conteúdo
-- aprovado e publicações PUBLISHED. Escrita continua só via
-- membro autenticado (policies 0002) ou service role (worker).
-- ============================================================

create policy "campaigns_public_read" on campaigns
    for select using (public_page = true);

create policy "products_public_read" on products
    for select using (exists (
        select 1 from campaigns c
        where c.product_id = products.id
          and c.public_page = true
    ));

create policy "contents_public_read" on contents
    for select using (
        status = 'APPROVED'
        and exists (
            select 1 from campaigns c
            where c.id = contents.campaign_id
              and c.public_page = true
        )
    );

create policy "publications_public_read" on publications
    for select using (
        status = 'PUBLISHED'
        and exists (
            select 1 from campaigns c
            where c.id = publications.campaign_id
              and c.public_page = true
        )
    );
