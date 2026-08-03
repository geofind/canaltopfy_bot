# Gerenciamento editorial da fila

## Objetivo

Permitir que a equipe controle pelo painel o mix de marketplaces e a ordem
real das próximas publicações, sem editar preço, score, imagem ou link afiliado.

## O que foi implementado

- Mix configurável por fila para Shopee, AliExpress e Mercado Livre; a soma deve
  ser exatamente 100%.
- Lista de itens `PENDING` numerada em ordem de publicação, limitada a 200 itens.
- Reordenação por arrastar e soltar e por botões de subir/descer.
- Edição restrita a `campaigns.title` e `contents.copy_text`.
- Remoção não destrutiva: o vínculo da fila vira `CANCELLED`, mas a campanha
  continua disponível em Campanhas.
- Proteção da ordem manual: após uma reordenação, o worker deixa de embaralhar
  a fila até o usuário escolher **Usar ordem automática**.
- Horário efetivo calculado com o último despacho, o horário salvo, a posição
  no ranking e o intervalo da fila. Assim, itens antigos nunca aparecem com um
  horário já vencido: 1º é a próxima janela, 2º é a janela seguinte e assim por
  diante.

## Banco de dados

As migrations `0014_queue_editor_controls.sql` e
`0015_queue_manual_order_lock.sql` adicionam os percentuais, validam a soma em
100%, criam a RPC atômica `reorder_queue_items` e armazenam o modo manual. A RPC
usa `security invoker`, valida a organização autenticada, bloqueia os itens
pendentes durante a troca e exige que a lista enviada corresponda à fila atual.

## Aplicação web

- Página: `apps/web/src/app/(app)/filas/page.tsx`
- Editor: `apps/web/src/components/app/queue-editor.tsx`
- Ações autenticadas: `apps/web/src/lib/actions.ts`

O editor faz atualização otimista da ordem e restaura o estado anterior se o
banco informar que a fila mudou durante a operação.

## Worker

`apps/worker/replenisher.py` lê os percentuais salvos no banco em cada ciclo.
As variáveis de ambiente permanecem como fallback. Quando
`manual_order_locked=true`, a etapa de embaralhamento retorna sem alterar os
horários; captura, score, deduplicação e publicação continuam funcionando.

## Como replicar

1. Aplicar as migrations 0014 e 0015 no Supabase.
2. Publicar o app web na Vercel.
3. Reiniciar o worker para carregar a leitura do mix e a proteção manual.
4. Abrir `/filas`, salvar um mix cuja soma seja 100% e conferir a mensagem de
   sucesso.
5. Abrir a edição de um cartão e confirmar que só título e descrição aparecem.
6. Mover um item e confirmar o selo **Ordem manual protegida**.
7. Se desejar devolver o controle ao score/mix automático, clicar em
   **Usar ordem automática**.

## Verificações executadas em 03/08/2026

- Build de produção do Next.js aprovado.
- 206 testes do worker aprovados.
- Migrations aplicadas no projeto Supabase de produção.
- Mix 50/20/30 salvo pela interface publicada.
- Página `/filas` verificada com 95 campanhas numeradas e controles de edição,
  remoção e reordenação visíveis.
- Publicações do Telegram confirmadas em intervalos recentes de cinco minutos.
