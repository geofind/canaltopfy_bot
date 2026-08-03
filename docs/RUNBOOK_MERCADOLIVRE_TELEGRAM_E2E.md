# Runbook — Mercado Livre → Topfy → Telegram

Última validação ponta a ponta: **2 de agosto de 2026**.

## Resultado alcançado

O fluxo foi validado com duas ofertas reais:

1. O worker descobriu produtos pela API oficial do Mercado Livre.
2. O Hermes/Chrome gerou links oficiais no Link Builder do Mercado Livre.
3. A interface do Topfy recebeu o link `meli.la` e criou o job
   `mercadolivre.link.ready`.
4. O worker validou o link, gerou três copies, aprovou automaticamente a
   primeira copy válida e inseriu a campanha na fila.
5. A fila publicou foto, texto e CTA no Telegram.
6. A publicação, o `message_id` e a auditoria ficaram gravados no Supabase.
7. O CTA `/r/<publication_id>` registrou o clique e redirecionou para o link
   oficial `meli.la`.

Evidências do teste:

- Soundcore P30i: mensagem Telegram `28`, link `https://meli.la/1h1mSHu`.
- Samsung Galaxy Fit3: mensagem Telegram `29`, link
  `https://meli.la/2HaLMjn`.
- A segunda mensagem confirmou o envio da imagem real do produto.
- A suíte final terminou com **143 testes aprovados**.
- O build de produção do Next.js terminou sem erro.

> Os IDs e links acima são evidências históricas. Não devem ser reutilizados
> para outra campanha.

## Estado atual e limitação conhecida

Depois que um link oficial é entregue ao Topfy, o restante do fluxo funciona
sem aprovação humana.

A descoberta roda automaticamente a cada cinco minutos, mas a criação de um
novo link `meli.la` ainda depende de uma sessão autenticada do Mercado Livre
controlada pelo Hermes/Chrome. A API pública do Mercado Livre não oferece o
mesmo gerador de link do Link Builder. Não se deve marcar um produto como
`VERIFIED` sem passar pela ferramenta oficial.

Para operação autônoma por tempo indefinido, ainda é necessário executar o
Hermes/Chrome como um agente durável que:

1. consulte campanhas `READY` sem `affiliate_link`;
2. abra `https://www.mercadolivre.com.br/afiliados/linkbuilder`;
3. gere o link usando a etiqueta correta;
4. entregue o resultado ao Topfy;
5. registre falhas de sessão, CAPTCHA ou expiração sem inventar links.

## Arquitetura

```text
Mercado Livre API
        |
        v
products + campaigns (READY)
        |
        v
Hermes/Chrome -> Link Builder oficial -> meli.la
        |
        v
Topfy /campanhas/<id> -> job mercadolivre.link.ready
        |
        v
worker -> valida link -> score/copy -> aprovação -> queue_items
        |
        v
Telegram Bot API -> publications (PUBLISHED + external_id)
        |
        v
/r/<publication_id> -> affiliate_clicks -> meli.la
```

Arquivos principais:

- `apps/worker/connectors/mercadolivre.py`: descoberta e normalização oficial.
- `apps/worker/discovery.py`: deduplicação e criação de produto/campanha.
- `apps/worker/pipeline.py`: link, copy, aprovação, fila e publicação.
- `apps/worker/publishers/telegram.py`: Telegram Bot API.
- `apps/worker/main.py`: loop de jobs, descoberta e filas.
- `apps/web/src/lib/actions.ts`: criação do job pela interface.
- `apps/web/src/app/r/[id]/route.ts`: rastreamento e redirecionamento.
- `apps/web/src/app/og/card/[id]/route.tsx`: card de campanha agendada ou
  publicada.
- `apps/web/src/lib/supabase/admin.ts`: cliente exclusivo de servidor para as
  rotas públicas que precisam atravessar o RLS.

## Variáveis necessárias

Nunca versionar valores reais. Use `.env.example` como referência.

Worker local:

```dotenv
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
CANALTOPFY_PUBLIC_BASE_URL=https://seu-dominio.vercel.app

ML_DISCOVERY_ENABLED=true
ML_DISCOVERY_INTERVAL_MINUTES=5
ML_DISCOVERY_TERMS_PER_CYCLE=2

# Manter falso enquanto o pipeline antigo do AliExpress não tiver
# limite e deduplicação operacional comprovados.
AUTO_PIPELINE_ENABLED=false
```

