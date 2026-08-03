"""Topfy Affiliate OS — cadastro local de cupom (sem abrir o site).

Cadastra um cupom real (nunca inventado pela copy) na tabela coupon_codes
— o mesmo dado que content.py usa pra montar a linha "🎟️Use o cupom: ...".
Só usado localmente (Windows) — nunca roda no container de produção.
"""
from __future__ import annotations

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

LOJAS = ("aliexpress", "amazon", "mercadolivre")


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


def _listar_cupons(organization_id: str) -> list[dict]:
    return (db._get().table("coupon_codes").select("*")
            .eq("organization_id", organization_id).order("created_at").execute().data or [])


def main() -> None:
    organization_id = _escolher_organizacao()
    existentes = _listar_cupons(organization_id)
    if existentes:
        print("\nCupons já cadastrados:")
        for c in existentes:
            loja = c.get("source_name") or "qualquer loja"
            status = "ativo" if c["is_active"] else "inativo"
            print(f"  - {c['code']} ({loja}, {status})"
                  + (f" — {c['label']}" if c.get("label") else ""))
        print()

    codigo = _perguntar("Código do cupom (ex.: OFERTAMELI15)")
    if not codigo:
        print("Cupom vazio — cancelado.")
        return

    print("\nEsse cupom vale pra qual loja? Deixe em branco pra valer em qualquer uma.")
    print("Opções conhecidas: " + ", ".join(LOJAS))
    loja = _perguntar("Loja", "") or None

    rotulo = _perguntar("Rótulo/observação (opcional, ex.: 'Meli+' ou 'todas as contas')", "") or None

    db._get().table("coupon_codes").insert({
        "organization_id": organization_id,
        "source_name": loja,
        "code": codigo,
        "label": rotulo,
        "is_active": True,
    }).execute()

    print(f"\nCupom '{codigo}' cadastrado"
          + (f" para {loja}" if loja else " (vale pra qualquer loja)")
          + " — já entra nos próximos posts que tiverem esse produto/loja.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado.")
