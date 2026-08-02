-- ============================================================
-- Topfy Affiliate OS — SEED de 20 produtos REAIS para teste
-- (colar no SQL Editor do Supabase, depois de 0009/0010/0011)
-- Cria products prontos (READY) com URLs reais de ML/AliExpress
-- para testar: sugestões do dia, conteúdo por loja, captura de
-- imagem real (og:image) e publicação no Telegram.
-- AVISO: preços/comissões são estimativas para teste.
-- ============================================================

insert into products (
    organization_id, status, source_name, source_url, external_id,
    method, title, description, image_url, original_price_brl,
    discounted_price_brl, currency, discount_pct, commission_pct,
    commission_brl, affiliate_link_status, seller, category,
    rating, sales_count, confidence, score, score_breakdown, aviso
)
select
    (select id from organizations limit 1), v.status, v.source_name,
    v.source_url, v.external_id, 'MANUAL', v.title, v.description,
    v.image_url, v.original_price_brl, v.discounted_price_brl,
    'BRL', v.discount_pct, v.commission_pct,
    round(v.discounted_price_brl * v.commission_pct / 100, 2),
    'UNKNOWN', v.seller, v.category, v.rating, v.sales_count,
    'UNKNOWN', v.score,
    jsonb_build_object('price', 30, 'demand', 30, 'margin', 25, 'risk', 10),
    'Seed de teste — preço estimado, confirme na loja antes de publicar'
