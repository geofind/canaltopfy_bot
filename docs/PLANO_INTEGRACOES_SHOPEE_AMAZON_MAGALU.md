# Plano de integração — Shopee, Amazon e Magalu

## Decisão técnica

O Topfy continuará usando um conector por marketplace, normalizando todos os
resultados para o mesmo produto interno antes de aplicar score, deduplicação,
diversidade, copy, fila e publicação no Telegram. Nenhum conector poderá
publicar diretamente: ele apenas descobre o produto e entrega um link afiliado
oficial ao motor existente.

Ordem de implantação:

1. Shopee Affiliate Open API Brasil;
2. Amazon Creators API Brasil;
3. Influenciador Magalu, condicionado a uma API/parceria oficial.

## 1. Shopee — primeira integração

### Fonte aprovada

- Portal oficial: <https://affiliate.shopee.com.br/open_api> (documentação
  exige login e acesso aprovado);
- endpoint configurável:
  `https://open-api.affiliate.shopee.com.br/graphql`;
- autenticação com App ID, Secret, timestamp e assinatura SHA-256;
- descoberta por `productOfferV2`/ofertas disponíveis na conta;
- link oficial retornado pela oferta ou pela mutation `generateShortLink`;
- Sub IDs para atribuir conversões a `canaltopfy` e `telegram`.

A documentação autenticada da conta confirmou em 3 de agosto de 2026:

- todas as operações usam `POST`, `application/json` e o mesmo endpoint;
- assinatura em hexadecimal minúsculo de
  `SHA256(AppID + timestamp + payload exato + Secret)`;
- o relógio do worker não pode divergir mais de 10 minutos do servidor;
- limite atual de 8.000 chamadas por hora;
- `productOfferV2` fornece `priceMin`, `priceMax`, `priceDiscountRate`,
  `sales`, `ratingStar`, comissões, `productLink` e `offerLink`;
- a plataforma também oferece feeds de produtos, shortlink, relatório de
  conversões e relatório validado;
- erros GraphQL chegam normalmente com HTTP 200 e códigos como 10010
  (request), 10020 (autenticação), 10030 (limite) e 11000 (negócio).

As regras oficiais da Shopee reconhecem links fornecidos pelo Programa e a
Central de Ajuda orienta gerar links com Sub IDs. Não serão usados cookies,
sessão de navegador, endpoints privados ou scraping.

### Código gratuito avaliado

| Projeto | Uso recomendado | Decisão |
| --- | --- | --- |
| [RenanGalvao/saapi](https://github.com/RenanGalvao/saapi) | Referência Python tipada para queries e mutations da Affiliate API; licença MIT | Melhor referência para o conector, mas revisar assinatura, país Brasil e respostas reais antes de adicionar como dependência |
| [vinniciusnascimento/bot-achadinhos](https://github.com/vinniciusnascimento/bot-achadinhos) | Exemplo brasileiro de assinatura SHA-256, busca GraphQL e Telegram; licença ISC | Aproveitar apenas padrões testáveis; não copiar o bot inteiro nem seu agendador |
| [bcat95/shopee-aff](https://github.com/bcat95/shopee-aff) | Catálogo de operações e exemplos GraphQL | Consulta secundária; exemplos são do Vietnã e precisam ser confrontados com a documentação brasileira autenticada |
| [snja/shopee-affiliate-openapi](https://github.com/snja/shopee-affiliate-openapi) | Wrapper Python antigo | Rejeitado: arquivado, uma única revisão e voltado à Indonésia |

Não foi localizado plugin pronto nem MCP oficial de afiliados Shopee. MCPs de
monitoramento encontrados usam captura não oficial e não entrarão no worker.

### Fases e critérios de aceite

1. **Credenciais** — preencher `SHOPEE_AFFILIATE_APP_ID` e
   `SHOPEE_AFFILIATE_SECRET`; manter `SHOPEE_DISCOVERY_ENABLED=false`.
2. **Prova de autenticação** — teste isolado com relógio UTC, assinatura
   determinística, timeout, redaction de segredo e tratamento de 401/429.
3. **Prova de link** — gerar shortlink de um produto real e confirmar que o
   domínio/redirect preserva a atribuição da conta e os Sub IDs.
4. **Conector** — criar `apps/worker/connectors/shopee.py` com paginação,
   retries com backoff e normalização de título, imagem, preços, desconto,
   avaliação, vendas, comissão, categoria e URL afiliada.
5. **Qualidade** — aplicar o mesmo Topfy Score, histórico de preço,
   deduplicação por item/URL, bloqueio de categorias consecutivas e cupom
   somente quando a API retornar código e validade verificáveis.
6. **Fila** — adicionar Shopee ao reabastecedor com cota inicial pequena
   (10–20%), seleção por score e sorteio ponderado entre fontes.
7. **Observabilidade** — heartbeat sem segredos, métricas de chamadas,
   throttle, candidatos, rejeições, links gerados e publicações.
8. **Liberação** — canário com uma oferta, depois 24 horas em baixa cota; só
   então ativar `SHOPEE_DISCOVERY_ENABLED=true` continuamente.

Testes obrigatórios: assinatura conhecida, timestamp expirado, credencial
inválida, rate limit, paginação, campos ausentes, preço em centavos, desconto,
URL inválida, deduplicação, score, diversidade, imagem e publicação Telegram.

## 2. Amazon — segunda integração

Usar exclusivamente a [Creators API](https://affiliate-program.amazon.com/creatorsapi/docs/),
que oferece `SearchItems`, `GetItems`, imagens e ofertas para o marketplace
brasileiro. A conta precisa estar no Amazon Associates do Brasil, registrar
credenciais e, conforme a documentação atual, ter pelo menos dez vendas
qualificadas nos últimos 30 dias.

O conector precisará de `AMAZON_CLIENT_ID`, `AMAZON_CLIENT_SECRET`, Partner Tag,
marketplace `www.amazon.com.br`, cache do token OAuth por até uma hora e links
retornados sem alteração. A antiga PA-API 5.0 e seus SDKs não devem ser
adotados. Os MCPs encontrados para Amazon tratam compras ou Seller Central,
não o programa de afiliados.

## 3. Magalu — terceira integração

O programa oficial [Influenciador Magalu](https://www.magazinevoce.com.br/)
permite compartilhar a loja e links específicos gerados pela área do
influenciador. Na pesquisa pública não foi encontrada API oficial de afiliados,
SDK ou MCP confiável para descoberta e geração automática desses links.

Portanto, a primeira versão deve ser assistida: importar um link oficial já
gerado na conta, validar que pertence à loja do usuário e deixar o motor cuidar
de score, copy, fila e Telegram. Automação total só será implementada se o
Magalu fornecer documentação/API ou autorização escrita; não serão usados
scraping autenticado, cookies copiados ou endpoints privados.

## Segurança operacional

- `.env` real nunca é versionado; `.env.example` contém apenas nomes e padrões;
- segredos permanecem no worker, nunca no Next.js ou no heartbeat;
- logs mascaram App ID, Secret, tokens e headers de autorização;
- cada fonte tem circuit breaker, timeout, limite de chamadas e kill switch;
- nenhum produto entra na fila sem URL afiliada oficial e dados mínimos
  verificáveis.
