# Claude no Chrome — revisar a vitrine CanalTopfy

Este roteiro orienta o Claude no Chrome a revisar a página pública criada em
`/ofertas`. Ele não autoriza publicação, alteração de anúncios, compra nem
coleta automática de dados da Amazon.

## Antes de começar

1. Inicie o projeto em outro terminal com `npm run dev --workspace apps/web`.
2. Confirme que a aplicação abriu em `http://localhost:3000`.
3. Se quiser validar cards reais, publique campanhas de teste no ambiente de
   desenvolvimento com título, categoria, imagem, preço e link já conferidos.
4. Abra o Chrome na página `http://localhost:3000/ofertas`.

## Prompt para colar no Claude no Chrome

```text
Revise a vitrine CanalTopfy que está aberta nesta aba. Você deve apenas
inspecionar e relatar; não altere arquivos, não publique campanhas, não clique
em links de compra e não faça login em lojas.

Valide em desktop e em uma largura móvel próxima de 390 px:
1. O logo CanalTopfy aparece nítido e o cabeçalho continua utilizável.
2. O hero “Achados que valem o clique” não corta texto nem cria rolagem
   horizontal.
3. Os números “ofertas publicadas” e “lojas no radar” correspondem ao conteúdo
   visível e não apresentam métricas inventadas.
4. O destaque mais recente mostra imagem, loja, categoria, título, preço e
   desconto somente quando os dados existem.
5. As categorias levam à seção correta e os cards mantêm alinhamento mesmo
   com títulos longos ou imagem ausente.
6. A navegação por Tab deixa foco visível em logo, botões, categorias e cards.
7. Os avisos de link de afiliado e de variação de preço/estoque estão visíveis.
8. O console não apresenta erros e as requisições principais não falham.

Entregue um relatório curto em português com: “Aprovado”, “Problemas” e
“Correções sugeridas”. Para cada problema, informe viewport, elemento, efeito
observado e uma correção objetiva. Não diga que preço, desconto, ranking ou
comissão foi verificado se isso não estiver demonstrado na interface.
```

## Segunda passagem, com uma oferta

Abra um card da vitrine e peça ao Claude:

```text
Revise agora a página individual desta oferta. Não prossiga para a loja.
Confirme que os dados exibidos coincidem com o card anterior, que o botão “Ver
oferta na loja” tem destino rastreado em /r/<id> quando há publicação, que o
disclaimer de afiliado está legível e que não há alegações sem fonte. Volte à
vitrine e confirme que o retorno preserva uma navegação compreensível.
```

## Referências estudadas

- Amazon Brasil — “Como encontrar ofertas para seus seguidores”: prioriza
  filtros por desconto, Prime, departamento, preço e avaliação; recomenda
  observar categorias relevantes para o público e páginas atualizadas de
  favoritos, produtos em alta e mais vendidos.
- Amazon Brasil — “Como criar links de Associado”: exige transparência sobre a
  relação de afiliado, uso do Link pelo App ou Site Stripe e recomenda IDs de
  rastreamento separados para analisar canais e campanhas.
- Amazon Brasil — “Mais Vendidos”: organiza itens por departamento, mostra
  posição, avaliação e preço, e informa que as listas são atualizadas com
  frequência.

Na vitrine CanalTopfy, esses padrões foram adaptados à marca e ao banco do
produto. “Destaque do radar” significa apenas a campanha publicada mais recente;
não significa “mais vendido”.
