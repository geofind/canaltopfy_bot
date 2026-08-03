# Captura segura de cupons afiliados

Data: 3 de agosto de 2026.

## Referência editorial analisada

Foi analisada uma amostra de 36 mensagens recentes do canal [CUPONS DE DESCONTO DO PEPE](https://web.telegram.org/a/#-1001764811887):

| Marketplace | Posts observados |
| --- | ---: |
| Mercado Livre | 8 |
| Amazon | 8 |
| Shopee | 7 |
| Magalu | 5 |
| KaBuM | 5 |
| AliExpress | 3 |

Os links observados usam páginas diretas dos marketplaces e redirecionadores como `aoferta.net` e `ofertou.ai`. Esses redirecionadores são infraestrutura de monetização do canal, não uma fonte oficial de verdade. Nenhum link, tag de afiliado ou texto do canal é importado pelo Topfy.

Os sinais editoriais úteis foram:

- benefício na primeira linha;
- código destacado e isolado quando existe;
- compra mínima e limite máximo informados;
- indicação explícita de validade somente no aplicativo;
- CTA separado para testar/resgatar;
- aviso de que o cupom pode esgotar ou mudar.

## Arquitetura aplicada

O fluxo separa três responsabilidades:

1. **Descoberta:** somente API, página ou feed oficial do marketplace.
2. **Verificação:** campanha ativa, validade vigente e código somente quando o próprio dado oficial o declara.
3. **Monetização:** geração de um link usando as credenciais afiliadas do Topfy. Links de terceiros nunca são reaproveitados.

### Shopee — ativa

A Shopee Affiliate Open API documenta `shopeeOfferV2`, que retorna nome, início, fim, URL original e `offerLink` afiliado da própria conta. A implementação consulta a lista oficial a cada 15 minutos e filtra localmente sinais explícitos de cupom, voucher, desconto, cashback ou frete grátis.

No primeiro teste real, a conta retornou 30 campanhas oficiais com 30 links afiliados verificados, mas nenhuma campanha declarava cupom. Resultado correto do ciclo: `0 encontrado / 0 criado`. O motor não converte coleções comuns em cupons.

Quando surgir uma campanha compatível:

- cria um produto sintético na categoria `Cupons > Shopee`;
- registra origem `shopee_offer_v2`, validade e horário de verificação em `card_config.coupon_offer`;
- grava o `offerLink` como link afiliado `VERIFIED`;
- cria campanha e conteúdo aprovados automaticamente;
- deixa o reabastecedor incorporar a campanha à fila respeitando mix, score e diversidade.

### Mercado Livre — limite atual

A API oficial de cupons documentada pelo Mercado Livre é destinada a campanhas do próprio vendedor (`SELLER_COUPON_CAMPAIGN`). Ela não fornece um catálogo público de códigos gerais para compradores/afiliados. Portanto, cupons como os observados no canal não serão extraídos dessa API como se fossem públicos.

Referência oficial: https://developers.mercadolivre.com.br/pt_br/categorizacao-de-produtos/cupons-do-vendedor

### Amazon, Magalu e KaBuM — pendentes de fonte oficial afiliada

Esses marketplaces aparecem bastante na amostra, mas a automação só deve ser ativada quando a conta Topfy possuir um feed, relatório ou API oficial que entregue campanha/validade e permita gerar o link próprio. Scraping de encurtadores ou cópia de tags de terceiros continua bloqueado.

### AliExpress — próxima expansão

O conector já gera links afiliados oficiais. A próxima etapa é validar quais endpoints da conta entregam promoções destacadas e datas de campanha sem inferir código de cupom. Códigos continuam proibidos quando não vierem explicitamente da fonte oficial.

## Padrão de copy Topfy para cupons

Exemplo com código verificado:

```text
🔥 CUPOM SHOPEE DISPONÍVEL

🎟 R$ 50 OFF em Tecnologia
🏷 CÓDIGO: TOPFY50
📱 Válido somente no APP
⏳ Pode esgotar ou mudar sem aviso — confira antes de pagar.

🔗 Resgatar com o link Topfy
```

Exemplo sem código, mas com resgate oficial por link:

```text
🔥 CUPOM SHOPEE DISPONÍVEL

🎟 Cupom Tecnologia
✅ Resgate direto pelo link oficial
⏳ Pode esgotar ou mudar sem aviso — confira antes de pagar.

🔗 Resgatar com o link Topfy
```

O disclaimer de afiliado do Topfy e as hashtags de produto/marketplace continuam sendo acrescentados pelo publicador.

## Configuração

```dotenv
SHOPEE_COUPON_DISCOVERY_ENABLED=true
SHOPEE_COUPON_DISCOVERY_ORG_ID=
SHOPEE_COUPON_DISCOVERY_INTERVAL_MINUTES=15
SHOPEE_COUPON_DISCOVERY_MAX_NEW=3
```

`SHOPEE_COUPON_DISCOVERY_ORG_ID` vazio herda a organização já usada pela descoberta Shopee/fluxo automático.

## Distribuição na fila

Cupons verificados passam a ocupar uma meta editorial de **10%** das capturas e posições da fila. Essa meta é independente do mix de marketplaces: um cupom Shopee continua contando como Shopee na distribuição das fontes.

Quando não existe cupom oficial ativo suficiente, o motor redistribui os espaços entre ofertas normais aprovadas. A fila não para e códigos não são inventados para completar a meta.

## Validação

- API oficial autenticada: 30 campanhas e 30 links da própria conta retornados.
- Filtro conservador: zero falsos cupons publicados no primeiro ciclo.
- Registro de auditoria confirmado no Supabase em `coupon_discovery_shopee`.
- 234 testes automatizados aprovados.
- Worker ativo após reinício.

### Aplicação retroativa na fila

Em 3 de agosto de 2026, a ordem manual protegida foi desativada por solicitação do usuário e a distribuição automática foi aplicada às 95 campanhas `PENDING`:

- 95 campanhas redistribuídas;
- duas próximas posições preservadas na ordem;
- 69 horários antigos/vencidos reprogramados;
- nenhum item permaneceu atrasado;
- nova cadência: intervalos de cinco minutos, de 11:16 a 19:06 no horário de Brasília;
- zero cupons verificados disponíveis naquele momento; a meta de 10% passa a ser preenchida à medida que fontes oficiais entregarem cupons válidos.