Vercel, ambiente `Production`:

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
CANALTOPFY_PUBLIC_BASE_URL
```

`SUPABASE_SERVICE_ROLE_KEY` deve ser sensível, usada somente no servidor e
nunca importada por Client Components.

## Configuração da fila 24h

Para publicar sem pausa noturna:

- `queues.is_active = true`;
- `queues.interval_minutes = 5`;
- `queues.window_start = null`;
- `queues.window_end = null`;
- deve existir uma linha em `queue_groups` ligando a fila ao grupo ativo;
- `channel_groups.telegram_chat_id` deve conter o ID numérico real do grupo.

Se `window_start` e `window_end` estiverem preenchidos, o worker respeitará a
janela no horário de Brasília. No incidente encontrado, a fila estava em
`08:00–23:00` e por isso parava corretamente depois das 23h.

## Como publicar uma oferta

1. Confirme que produto e campanha estão `READY` e sem `affiliate_link`.
2. Abra o Link Builder autenticado.
3. Cole a `source_url` exata do produto.
4. Selecione a etiqueta de afiliado correta e gere o link curto.
5. Confira a confirmação visual e copie o `https://meli.la/...`.
6. Abra `/campanhas/<campaign_id>` no Topfy.
7. Cole o link em **Link criado pelo Hermes no Gerador oficial**.
8. Selecione a fila e use **Continuar e publicar automaticamente**.
9. Confirme a criação do job antes de sair da tela.

Payload esperado:

```json
{
  "type": "mercadolivre.link.ready",
  "payload": {
    "campaign_id": "<uuid>",
    "affiliate_url": "https://meli.la/...",
    "official_tool_confirmed": true,
    "auto_approve": true,
    "queue_id": "<uuid>",
    "agent": "hermes"
  }
}
```

## Falhas encontradas e soluções

### Auditoria rejeitava o fluxo do Hermes

Sintoma: `audit_log_actor_type_check` recusava `actor_type = agent`.

Causa: o schema aceita somente `user`, `worker` e `system`.

Solução: automações do Hermes passaram a registrar `actor_type="worker"`,
inclusive na aprovação automática. O teste correspondente foi atualizado.

### CTA redirecionava para a página inicial

Sintoma: `/r/<publication_id>` respondia `302` para `/` em vez de `meli.la`.

Causa: a requisição pública não possui cookies do dashboard; o cliente
Supabase baseado no usuário era bloqueado pelo RLS.

Solução:

- foi criado `createAdminClient()` em `src/lib/supabase/admin.ts`;
- a service role ficou restrita ao servidor;
- a rota consulta somente a publicação solicitada;
- o clique é gravado antes do redirecionamento.

Validação esperada:

```text
HTTP 302
Location: https://meli.la/...
```

### Card público retornava 404

Sintoma: `/og/card/<campaign_id>` respondia `Campanha não encontrada`.

Causa: o Telegram acessa sem sessão e a consulta era bloqueada pelo RLS. A
rota também exigia `public_page=true`, enquanto a campanha na fila ainda
estava `SCHEDULED`.

Solução: usar o cliente administrativo de servidor e aceitar somente campanhas
`SCHEDULED` ou `PUBLISHED`. Rascunhos continuam indisponíveis.

Validação esperada:

```text
HTTP 200
Content-Type: image/png
assinatura PNG: 89504e470d0a1a0a
dimensões: 1024x1024
```

### Fila não publicava depois das 23h

Causa: a janela estava configurada como `08:00–23:00`.

Solução: definir `window_start` e `window_end` como `null` para operação 24h.

### Pipeline antigo criava backlog em massa

Sintoma: oito campanhas do AliExpress eram criadas por ciclo, enquanto apenas
uma era enviada a cada cinco minutos. O teste encontrou 28 itens pendentes.

Solução operacional:

- `AUTO_PIPELINE_ENABLED=false`;
- os 28 itens daquele lote foram marcados `CANCELLED`, com motivo;
- a descoberta do Mercado Livre permaneceu ativa.

Não reativar esse modo antes de implementar limite por ciclo, deduplicação e
controle de tamanho da fila.

