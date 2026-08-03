"""Topfy Affiliate OS — configuração local de fila (sem abrir o site).

Cria ou edita uma fila (queues) por terminal: nome, intervalo em minutos,
janela de horário opcional (24h se em branco) e grupos de destino. Mesma
tabela que a tela /filas do site edita — este script é só um atalho local,
não substitui a UI (validações e RLS continuam as mesmas).

Só usado localmente (Windows) — nunca roda no container de produção.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import truststore

truststore.inject_into_ssl()

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

import db  # noqa: E402

HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _perguntar(rotulo: str, padrao: str = "") -> str:
    sufixo = f" [{padrao}]" if padrao else ""
    valor = input(f"{rotulo}{sufixo}: ").strip()
    return valor or padrao


def _escolher_organizacao() -> str:
    orgs = db._get().table("organizations").select("id, name").execute().data or []
    if not orgs:
        print("Nenhuma organização encontrada — crie uma conta pelo site primeiro.")
        sys.exit(1)
    if len(orgs) == 1:
        return orgs[0]["id"]
    print("Mais de uma organização encontrada:")
    for i, org in enumerate(orgs, 1):
        print(f"  {i}. {org['name']} ({org['id']})")
    escolha = int(_perguntar("Qual organização (número)", "1")) - 1
    return orgs[escolha]["id"]


def _listar_grupos(organization_id: str) -> list[dict]:
    grupos = (db._get().table("channel_groups").select("id, name, is_active")
              .eq("organization_id", organization_id).order("name").execute().data or [])
    if not grupos:
        print("Nenhum grupo cadastrado — cadastre um em /grupos no site primeiro.")
        sys.exit(1)
    return grupos


def _listar_filas(organization_id: str) -> list[dict]:
    return (db._get().table("queues").select("*")
            .eq("organization_id", organization_id).order("name").execute().data or [])


def _validar_hora(valor: str, rotulo: str) -> str | None:
    if not valor:
        return None
    if not HORA_RE.match(valor):
        print(f"{rotulo} inválido — use HH:MM (ex.: 09:00). Tente de novo.")
        raise ValueError
    return valor


def main() -> None:
    organization_id = _escolher_organizacao()
    grupos = _listar_grupos(organization_id)
    filas = _listar_filas(organization_id)

    print("\nGrupos de destino cadastrados:")
    for i, g in enumerate(grupos, 1):
        status = "ativo" if g["is_active"] else "inativo"
        print(f"  {i}. {g['name']} ({status})")

    fila_editar = None
    if filas:
        print("\nFilas existentes:")
        for i, f in enumerate(filas, 1):
            janela = (f"{f['window_start']}–{f['window_end']}"
                      if f.get("window_start") else "24h")
            print(f"  {i}. {f['name']} — {f['interval_minutes']}min, "
                  f"{janela}, {'ativa' if f['is_active'] else 'inativa'}")
        escolha = _perguntar(
            "Editar fila existente? Número, ou Enter pra criar uma nova", "")
        if escolha:
            fila_editar = filas[int(escolha) - 1]

    nome = _perguntar("Nome da fila", fila_editar["name"] if fila_editar else "Ofertas 24h")
    intervalo_padrao = str(fila_editar["interval_minutes"]) if fila_editar else "5"
    while True:
        intervalo_txt = _perguntar("Intervalo entre envios em minutos (1–240)",
                                   intervalo_padrao)
        try:
            intervalo = int(intervalo_txt)
            if not (1 <= intervalo <= 240):
                raise ValueError
            break
        except ValueError:
            print("Precisa ser um número entre 1 e 240. Tente de novo.")

    print("\nJanela de horário: deixe as duas em branco pra postar 24h sem parar.")
    janela_padrao_ini = fila_editar.get("window_start", "") if fila_editar else ""
    janela_padrao_fim = fila_editar.get("window_end", "") if fila_editar else ""
    while True:
        try:
            inicio = _validar_hora(
                _perguntar("Início da janela (HH:MM, ou Enter p/ 24h)",
                          janela_padrao_ini or ""), "Início")
            fim = _validar_hora(
                _perguntar("Fim da janela (HH:MM, ou Enter p/ 24h)",
                          janela_padrao_fim or ""), "Fim")
            if (inicio and not fim) or (fim and not inicio):
                print("Preencha início E fim, ou deixe os dois em branco. Tente de novo.")
                continue
            break
        except ValueError:
            continue

    print("\nQuais grupos recebem essa fila? (números separados por vírgula, ex.: 1,2)")
    indices = _perguntar("Grupos", "1").split(",")
    grupo_ids = [grupos[int(i.strip()) - 1]["id"] for i in indices if i.strip()]

    ativa_txt = _perguntar("Fila ativa? (s/n)", "s").lower()
    ativa = ativa_txt.startswith("s")

    payload = {
        "organization_id": organization_id,
        "name": nome,
        "interval_minutes": intervalo,
        "window_start": inicio,
        "window_end": fim,
        "is_active": ativa,
    }

    if fila_editar:
        queue_id = fila_editar["id"]
        db._get().table("queues").update(payload).eq("id", queue_id).execute()
        db._get().table("queue_groups").delete().eq("queue_id", queue_id).execute()
    else:
        resp = db._get().table("queues").insert(payload).select("id").execute()
        queue_id = resp.data[0]["id"]

    if grupo_ids:
        linhas = [{"queue_id": queue_id, "group_id": gid} for gid in grupo_ids]
        db._get().table("queue_groups").insert(linhas).execute()

    print(f"\nFila '{nome}' salva — {intervalo}min, "
          f"{'24h' if not inicio else f'{inicio}–{fim}'}, "
          f"{'ativa' if ativa else 'inativa'}, {len(grupo_ids)} grupo(s).")
    print("Lembrete: fila só publica quem já foi aprovado e adicionado a ela "
          "(via campanha → 'Adicionar à fila', ou rodando este script de novo).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado.")
