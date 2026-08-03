# Hermes: Mercado Livre → Telegram

Fluxo assistido no portal do Mercado Livre e automático dentro da Topfy.
O Hermes opera apenas a etapa para a qual não existe API pública documentada:
criar o link no Gerador oficial. Depois disso não há aprovação humana.

## Pipeline

```text
API oficial ML (a cada 5 min)
  → produto + imagem + preço no Supabase
  → campanha READY, sem publicação
  → Hermes abre o Link Builder oficial
  → gera o meli.la com a etiqueta canaltopfy
  → entrega o link na campanha Topfy
  → worker valida domínio e registra evidência
  → calcula Topfy Score
  → gera 3 copies com fatos reais
  → aprova automaticamente a primeira copy válida
  → adiciona à fila escolhida
  → Telegram sendPhoto + caption HTML
  → registra message_id, auditoria e cliques
```

## Instrução para o Hermes / Claude Chrome

Use este texto como tarefa recorrente do agente:

> A cada ciclo, abra a Topfy e procure campanhas do Mercado Livre em estado
> Pronto/READY e sem link afiliado. Para cada campanha, leia a URL de origem
> do produto e abra `https://www.mercadolivre.com.br/afiliados/linkbuilder`
> na sessão autenticada. Insira as URLs, uma por linha, mantenha a etiqueta
> `canaltopfy`, clique em Gerar e capture o link curto `https://meli.la/...`
> devolvido para cada produto. Volte à campanha correspondente na Topfy,
> preencha “Link criado pelo Hermes no Gerador oficial”, escolha a fila
> automática do Telegram e clique em “Continuar e publicar automaticamente”.
> Confirme que a Topfy mostrou “Link entregue”. Não edite preço, título,
> cupom ou imagem manualmente. Não repita campanhas que já tenham link ou
> publicação. Se houver login expirado, CAPTCHA, bloqueio do portal, link sem
> correspondência ou erro de validação, pare esse item, registre o motivo e
> passe ao próximo sem tentar contornar o bloqueio.

## Estados e garantias

| Estado | Responsável | Próximo passo |
|---|---|---|
| `READY`, link vazio | coletor | Hermes gera o link oficial |
| job `mercadolivre.link.ready` | Topfy | worker valida e gera conteúdo |
| `APPROVED` | agente | inserção automática na fila |
| `SCHEDULED` | fila | aguarda janela/intervalo |
| `PUBLISHED` | Telegram | registra `message_id` e inicia métricas |
| `FAILED`/`CANCELLED` | worker | auditoria e até 3 tentativas |

O link só é marcado como `VERIFIED` quando o job registra que veio do Link
Builder oficial. URLs fora de HTTPS e dos domínios `meli.la`,
`mercadolivre.com.br` ou `mercadolibre.com.br` são recusadas. A publicação é
deduplicada por campanha e grupo do Telegram.

## Operação 24 horas

No worker:

```env
ML_DISCOVERY_ENABLED=true
ML_DISCOVERY_ORG_ID=<uuid-da-organizacao>
ML_DISCOVERY_TERMOS=air fryer,smartphone,notebook,ferramentas
ML_DISCOVERY_MIN_DISCOUNT=10
ML_DISCOVERY_MAX_NOVOS=10
ML_DISCOVERY_INTERVAL_MINUTES=5
CANALTOPFY_PUBLIC_BASE_URL=https://web-lac-seven-pg17eswj7d.vercel.app
```

Também são necessários `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`TELEGRAM_BOT_TOKEN`, uma fila ativa vinculada ao grupo e apenas **uma réplica**
do worker atual. O Chrome autenticado com Hermes precisa permanecer em uma
máquina ativa; Vercel hospeda a web, mas não mantém uma sessão de navegador.

## Formato do post

- foto do produto ou card Topfy construído a partir dela;
- gancho curto e específico;
- nome do produto;
- preço original somente quando confirmado e maior que o atual;
- preço atual e cupom somente quando vierem do banco;
- CTA rastreável `/r/<publication_id>` que redireciona ao `meli.la`;
- aviso de afiliado;
- publicação via `sendPhoto`, com fallback seguro para texto sem preview.

