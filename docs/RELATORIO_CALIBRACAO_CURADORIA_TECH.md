# Calibração da curadoria tech

Data da análise: 3 de agosto de 2026.

## Objetivo

Usar padrões editoriais observáveis em dois canais públicos do Telegram para melhorar a descoberta e a ordenação de ofertas do Topfy, sem copiar textos, identidade, frequência ou distribuição de marketplaces desses canais.

Fontes analisadas:

- [Alerta Tech Brasil](https://web.telegram.org/a/#-1003702629762)
- [MINI OFERTAS & PROMOÇÕES](https://web.telegram.org/a/#-1002475846465)
- [Bench Promos - Cupons e Promoções](https://web.telegram.org/a/#-1001686905299)

No segundo canal, mensagens institucionais, divulgação do próprio canal, chamadas sem produto e publicações sem preço ou link reconhecido de marketplace foram excluídas da amostra.

## Amostra e resultados

Foram classificados 123 posts de produtos: 90 do primeiro canal e 33 ofertas válidas do segundo. No segundo canal, 50 das 83 mensagens visíveis foram descartadas pelo filtro editorial descrito acima.

| Sinal observado | Resultado combinado |
| --- | ---: |
| Games, consoles e controles | 38 (30,9%) |
| Componentes e montagem de PC | 37 (30,1%) |
| Monitores e TVs | 13 (10,6%) |
| Periféricos especializados | 13 (10,6%) |
| Mobile e smart | 3 (2,4%) |
| Outros produtos | 19 (15,4%) |
| Posts com cupom mencionado | 98 (79,7%) |
| Preço mediano observado | R$ 232 |
| Produtos abaixo de R$ 200 | 58 (47,2%) |

O segundo canal reforçou principalmente o nicho gamer: controles Hall Effect, 8BitDo, GameSir, Machenike, consoles portáteis, Nintendo Switch e PlayStation. O primeiro canal mostrou maior equilíbrio entre componentes de PC, games, monitores e periféricos.

### Terceiro canal e mescla redistribuída

No Bench Promos foram observadas 91 mensagens recentes. O filtro reteve 78 posts de produto e descartou 13 chamadas próprias, lives, vídeos, eventos e cupons sem produto. Depois de consolidar cores e republicações do mesmo modelo, restaram 56 famílias únicas:

| Família | Produtos únicos |
| --- | ---: |
| Áudio | 13 |
| Periféricos | 12 |
| Monitores e TVs | 11 |
| Notebooks | 10 |
| Games e controles | 8 |
| Celulares | 2 |

Essa amostra acrescenta ao perfil anterior uma curadoria mais forte de notebooks gamer, monitores de alta taxa de atualização, mouses, headsets e áudio especializado. Foram frequentes especificações concretas como sensor, polling rate, painel, resolução, taxa de atualização, GPU e memória, além da indicação de estoque no Brasil.

A mescla operacional passou a orientar a fila pelas seguintes proporções editoriais, sempre condicionadas à disponibilidade de ofertas aprovadas:

| Pilar editorial | Meta de ordenação |
| --- | ---: |
| Componentes de PC | 22% |
| Games e controles | 22% |
| Monitores e TVs | 15% |
| Notebooks | 15% |
| Periféricos | 10% |
| Áudio | 9% |
| Celulares | 5% |
| Outros tech | 2% |

O balanceamento acontece dentro de cada marketplace antes de as fontes serem intercaladas. Assim, o mix de Shopee, AliExpress e Mercado Livre definido no painel continua preservado.

## Diagnóstico do Topfy antes da calibração

Uma leitura textual aproximada da fila pendente, então com 95 campanhas, indicou concentração excessiva em periféricos genéricos e acessórios mobile. Games/controles e componentes de PC apareciam abaixo do padrão editorial observado nos grupos.

Essa comparação serve como direção editorial, não como meta matemática: a classificação da fila foi feita por termos no título e pode haver sobreposição entre famílias.

## Alterações aplicadas

1. Foi criado um perfil editorial explicável em `apps/worker/editorial_profile.py`.
2. O perfil prioriza, sem alterar o Topfy Score:
   - placas de vídeo, placas-mãe, processadores, memórias, SSDs e montagem de PC;
   - controles Hall Effect e marcas gamer recorrentes;
   - consoles e portáteis;
   - monitores de alta taxa de atualização e TVs 4K;
   - periféricos especializados, como teclados mecânicos, mouses gamer e microfones.
3. A descoberta do Mercado Livre e o pipeline geral passaram a ordenar candidatos pela afinidade editorial antes dos desempates por desconto e vendas.
4. A justificativa da afinidade é armazenada em `card_config.editorial_profile`, permitindo auditoria futura.
5. Os termos automáticos de Shopee, Mercado Livre e reabastecimento foram ampliados para refletir os nichos identificados.
6. As regras de diversidade ganharam famílias separadas para placas-mãe, processadores, memórias, placas de vídeo, fontes, refrigeração e gabinetes, evitando repetição visual na sequência.

## Proteções preservadas

- O mix de fontes configurado pelo usuário continua soberano; a calibração não força a proporção dos canais analisados.
- Score, desconto real, deduplicação, diversidade e validação de link continuam obrigatórios.
- Cupom só pode ser anunciado quando houver código verificado.
- A afinidade editorial não aprova uma oferta ruim e não substitui o Topfy Score.
- Conteúdo, copy e identidade dos canais não são copiados.

## Faixas iniciais para acompanhamento

Estas faixas são guardrails editoriais para observar durante 24–48 horas, não cotas rígidas:

- componentes de PC: 25–35%;
- games, consoles e controles: 20–30%;
- monitores e TVs: 10–15%;
- periféricos especializados: 10–20%;
- acessórios mobile genéricos: no máximo 15%;
- nunca publicar dois produtos seguidos da mesma família.

Antes de alterar pesos do Topfy Score, comparar cliques, conversões, receita por clique, rejeições manuais e velocidade de consumo da fila entre famílias.

## Validação técnica

- 225 testes automatizados aprovados.
- Testes novos cobrem prioridade, ordenação e preservação dos candidatos.
- Worker reiniciado e ativo após a alteração.
- Fila observada sendo despachada e reabastecida normalmente, em torno de 95–96 campanhas.

## Limitações

A amostra representa as mensagens recentes visíveis na sessão autenticada do Telegram. Ela não inclui métricas privadas de clique, venda ou conversão dos canais, e alguns posts podem ser republicações. Por isso, a calibração privilegia sinais editoriais consistentes, mas deve ser refinada com os resultados reais do Topfy.