from (values
    -- -------- Mercado Livre --------
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-5162321538-smartwatch-w10-microwear-serie-10-nfc-chatgpt-bussola-2025-_JM',
     'MLB-5162321538', 'Smartwatch W10 Microwear Série 10 NFC ChatGPT Bússola 2025',
     'Smartwatch com chamadas via bluetooth, NFC, assistente por IA e bússola. Ideal para quem quer monitorar treino e receber notificações sem tirar o celular do bolso.',
     null, 189.90, 129.90, 32, 10, 'Microwear', 'Smartwatches', 4.8, 420, 92),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-4343860854-fire-stick-tv-4k-max-segunda-geraco-smart-lancamento-2023-_JM',
     'MLB-4343860854', 'Fire Stick TV 4K Max Segunda Geração Smart (Alexa)',
     'Streaming 4K com Alexa, Wi-Fi 6 e processador 40% mais rápido. Transforma qualquer TV em smart TV em segundos.',
     null, 549.90, 429.90, 22, 8, 'Amazon', 'Streaming', 4.9, 3100, 94),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-5751762426-minisforum-m1-pro-mini-pc-core-ultra-9-processador-285h16c-_JM',
     'MLB-5751762426', 'Minisforum M1 Pro Mini PC Core Ultra 9 285H 16C',
     'Mini PC com Intel Core Ultra 9, ideal para home office, edição e estação compacta. Potência de desktop em menos de 1 litro.',
     null, 8299.00, 6999.00, 16, 5, 'Minisforum', 'Computadores', 4.6, 85, 78),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-4306580024-placa-wireless-wi-fi-7-intel-be200-58-gbps-5800mbps-bt-54-_JM',
     'MLB-4306580024', 'Placa Wireless Wi-Fi 7 Intel BE200 5.8 Gbps + BT 5.4',
     'Placa PCIe/NGFF com Wi-Fi 7 de até 5.8 Gbps e Bluetooth 5.4. Upgrade definitivo de rede para o seu PC.',
     null, 179.90, 129.90, 28, 9, 'Intel', 'Redes', 4.7, 230, 88),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-4345618885-mouse-led-rgb-transparente-usb-24hz-bluetooth-aportex-_JM',
     'MLB-4345618885', 'Mouse LED RGB Transparente USB 2.4GHz Bluetooth',
     'Mouse com visual transparente e LED RGB, conexão sem fio dupla (USB + Bluetooth) e alta precisão. Estilo que combina com setups gamer e minimalistas.',
     null, 79.90, 49.90, 38, 10, 'Aportex', 'Periféricos', 4.5, 540, 90),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-5266413504-smart-touch-screen-tv-com-tela-21-polegadandroid-12-portatil-_JM',
     'MLB-5266413504', 'Smart Touch Screen TV 21 Polegadas Android 12 Portátil',
     'TV portátil touch de 21" com Android 12: rede de 4G/5G, Wi-Fi e bateria embutida. Assistir e navegar onde quiser.',
     null, 1899.00, 1499.00, 21, 7, 'Genérico', 'TVs', 4.4, 180, 82),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-5319012824-console-nintendo-switch-lite-32gb-azul-turquesa-standard-tela-55-_JM',
     'MLB-5319012824', 'Nintendo Switch Lite 32GB Azul Turquesa',
     'Console portátil da Nintendo com tela de 5,5", ideal para jogar no sofá ou na viagem. Garantia nacional e envio rápido.',
     null, 1499.00, 1199.00, 20, 8, 'Nintendo', 'Videogames', 4.9, 860, 95),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-4048093120-teclado-mecanico-gamer-mancer-shade-mk2-rainbow-s-huano-red-_JM',
     'MLB-4048093120', 'Teclado Mecânico Gamer Mancer Shade MK2 Rainbow S Huano Red',
     'Teclado mecânico com switches Huano Red, iluminação rainbow e construção robusta. Excelente custo-benefício para games e digitação.',
     null, 239.90, 169.90, 29, 10, 'Mancer', 'Periféricos', 4.6, 950, 91),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/xiaomi-smart-band-10-pink-amoled-172-1500-nits-bateria-de-21-dias-mais-de-150-esportes-nataco-5-atm/p/MLB52027865',
     'MLB52027865', 'Xiaomi Smart Band 10 Pink AMOLED 1.72" Bateria 21 dias',
     'Smart band com AMOLED de 1.72", 150+ modos de esporte, resistência 5 ATM e bateria de 21 dias. Monitora saúde o dia inteiro.',
     null, 499.90, 399.90, 20, 9, 'Xiaomi', 'Smartbands', 4.8, 720, 93),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/fone-de-ouvido-sem-fio-bluetooth-53/p/MLB35435077',
     'MLB35435077', 'Fone de Ouvido Sem Fio Bluetooth 5.3',
     'Fone TWS com Bluetooth 5.3, conexão estável e graves presentes. Compacto, confortável e com boa autonomia de bateria.',
     null, 149.90, 89.90, 40, 10, 'Genérico', 'Fones', 4.4, 1900, 89),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/relogio-xiaomi-mi-smart-band-7-cor-preta/p/MLB19174175',
     'MLB19174175', 'Relógio Xiaomi Mi Smart Band 7 Cor Preta',
     'Xiaomi Mi Band 7 com tela AMOLED 1.62", monitoramento de sono, estresse e 120+ modos esportivos. A clássica smart band.',
     null, 279.90, 199.90, 29, 9, 'Xiaomi', 'Smartbands', 4.7, 2400, 92),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/fone-de-ouvido-gamer-lenovo-gm2-pro-bluetooth-53-preto/p/MLB28757043',
     'MLB28757043', 'Fone de Ouvido Gamer Lenovo GM2 Pro Bluetooth 5.3',
     'Fone gamer com Bluetooth 5.3, baixa latência e microfone. Perfeito para jogar no celular ou no PC sem fios.',
     null, 179.90, 119.90, 33, 10, 'Lenovo', 'Fones', 4.5, 1300, 90),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/fone-de-ouvido-musical-p47-bt-com-reduco-de-ruido-dobravel/p/MLB2010102678',
     'MLB2010102678', 'Fone de Ouvido Musical P47 BT Redução de Ruído Dobrável',
     'Fone over-ear dobrável com Bluetooth, suporte a cartão SD e bateria de 400 mAh. Música o dia inteiro com conforto.',
     null, 129.90, 79.90, 38, 10, 'Genérico', 'Fones', 4.3, 810, 87),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-3861903613-fone-de-ouvido-sem-fio-jbl-tune-520bt-dobravel-cor-preto-_JM',
     'MLB-3861903613', 'Fone de Ouvido Sem Fio JBL Tune 520BT Dobrável Preto',
     'Fone over-ear da JBL com assinatura sonora Pure Bass, Bluetooth multiponto e 57h de bateria. Dobrável para levar junto.',
     null, 349.90, 249.90, 29, 8, 'JBL', 'Fones', 4.8, 680, 94),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-3823490483-fone-de-ouvido-wireless-bluetooth-51-c-microfone-elg-_JM',
     'MLB-3823490483', 'Fone de Ouvido Wireless Bluetooth 5.1 com Microfone ELG',
     'Fone sem fio com Bluetooth 5.1, microfone integrado e ótimo custo-benefício. Ideal para chamadas, aulas e música.',
     null, 99.90, 69.90, 30, 10, 'ELG', 'Fones', 4.3, 520, 86),
    ('READY', 'mercadolivre',
     'https://produto.mercadolivre.com.br/MLB-3890819371-fone-bt-52-microfone-estereo-_JM',
     'MLB-3890819371', 'Fone BT 5.2 Estéreo com Microfone',
     'Fone TWS Bluetooth 5.2 com som estéreo e microfone, leve e com estojo de recarga. Som portátil com boa autonomia.',
     null, 89.90, 59.90, 33, 10, 'Genérico', 'Fones', 4.2, 1100, 85),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/kit-projetor-hy300-android-wifi---caixa-de-som-bluetooth/up/MLBU3275368472',
     'MLBU3275368472', 'Kit Projetor HY300 Android WiFi + Caixa de Som Bluetooth',
     'Projetor Android com Wi-Fi e caixa de som Bluetooth. Cinema em casa sem complicação: conecte, ajuste e assista.',
     null, 459.90, 329.90, 28, 10, 'HY300', 'Projetores', 4.4, 410, 88),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/projetor-portatil-maxnova-bluetooth-wi-fi-full-hd-4k-mini-hdmi-usb-preto/p/MLB54008655',
     'MLB54008655', 'Projetor Portátil Maxnova Bluetooth Wi-Fi Full HD 4K',
     'Projetor mini Full HD com suporte 4K, Wi-Fi, Bluetooth, HDMI e USB. Portátil para jogar e assistir em qualquer lugar.',
     null, 399.90, 299.90, 25, 10, 'Maxnova', 'Projetores', 4.5, 330, 89),
    ('READY', 'mercadolivre',
     'https://www.mercadolivre.com.br/projetor-lcd-portatil-wifi-bluetooth-android-13-4k-full-hd-cor-preto-127220v/p/MLB43501608',
     'MLB43501608', 'Projetor LCD Portátil WiFi Bluetooth Android 13 4K Full HD',
     'Projetor com Android 13, Wi-Fi e Bluetooth, resolução Full HD com suporte 4K. Assista seus apps direto no projetor.',
     null, 599.90, 459.90, 23, 9, 'Genérico', 'Projetores', 4.3, 260, 87),
    -- -------- AliExpress --------
    ('READY', 'aliexpress',
     'https://www.aliexpress.com/item/1005004813846577.html',
     '1005004813846577', 'Smartwatch DT8 Ultra 2" Tela Grande',
     'Smartwatch esportivo com tela grande de 2", chamadas via bluetooth 5.0 e visual robusto. Excelente custo-benefício direto do AliExpress.',
     null, 349.90, 179.90, 49, 12, 'DTNO.1', 'Smartwatches', 4.6, 1500, 93),
    ('READY', 'aliexpress',
     'https://www.aliexpress.com/item/1005010420078087.html',
     '1005010420078087', 'Smart Watch Ultra Fino AMOLED 1.96" 360x360',
     'Smartwatch ultra fino com tela AMOLED 1.96" HD e lembretes de chamadas. Visual elegante para o dia a dia, vendido direto do AliExpress.',
     null, 289.90, 139.90, 52, 12, 'AliExpress Store', 'Smartwatches', 4.5, 980, 92)
) as v(
    status, source_name, source_url, external_id, title, description,
    image_url, original_price_brl, discounted_price_brl, discount_pct,
    commission_pct, seller, category, rating, sales_count, score
);

