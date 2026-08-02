-- ============================================================
-- Topfy Affiliate OS — migração 0005: provider de IA da copy
-- Troca Ollama (local) por OpenRouter (hospedado, API formato
-- OpenAI, tem modelos grátis — ex. DeepSeek). Decisão registrada
-- em docs/DECISIONS.md.
-- ============================================================

alter table contents
    drop constraint if exists contents_provider_check;

alter table contents
    add constraint contents_provider_check
    check (provider in ('openrouter', 'openai', 'anthropic', 'fallback', 'manual'));
