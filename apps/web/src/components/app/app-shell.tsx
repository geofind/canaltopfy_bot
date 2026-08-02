"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { signOut } from "@/lib/actions";

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/campanhas", label: "Campanhas" },
  { href: "/campanhas/nova", label: "Nova campanha" },
  { href: "/sistema", label: "Sistema" },
  { href: "/integracoes", label: "Integrações" },
];

interface AppShellProps {
  children: React.ReactNode;
  comissao: number;
  cliques: number;
}

export function AppShell({ children, comissao, cliques }: AppShellProps) {
  const pathname = usePathname();
  const [menuAberto, setMenuAberto] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="min-h-svh bg-background">
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex w-64 flex-col bg-sidebar text-sidebar-foreground transition-transform duration-200 ease-out",
          menuAberto ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex items-center gap-3 px-6 pb-7 pt-7">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[10px] bg-[#f5f5f5] p-1.5">
            <Image
              src="/brand/logo-mark.png"
              alt="CanalTopfy"
              width={28}
              height={28}
              className="h-full w-full object-contain"
            />
          </span>
          <span className="text-base font-extrabold leading-none tracking-tight">
            CanalTopfy
            <small className="mt-1 block text-[8px] font-bold tracking-[2px] text-sidebar-foreground/60">
              AFFILIATE OS
            </small>
          </span>
        </div>

        <nav className="flex-1 space-y-0.5 px-3" aria-label="Navegação principal">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMenuAberto(false)}
              className={cn(
                "block rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-white",
                isActive(link.href) &&
                  "bg-sidebar-accent text-white shadow-[inset_3px_0_var(--sidebar-primary)]",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="mx-3 mb-4 rounded-xl border border-sidebar-border bg-sidebar-accent p-4">
          <small className="block text-[9px] font-bold uppercase tracking-[1.5px] text-sidebar-foreground/60">
            Comissão estimada
          </small>
          <strong className="mt-1 block text-2xl text-white">
            R$ {comissao.toFixed(2)}
          </strong>
          <small className="mt-1 block text-[10px] text-sidebar-foreground/60">
            {cliques} clique{cliques === 1 ? "" : "s"} rastreados
          </small>
        </div>
      </div>

      <div
        className={cn(
          "fixed inset-0 z-20 bg-black/40 lg:hidden",
          menuAberto ? "block" : "hidden",
        )}
        onClick={() => setMenuAberto(false)}
        aria-hidden="true"
      />

      <div className="flex min-h-svh flex-col lg:pl-64">
        <header className="sticky top-0 z-10 flex h-[66px] items-center gap-3 border-b border-border bg-card px-4 sm:px-8">
          <button
            type="button"
            onClick={() => setMenuAberto(true)}
            className="grid h-9 w-9 place-items-center rounded-lg text-foreground hover:bg-muted lg:hidden"
            aria-label="Abrir menu"
          >
            <Menu className="size-5" />
          </button>
          <div className="flex items-center gap-2">
            <Image
              src="/brand/logo-mark.png"
              alt="CanalTopfy"
              width={32}
              height={32}
              className="h-8 w-auto"
            />
            <span className="hidden font-display text-[15px] font-bold text-foreground sm:block">
              CanalTopfy
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Link
              href="/campanhas/nova"
              className="inline-flex h-9 items-center gap-1.5 rounded-[9px] bg-primary px-4 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Plus className="size-4" />
              Nova campanha
            </Link>
            <form action={signOut}>
              <button
                type="submit"
                className="inline-flex h-9 items-center rounded-lg border border-border bg-card px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Sair
              </button>
            </form>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1480px] flex-1 px-4 py-7 sm:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
