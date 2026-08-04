import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

type NavLink = readonly [href: string, label: string];

interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description?: string;
  statusTone?: "ok" | "warn" | "none";
  nav?: readonly NavLink[];
  right?: ReactNode;
  backHref?: string;
  backLabel?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  statusTone = "none",
  nav,
  right,
  backHref,
  backLabel = "Voltar",
}: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
      <div className="max-w-3xl">
        {backHref && (
          <Link
            href={backHref}
            className="mb-3 inline-block text-sm text-muted-foreground hover:underline"
          >
            ← {backLabel}
          </Link>
        )}
        <div className="flex items-center gap-2">
          {statusTone !== "none" && (
            <span
              className={cn(
                "size-2.5 rounded-full",
                statusTone === "ok"
                  ? "bg-emerald-500 shadow-[0_0_0_5px_rgba(16,185,129,.12)]"
                  : "bg-amber-500",
              )}
            />
          )}
          <p className="eyebrow">{eyebrow}</p>
        </div>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-[-0.035em] sm:text-5xl">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {nav && (
        <nav
          aria-label={`Seções de ${title}`}
          className="flex flex-wrap gap-2 rounded-xl border bg-white p-1.5 shadow-soft-sm"
        >
          {nav.map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="rounded-lg px-3 py-2 text-xs font-bold text-muted-foreground transition-colors hover:bg-[#1F2837] hover:text-white focus-visible:ring-2 focus-visible:ring-primary"
            >
              {label}
            </a>
          ))}
        </nav>
      )}
      {right && <div className="shrink-0">{right}</div>}
    </header>
  );
}