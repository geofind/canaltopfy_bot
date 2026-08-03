# Integração do Influenciador Magalu

## Resultado

A conta **Magazine Canaltopfy** está ativa no Influenciador Magalu. A identificação de afiliado é a vitrine `magazinecanaltopfy`; não existe token de Affiliate API para essa modalidade.

Configuração usada pelo worker:

```dotenv
MAGALU_STORE_SLUG=canaltopfy
MAGALU_STOREFRONT_URL=https://www.magazinevoce.com.br/magazinecanaltopfy/
MAGALU_COUPONS_URL=https://especiais.magazineluiza.com.br/magazinevoce/cupons/?showcase=magazinecanaltopfy
```

## Como a atribuição funciona

- Produtos usam o domínio `www.magazinevoce.com.br` e o prefixo `/magazinecanaltopfy/`.
- Páginas especiais, como a página oficial de cupons, usam `showcase=magazinecanaltopfy`.
- O conector marca um link como verificado somente quando uma dessas duas formas de atribuição está presente.
- O conector não inventa título, preço, imagem ou desconto quando não há uma fonte oficial estruturada.

## Por que não há token

O tutorial `luizalabs/tutorial-python-brasil` demonstra uma API alpha voltada ao marketplace e usa um tenant `SELLER` para consultar pedidos. A plataforma atual Magalu Devs também descreve autorização OAuth concedida por sellers a aplicações de catálogo, pedidos e operação. Esse acesso não representa o Influenciador Magalu e não gera links de comissão.

Por segurança, nenhuma chave de seller foi solicitada ou reutilizada no bot de afiliados.

## Fluxo implementado

1. O usuário importa uma URL de produto Magalu ou Magazine Você.
2. O pipeline seleciona `MagaluConnector`.
3. O conector transforma a URL na vitrine `magazinecanaltopfy`.
4. A atribuição é verificada antes de persistir o link.
5. O produto segue o fluxo existente de score, copy, fila e Telegram quando os dados de catálogo estiverem completos.

## Catálogo inicial e captura automática

Em 03/08/2026 foi criado um seed auditável com 20 páginas oficiais indexadas
do Magazine Você. Ele fica em `apps/worker/data/magalu_seed_offers.json` e
registra URL de origem, data da indexação, produto, seller, preço, preço
anterior, avaliação e imagem oficial `mlcdn.com.br`.

Esse seed resolve a carga inicial sem contornar o CAPTCHA da vitrine e sem
reutilizar a API de seller. Não é tratado como preço em tempo real: a confiança
é `STALE`, fica explícita no Topfy Score e deve ser substituída por uma fonte
oficial de afiliados quando ela estiver disponível.

O método `MagaluConnector.search_offers()` filtra esse catálogo por termo. O
`ciclo_automatico(..., source_name="magalu")` usa o fluxo comum de deduplicação,
diversidade, link verificado, Topfy Score, copy, aprovação e fila.

O reabastecedor inclui Magalu na escolha por déficit do mix. Depois que os 20
itens do seed forem consumidos, novas tentativas são idempotentes e não duplicam
produto; ampliar a captura exige acrescentar novas páginas oficiais auditadas.

## Ativação executada em 03/08/2026

- Migration `0018_queue_magalu_mix.sql` aplicada no Supabase.
- Mix salvo: 40% Shopee, 10% AliExpress, 30% Mercado Livre e 20% Magalu.
- 20 produtos importados, 20 links verificados e 20 campanhas aprovadas.
- As 20 campanhas entraram na fila; 99 posições pendentes foram reordenadas em
  intervalos de 5 minutos, preservando os dois próximos slots protegidos.
- Worker reiniciado e painel publicado no alias de produção
  `https://web-lac-seven-pg17eswj7d.vercel.app`.

## Verificação

Execute:

```powershell
python -m unittest discover -s apps/worker/tests -p "test_*.py"
```

Os testes cobrem detecção de domínio, conversão da URL, preservação da vitrine,
página de cupons, extração do ID, ausência de credencial, quantidade mínima de
20 ofertas e filtragem do seed por termo. Além dos testes, confirme no banco:
`source_name = 'magalu'`, link `VERIFIED`, campanha `APPROVED`, fila `PENDING`
e presença de preço e imagem.
