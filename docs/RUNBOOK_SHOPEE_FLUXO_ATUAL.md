# Shopee no fluxo atual do Topfy

Registro da implementação e validação realizada em 3 de agosto de 2026.

## Resultado

A Shopee foi incorporada ao mesmo fluxo já usado pelo app:

`Affiliate Open API -> normalização -> desconto mínimo -> Topfy Score -> deduplicação -> diversidade de categoria -> copy/hashtags -> aprovação automática -> fila existente -> Telegram`

Não existe publicador paralelo. O ciclo dedicado da Shopee permanece desligado
por padrão; o reabastecedor atual é quem escolhe a fonte conforme o mix.

Mix configurado:

- Shopee: 50%;
- AliExpress: 20%;
- Mercado Livre/Meli: 30%.

Campanhas aprovadas e ainda não publicadas também entram no balanceamento. Para
convergir uma fila antiga, o agente cancela somente o vínculo `PENDING` mais
distante de uma fonte excedente. Produto, campanha, copy, link e aprovação não
são apagados e permanecem disponíveis no inventário.

## API oficial confirmada

- Endpoint: `https://open-api.affiliate.shopee.com.br/graphql`;
- método: `POST` com `application/json`;
- assinatura: SHA-256 hexadecimal minúsculo de
  `AppID + Timestamp + payload exato + Secret`;
- header: `SHA256 Credential=..., Timestamp=..., Signature=...`;
- tolerância do relógio: até 10 minutos;
- limite observado na documentação autenticada: 8.000 chamadas/hora;
- catálogo: query `productOfferV2`;
- shortlink: mutation `generateShortLink`;
- erros GraphQL podem vir com HTTP 200; o conector trata `errors` e faz backoff
  para throttle/códigos transitórios.

Documentação oficial:

- <https://affiliate.shopee.com.br/open_api/home>
- <https://affiliate.shopee.com.br/open_api/list?type=product_offer>
- <https://affiliate.shopee.com.br/open_api/list?type=short_link>
- <https://affiliate.shopee.com.br/open_api/document?type=authentication>
- <https://affiliate.shopee.com.br/open_api/document?type=request_response>

## Configuração

O conector aceita os nomes oficiais abaixo e, por compatibilidade com o `.env`
existente, também aceita `SHOPPE_APP_KEY` e `SHOPPE_APP_SECRET`:

```dotenv
SHOPEE_AFFILIATE_APP_ID=
SHOPEE_AFFILIATE_SECRET=
SHOPEE_AFFILIATE_ENDPOINT=https://open-api.affiliate.shopee.com.br/graphql
SHOPEE_AFFILIATE_SUB_IDS=canaltopfy,telegram

REPLENISHER_SHOPEE_TARGET_PERCENT=50
REPLENISHER_ALIEXPRESS_TARGET_PERCENT=20
REPLENISHER_ML_TARGET_PERCENT=30
```

Os três percentuais precisam somar 100. As credenciais ficam somente no worker,
nunca no Next.js, heartbeat ou logs.

## Arquivos alterados

- `apps/worker/connectors/shopee.py`: autenticação, catálogo, normalização,
  shortlink, verificação e health check;
- `apps/worker/pipeline.py`: registro da fonte e uso do pipeline comum;
- `apps/worker/replenisher.py`: mix 50/20/30, score ponderado, campanhas já
  aprovadas e convergência gradual da fila;
- `apps/worker/main.py`: configuração, heartbeat e execução do agente;
- `apps/web/src/lib/actions.ts`: importação de URLs Shopee;
- dashboard, ofertas, sugestões, página pública e Integrações: rótulo e dados
  reais da Shopee;
- `.env.example`: contrato de configuração reproduzível.

## Validações executadas

- autenticação real: OK;
- `productOfferV2`: 20 ofertas reais retornadas no teste;
- campos confirmados: ID, título, imagem, preço, desconto, comissão e
  `offerLink`;
- `generateShortLink`: OK, domínio oficial `s.shopee.com.br`;
- canário ponta a ponta: campanhas Shopee capturadas, pontuadas, copiadas,
  aprovadas e enfileiradas sem aprovação humana;
- build Next.js de produção: aprovado;
- suíte do worker: 203 testes aprovados.

No primeiro período de convergência, a fila histórica tinha 85 itens: 77
AliExpress, 8 Mercado Livre e 0 Shopee. Depois dos primeiros lotes, chegou a 95
itens: 70 AliExpress, 8 Mercado Livre e 17 Shopee. O worker PID 38008 ficou
ativo para continuar a convergência em lotes de até 4, sem tocar nos próximos
dois horários de publicação.

## Operação e rollback

O worker local inicia por `apps/worker/run_worker.bat`, que chama
`_local_bootstrap.py` para usar o repositório de certificados do Windows.

Para interromper novas capturas Shopee sem afetar publicações já agendadas,
defina a meta da Shopee como zero e redistribua os outros percentuais para
somarem 100, depois reinicie o worker. Não apague produtos, campanhas ou itens
da fila manualmente.

O percentual de Mercado Livre só converge quando existem links de afiliado
oficiais confirmados pelo Link Builder/Hermes. Na falta deles, o agente preserva
a autonomia da fila com as APIs disponíveis e continua solicitando os links
oficiais, sem fabricar atribuição.
