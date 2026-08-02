-- ============================================================
-- Topfy Affiliate OS — migração 0007: refresh_token opcional
-- A resposta de /oauth/token do app Mercado Livre não inclui
-- refresh_token (confirmado em produção — só access_token,
-- token_type, expires_in, scope, user_id). Sem isso o upsert em
-- ml_credentials violava o not null. access_token expira em ~6h;
-- sem refresh_token, reconectar exige refazer o fluxo OAuth.
-- ============================================================

alter table ml_credentials
    alter column refresh_token drop not null;