### Deploy local falhava com `EPERM` no Windows

Sintoma: `vercel build --prod` compilava, mas falhava ao criar um symlink em
`.vercel/output`.

Solução: usar build remoto:

```powershell
vercel deploy --prod --yes --force --archive=tgz
```

Foi criado `.vercelignore` na raiz para excluir `node_modules`, `.next`,
ambientes locais, logs e segredos.

## Iniciar e verificar o worker no Windows

Iniciar em segundo plano:

```powershell
Start-Process -FilePath "cmd.exe" `
  -ArgumentList "/c","apps\worker\run_worker.bat" `
  -WorkingDirectory "C:\caminho\Topfy_Affiliate_OS" `
  -WindowStyle Hidden
```

Confirmar o processo:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq "python.exe" -and
    $_.CommandLine -like "*_local_bootstrap.py*" }
```

Ver as últimas ocorrências:

```powershell
Get-Content apps\worker\worker.log -Tail 50
```

## Checklist ponta a ponta

Execute na ordem e pare na primeira falha:

- [ ] Worker está ativo e existe somente uma instância.
- [ ] Bot responde ao `getMe` sem expor o token.
- [ ] Grupo e fila estão ativos e ligados em `queue_groups`.
- [ ] Fila 24h possui `window_start/window_end = null`.
- [ ] Produto e campanha estão `READY`.
- [ ] Link foi gerado no Link Builder e começa com `https://meli.la/`.
- [ ] Job `mercadolivre.link.ready` terminou como `done`.
- [ ] Produto ficou com `affiliate_link_status = VERIFIED`.
- [ ] Uma copy ficou `APPROVED`.
- [ ] Campanha passou por `SCHEDULED` e terminou `PUBLISHED`.
- [ ] `queue_items.status = DONE`, sem `error`.
- [ ] `publications.status = PUBLISHED` e `external_id` tem o `message_id`.
- [ ] Telegram mostra foto, título, preços e CTA.
- [ ] `/r/<publication_id>` responde `302` para o `meli.la` correto.
- [ ] `affiliate_clicks` recebeu o clique de teste.
- [ ] Não existe duplicidade da campanha no mesmo `chat_id`.

## Testes de regressão

Worker:

```powershell
C:\Python314\python.exe -m unittest discover `
  -s apps\worker\tests -p "test_*.py"
```

Web:

```powershell
Set-Location apps\web
npm run build
```

Qualidade do diff:

```powershell
git diff --check
```

Antes de encerrar uma manutenção, consulte os logs da implantação Vercel e
confirme que não existem novos erros de runtime.

## Segurança e recuperação

- Nunca registrar tokens, service role, cookies ou códigos de autenticação.
- Nunca fabricar um link de afiliado alterando parâmetros manualmente.
- Publicar uma oferta de teste por vez antes de liberar um lote.
- Preservar a deduplicação por `campaign_id`, canal e `chat_id`.
- Em falhas, conferir `publications.error`, `queue_items.error` e `audit_log`
  antes de reenfileirar.
- Não apagar histórico de publicação para contornar deduplicação.
- Se o login do Mercado Livre expirar, reconectar a conta e a sessão do Link
  Builder; não tentar burlar CAPTCHA ou controles de acesso.

## Execução validada em 2026-08-02

Foi executado um lote real de nove ofertas do Mercado Livre usando a conta
autenticada e a etiqueta `canaltopfy` no Link Builder oficial. O procedimento
validado foi:

1. Confirmar que produto e campanha estavam `READY`, sem link, publicação,
   item de fila ou job ativo duplicado.
2. Enviar as nove URLs ao Link Builder em um único lote e exigir nove links
   curtos, únicos e no formato `https://meli.la/...`.
3. Criar os jobs `mercadolivre.link.ready` com `official_tool_confirmed=true`,
   `auto_approve=true`, agente `hermes` e a fila automática existente.
4. Acompanhar os jobs até `done` e confirmar a criação de nove itens da fila.
5. Confirmar a primeira publicação real no grupo
   `Canal Topfy - Tech Ofertas`, com `publications.status=PUBLISHED`,
   `queue_items.status=DONE` e `external_id=31`.
6. Manter os oito itens restantes em `PENDING`; o worker os publica em ordem,
   respeitando o intervalo configurado de cinco minutos.