-- Zera o aviso do seed nos produtos READY (é só para pós-importação real)
update products
set aviso = null
where status = 'READY';

-- -------- Amazon --------
-- Teste do conector manual: os links já são o link de afiliado do usuário
-- (amzn.to), então affiliate_link é preenchido direto no seed pra o redirect
-- /r/<id> funcionar mesmo sem passar pelo worker. external_id/ASIN só é
-- resolvido quando o worker rodar o job product.import.
insert into products (
    organization_id, status, source_name, source_url, external_id,
    method, title, image_url, currency, affiliate_link,
    affiliate_link_status, seller, category, confidence, score,
    score_breakdown, aviso
)
select
    (select id from organizations limit 1), v.status, v.source_name,
    v.source_url, NULL, 'MANUAL', v.title, NULL, 'BRL', v.source_url,
    'UNKNOWN', v.seller, v.category, 'UNKNOWN', v.score,
    jsonb_build_object('price', 25, 'demand', 25, 'margin', 25, 'risk', 25),
    'Teste Amazon — confira título/preço na loja antes de publicar'
from (values
    ('READY', 'amazon',
     'https://amzn.to/4hKx5yk',
     'Oferta Amazon — teste de importação (amzn.to)',
     'Amazon', 'Destaques da Amazon', 70),
    ('READY', 'amazon',
     'https://amzn.to/45CQFoY',
     'Oferta Amazon — teste de importação (amzn.to)',
     'Amazon', 'Destaques da Amazon', 70)
) as v(
    status, source_name, source_url, title, seller, category, score
);
