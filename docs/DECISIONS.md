# Decisões — Topfy Affiliate OS

Formato: `Decisão` (ADOTAR/INTEGRAR/ADAPTAR/CRIAR) · `Alternativas consideradas` ·
`Motivo` · `Data`. Mesmo padrão do `TopFy_Affiliate_Lab` (laboratório irmão deste
produto) — consistência entre os dois, não union.

## 1. ADOTAR `next/og` (`ImageResponse`) para cards de produto, não Pictify

- **Decisão:** gerar os cards de produto (imagem vertical/quadrada para as
  publicações) com `next/og`, embutido no Next.js desde a v14 (usa
  `@vercel/og`/Satori/Resvg internamente) — rota própria em `apps/web`, sem
  serviço externo, sem conta, sem chave de API.
- **Alternativas consideradas:** Pictify (free tier 50 imagens/mês, US$15/mês
  depois — era a escolha original do plano inicial), Bannerbear (US$49+/mês),
  Placid (marca d'água no free tier), Cloudinary (US$89+/mês).
- **Motivo:** a regra de descoberta do projeto prioriza solução open
  source/embutida madura sobre serviço especializado pago quando ambos
  resolvem o mesmo problema — `next/og` é oficial (parte do próprio Next.js),
  MIT, gratuito para sempre, sem teto de uso mensal e sem uma nova credencial
  pra gerenciar/vazar. Pictify só faria sentido se `next/og` não cobrisse o
  caso de uso, o que não é verdade aqui (título/preço/desconto/score em cima
  de flexbox e texto é exatamente o que `ImageResponse` faz bem).
- **Custos e limitações:** custo zero. `next/og` só suporta subconjunto
  flexbox de CSS, bundle máximo 500KB (JSX+CSS+fontes+imagens), fontes
  ttf/otf/woff — suficiente para um card de oferta, não para layouts
  complexos tipo grid.
- **Data:** 2026-08-01

## 2. ADOTAR vocabulário próprio de `verification_status`/`confidence`, divergente do laboratório

- **Decisão:** manter `UNKNOWN` / `NOT_AVAILABLE` / `VERIFIED` / `NOT_SUPPORTED`
  / `FAILED` como o vocabulário oficial de `products.affiliate_link_status` e
  `products.confidence` neste produto (já é o que está no CHECK constraint de
  `packages/db/migrations/0001_schema.sql`), em vez de adotar o vocabulário do
  laboratório (`PENDING` / `NOT_REQUESTED` / `VERIFIED`).
- **Alternativas consideradas:** renomear para bater 1:1 com o laboratório —
  descartado porque exigiria alterar o CHECK constraint já aplicado no
  Supabase, mais `connectors/aliexpress.py`, `pipeline.py`, `adapters/` e os
  20 testes já passando, sem nenhum ganho de comportamento (as duas
  nomenclaturas já cumprem a mesma regra: nunca marcar `VERIFIED` sem
  evidência real da API oficial).
- **Motivo:** Topfy Affiliate OS e CanalTopfy Bot de Cupons são produtos
  separados, com bancos e schemas separados — não precisam compartilhar
  vocabulário de enum, só a regra de fundo (nunca fabricar confiança sem
  evidência). Ratificar o que já está implementado evita um rename arriscado
  sem benefício, sobretudo com desenvolvimento ativo em paralelo nos mesmos
  arquivos.
- **Custos e limitações:** nenhum custo. Limitação: quem trabalhar nos dois
  produtos precisa lembrar que os nomes de status diferem mesmo a regra
  sendo a mesma — documentado aqui para não virar confusão futura.
- **Data:** 2026-08-01

## 3. ADOTAR OpenRouter (modelo grátis) para geração de copy, não Ollama local

- **Decisão:** gerar as 3 cópias de oferta via OpenRouter (openrouter.ai —
  agregador de LLMs hospedado, API no formato OpenAI `/chat/completions`),
  com modelo configurável por `OPENROUTER_MODEL` (padrão
  `deepseek/deepseek-chat:free`) — em vez de exigir Ollama instalado e
  rodando localmente. Sem `OPENROUTER_API_KEY`, `gerar_copy` continua caindo
  no fallback determinístico — nunca quebra por falta de credencial.
- **Alternativas consideradas:** manter Ollama local (rejeitado — pedido
  explícito de opção sem instalação/gerência de servidor local, "grátis e
  mais amigável"); DeepSeek API oficial direto (rejeitado — um provider a
  mais pra gerenciar credencial, sem ganho sobre o agregador); Groq
  (rejeitado — free tier bom, mas catálogo não inclui modelos DeepSeek, e o
  pedido citou DeepSeek).
- **Motivo:** o usuário queria trocar a dependência de infraestrutura local
  (instalar/rodar Ollama, baixar modelo, manter servidor local) por um
  serviço hospedado grátis — OpenRouter cobre isso com um único endpoint
  compatível com o formato OpenAI, modelos `:free` sem custo, e ainda dá pra
  trocar de modelo (DeepSeek, Llama, etc.) só mudando `OPENROUTER_MODEL`,
  sem tocar em código.
- **Custos e limitações:** custo zero no modelo `:free` padrão (rate limit
  mais apertado que planos pagos). Exige criar conta e gerar
  `OPENROUTER_API_KEY` em openrouter.ai/keys — usuário ainda não tinha a key
  no momento desta decisão. Catálogo de modelos grátis muda com o tempo;
  confirme o slug vigente em openrouter.ai/models antes de trocar
  `OPENROUTER_MODEL`.
- **Data:** 2026-08-01