Resultado: jobs 30 a 38 concluídos sem erro. Nenhuma alteração foi feita no
motor; o lote entrou exclusivamente pelo contrato já existente de jobs e fila.

## Grade automática de 6 horas validada em 2026-08-03

Para garantir seis horas de publicações no intervalo de cinco minutos, foi
montada uma grade com 72 itens pendentes. O procedimento usado foi:

1. Congelar temporariamente a fila com `is_active=false`.
2. Validar links, copies aprovadas e ausência de duplicidade antes de incluir
   cada campanha.
3. Distribuir os itens do Mercado Livre uniformemente entre os itens do
   AliExpress, preservando a ordem interna de cada fonte.
4. Gravar `scheduled_at` em passos exatos de cinco minutos.
5. Reativar a fila em bloco `finally`, inclusive se alguma validação falhar.

Na execução validada foram programadas 72 ofertas: 11 do Mercado Livre e 61 do
AliExpress. A primeira ficou marcada para 2026-08-03 00:15:49 e a última para
06:10:49, horário de Brasília. Os dez novos links do Mercado Livre foram
gerados em lote no Link Builder oficial, com a etiqueta `canaltopfy`, e os jobs
39 a 48 terminaram como `done`.

## Agente interno de reabastecimento

O worker possui um agente independente em `apps/worker/replenisher.py`. Ele é
executado em uma thread de background para que consultas às lojas nunca parem
o envio ao Telegram.

Configuração ativa recomendada:

```dotenv
REPLENISHER_ENABLED=true
REPLENISHER_MIN_ITEMS=84
REPLENISHER_TARGET_ITEMS=96
REPLENISHER_MAX_NEW_PER_CYCLE=4
REPLENISHER_INTERVAL_MINUTES=5
REPLENISHER_MIN_SCORE=35
REPLENISHER_ML_TARGET_PERCENT=20
```

Com intervalo de publicação de cinco minutos, 72 itens representam seis horas.
O agente dispara antes, em 84 itens (sete horas), e recompõe até 96 itens (oito
horas). Essa hora de margem absorve o tempo das APIs sem deixar a reserva cair
abaixo de seis horas. Ao atingir o gatilho, o agente reaproveita campanhas
aprovadas e ainda não publicadas; depois captura até quatro novas ofertas por
ciclo pela API oficial do AliExpress. Os itens são gravados depois da cauda da
fila, em passos de cinco minutos, e nunca reutilizam campanha já enfileirada ou
publicada. Assim, o estoque volta gradualmente a 72 sem rajadas nem bloqueio do
publicador.

Para Mercado Livre, o agente prioriza campanhas que já tenham link oficial
verificado. Novas URLs podem ser enviadas automaticamente a um bridge Hermes
compatível por `HERMES_LINK_AGENT_URL`. O bridge deve devolver
`official_tool_confirmed=true`; sem essa evidência, o worker rejeita o link.
Quando o bridge não está configurado, o agente registra a demanda para Hermes
e mantém a continuidade com AliExpress — jamais fabrica um link `meli.la`.

Depois de cada reposição, o agente mantém os mesmos horários de cinco minutos,
mas embaralha as campanhas futuras entre Mercado Livre e AliExpress. A fonte
minoritária é espalhada pela grade com espaços aleatórios controlados; isso
evita uma alternância mecânica e também evita concentrar todos os links de uma
loja num único bloco. Os dois próximos intervalos ficam protegidos durante o
embaralhamento para não interferir numa publicação já iniciada.

Dentro de cada loja, o sorteio é ponderado pelo quadrado do Topfy Score. Isso
faz ofertas com score alto aparecerem mais cedo com maior frequência, sem criar
uma classificação rígida: cada reposição ainda produz uma ordem diferente.

## Escopo ampliado de captura

O motor pesquisa promoções e oportunidades em smartphones, notebooks, fones e
headsets, smartwatches, monitores, TVs, consoles, controles, periféricos gamer,
placas de vídeo, SSDs, memórias, tablets, impressoras, redes, áudio, câmeras de
segurança, carregadores e power banks. Em eletrodomésticos inclui air fryers,
cafeteiras, aspiradores robô, liquidificadores, micro-ondas, geladeiras,
ventiladores, ar-condicionado, lavadoras e lava-e-seca.

