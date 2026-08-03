"""Bootstrap só para rodar o worker localmente nesta máquina (Windows), via
Task Scheduler — nunca usado no container de produção (Dockerfile chama
`-m main` direto). Corrige um problema específico deste ambiente: o
OpenSSL do Python não confia no certificado raiz que uma ferramenta local
(antivírus/rede corporativa) injeta nas conexões HTTPS, mas o Windows
confia — por isso o navegador/curl funcionam normalmente e o Python (com o
bundle da certifi) não. `truststore` faz o ssl do Python usar a mesma
verificação de certificado do Windows, sem mexer no worker em si.
"""
from __future__ import annotations

import truststore

truststore.inject_into_ssl()

import runpy  # noqa: E402

runpy.run_module("main", run_name="__main__")
