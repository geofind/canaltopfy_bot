# Descoberta de ofertas Mercado Livre

## O que foi aproveitado do projeto de referência

O repositório `p0nch000/MercadoLibre-AffiliateMarketing` mostrou um fluxo útil:
consultar produtos por categoria/termo, calcular desconto, deduplicar e distribuir
os resultados ao longo do tempo. O código dele não foi copiado porque é voltado
ao México (`MLM`), recria o banco a cada inicialização e não implementa a geração
do link afiliado — apenas espera que outra rotina preencha esse campo.

No CanalTopfy, a implementação equivalente usa somente a API oficial:

- `GET /sites/MLB/search`, com o OAuth da organização;
- anúncios individuais em BRL;
- filtro por desconto mínimo e deduplicação por `external_id`;
- produto e campanha privada no Supabase;
- auditoria `mercadolivre_oferta_descoberta`;
- nenhuma aprovação, publicação ou redirect enquanto faltar link afiliado.

Não há scraping do site, cookies de navegador, engenharia reversa do Portal de
Afiliados nem acesso a endpoints privados.

## Configuração do worker

```dotenv
ML_DISCOVERY_ENABLED=true
ML_DISCOVERY_ORG_ID=<uuid-da-organizacao>
ML_DISCOVERY_TERMOS=smartphone,notebook,fone bluetooth
ML_DISCOVERY_MIN_DISCOUNT=10
ML_DISCOVERY_MAX_NOVOS=10
ML_DISCOVERY_INTERVAL_MINUTES=60
```

A conta deve estar conectada em `/integracoes`. Se o access token estiver
expirado e a autorização não tiver produzido `refresh_token`, é necessário
clicar em **Conectar novamente**. O worker registra um erro claro e não tenta
contornar a autenticação.

## Links afiliados

Na documentação pública atual do Programa de Afiliados do Mercado Livre Brasil,
os links são gerados pela Central de Afiliados ou pela Barra de Afiliados. A API
de desenvolvedores usada para consultar anúncios não documenta um endpoint de
geração de link afiliado.

Por isso, cada oferta descoberta fica com:

- `affiliate_link = null`;
- `affiliate_link_status = UNKNOWN`;
- campanha privada em `READY`;
- nenhuma entrada automática na fila de publicação.

Só depois de receber um link produzido por uma ferramenta oficial da conta a
campanha pode seguir para copy, aprovação e publicação. Esse bloqueio evita
publicar permalink comum como se fosse comissionado.