No Mercado Livre, 30 categorias-folha confirmadas pela API oficial são rodadas
em grupos de oito. Isso impede que apenas as primeiras categorias da lista
sejam consultadas. Três termos adicionais giram a cada ciclo de cinco minutos;
desconto mínimo e consulta de preço vigente continuam ativos.

No AliExpress, os termos são embaralhados a cada ciclo do reabastecedor, para
que o limite de captura não favoreça sempre a primeira categoria. Score,
diversidade de categoria, preço confirmado, link verificado e deduplicação
continuam obrigatórios.

Cupons não são inferidos de palavras como “promoção”. Eles só entram na copy
quando existe código ativo e verificável em `coupon_codes`. As APIs de produto
usadas atualmente não entregam um código de cupom confiável; portanto o motor
captura a oportunidade de preço/desconto, mas não inventa cupom.

## Destaque de estoque local AliExpress

O metadado fica em `products.card_config.local_stock`, sem exigir uma nova
migração. O worker aceita somente duas evidências:

- `VERIFIED_API`: um campo explícito de país de envio/depósito da API contém
  `BR`, `BRA`, `Brasil` ou `Brazil`;
- `DECLARED_TITLE`: o título do vendedor declara expressamente “estoque no
  Brasil”, “envio do Brasil”, “envio nacional” ou frase equivalente.

No segundo caso, a copy e o card sempre mostram a ressalva “informado no
anúncio”. Prazo curto, frete rápido e estimativa de entrega não contam como
prova de estoque local. Sem uma das evidências acima, nenhum selo é exibido.

A Affiliate API consultada em produção (`product.query` e
`productdetail.get`) atualmente não devolve país do depósito nos resultados.
Os endpoints de logística exigem um token OAuth diferente das credenciais de
afiliado. Por isso, até esse acesso existir, a identificação automática real
acontece principalmente pela declaração explícita no título e fica claramente
rotulada como informação do anúncio.

Ao salvar tema ou borda no painel, o servidor mescla `card_config` em vez de
substituí-lo, preservando `local_stock`. Para replicar e validar, execute
`python -m unittest discover -s tests -p "test_*.py"` em `apps/worker` e
`npm run build` em `apps/web`.

## Diversidade consecutiva e destaque IMPERDÍVEL

A fila classifica cada produto em uma família estreita (`carregadores`,
`celulares`, `monitores`, `notebooks`, `fones`, etc.) usando categoria oficial
e palavras explícitas do título. O reabastecedor reorganiza os horários sem
perder itens, mantendo a mistura Mercado Livre/AliExpress e a preferência pelo
Topfy Score. Depois, o despacho faz a verificação final contra o último item
concluído: procura outro item vencido quando a família coincide e, se só houver
a mesma família disponível, aguarda em vez de publicar repetido.

“IMPERDÍVEL” é permitido somente em duas situações verificáveis:

- desconto real **maior que 50%**, calculado com preço original e preço atual
  confirmados (exatamente 50% não ativa);
- preço atual estritamente menor que todas as observações confirmadas do mesmo
  produto nos últimos 30 dias. Sem observação anterior, não existe alegação de
  menor preço.

O motivo acompanha o destaque na copy: “MAIS DE 50% DE DESCONTO CONFIRMADO” ou
“MENOR PREÇO CONFIRMADO DOS ÚLTIMOS 30 DIAS”. A evidência fica preservada em
`products.card_config.deal_highlight`, junto dos demais metadados do card.

## Dashboard operacional do administrador

A rota autenticada `/` é a sala de controle do motor. Ela consulta o Supabase
a cada abertura e apresenta reserva real da fila, cobertura em horas até o
último horário agendado, mix Mercado Livre/AliExpress, posts nas últimas 24h,
cupons ativos, maiores descontos recentes, jobs e eventos do worker. Pontos do
trilho e ofertas da lista são links para a campanha correspondente; as seções
também navegam para Sugestões, Filas, Campanhas e Sistema.

O worker registra `worker_heartbeat` no `audit_log` a cada cinco minutos. O
evento contém PID e a configuração efetivamente carregada: termos AliExpress,
termos e categorias Mercado Livre, tamanhos de rotação, intervalos, alvo da
reserva, score mínimo e guardas de qualidade. O dashboard considera o motor
online quando o último heartbeat tem no máximo 12 minutos; portanto não usa
PID, número de termos ou status fixos no código da interface.

