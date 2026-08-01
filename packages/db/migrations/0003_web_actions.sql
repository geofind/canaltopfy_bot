-- ============================================================
-- Topfy Affiliate OS — migração 0003: suporte às actions da web
-- ============================================================

-- Configuração de canal por campanha (ex.: chat_id do Telegram).
-- Guardada no banco (fonte da verdade), preenchida pelo dono na UI.
alter table campaigns
    add column channel_config jsonb not null default '{}'::jsonb;

-- Resumo rápido para o dashboard (evita N+1 no web).
create index if not exists idx_contents_campaign_status
    on contents (campaign_id, status);
create index if not exists idx_publications_channel
    on publications (channel);