As fontes e grãos principais são:

- `queue_items` (um item pendente por oferta agendada): reserva e trilho;
- `campaigns` + `products` (uma campanha por produto): achados e descontos;
- `publications` (uma linha por publicação/grupo): volume nas últimas 24h;
- `coupon_codes` (um código cadastrado): cupons ativos verificáveis;
- `jobs` e `audit_log`: execução, falhas, atividade e heartbeat.

## Hashtags pesquisáveis nas ofertas do Telegram

As copies novas recebem automaticamente até seis hashtags extraídas do título
real do produto. A regra prioriza tipo, compatibilidade e marca, normaliza para
minúsculas sem acentos e elimina repetições. Exemplo:

```text
Carregador sem fio Samsung 15W para celular iPhone 15
#carregador #semfio #samsung #celular #iphone
```

A aplicação acontece em dois pontos:

1. na geração da copy, para que o texto persistido já contenha as tags;
2. imediatamente antes do envio ao Telegram, cobrindo também ofertas antigas
   que já estavam na fila quando a regra foi adicionada.

`aplicar_hashtags_produto` é idempotente: reprocessar a mesma copy não duplica
tags. O limite de seis mantém a legenda legível e reduz o risco de ultrapassar
o limite de caption do Telegram.

## Paginação e retenção das campanhas

A rota `/campanhas` consulta somente dez registros por página usando `range`
do Supabase e navega por `?page=2`, `?page=3` etc. A contagem exibida vem da
mesma consulta, não de um número fixo.

A migração `0013_campaign_retention.sql` instala um trigger `AFTER INSERT` por
organização. Depois de serializar inserções simultâneas com advisory lock, ele
mantém as 200 campanhas mais recentes e apaga o excedente. As chaves
estrangeiras removem em cascata contents, publications e queue_items; clicks e
conversions históricos permanecem com `campaign_id` nulo. A função é
`SECURITY INVOKER` e não pode ser chamada diretamente por `anon` ou
`authenticated`.

## AliExpress em Conexões / Integrações

A rota `/integracoes` mostra o AliExpress com estado operacional real sem
enviar segredos ao frontend. O heartbeat do worker publica apenas booleanos
seguros indicando se a API e o tracking estão configurados. O site combina
esses sinais com a idade do heartbeat, número de termos, total de produtos
AliExpress e data da última captura consultados no Supabase.

As chaves `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET` e
`ALIEXPRESS_TRACKING_ID` continuam existindo somente no ambiente do worker;
seus valores nunca aparecem no HTML nem precisam ser copiados para a Vercel.

## Fluxo ao vivo da próxima publicação

O topo do dashboard renderiza um circuito com cinco etapas: Descoberta,
Score, Copy + link, Fila e Telegram. A primeira entrada `PENDING` de
`queue_items`, ordenada por `scheduled_at`, define a próxima campanha e fornece
título, fonte, preço, score, desconto e horário. Quando o horário ainda não
chegou, Fila é a etapa atual; quando já chegou, Telegram recebe o contorno
vermelho até o worker concluir o envio e a próxima entrada assumir o circuito.

O componente atualiza o Server Component a cada 30 segundos com
`router.refresh()`. Os conectores são SVGs com corrente animada por CSS; em
`prefers-reduced-motion`, a animação é desligada. Em telas estreitas, a esteira
mantém os cards legíveis por rolagem horizontal.

## Contagem regressiva da próxima postagem

O painel de **Autonomia de publicação** também mostra a contagem regressiva
`HH:MM:SS` da primeira entrada `PENDING` da fila. O horário absoluto é lido no
servidor a partir de `queue_items.scheduled_at`; somente o instante em
milissegundos, o rótulo do horário e o título são enviados ao componente
cliente, que recalcula o tempo restante a cada segundo.

Quando não existe item pendente, o painel mostra `--:--:--`. Quando o horário
agendado já chegou, a contagem permanece em `00:00:00` com o estado
**Publicando agora**, até o worker concluir o envio e a atualização automática
de 30 segundos carregar a campanha seguinte. Assim, o relógio nunca apresenta
tempo negativo nem cria uma segunda consulta à base.
