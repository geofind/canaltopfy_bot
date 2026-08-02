import Link from "next/link";
import { signOut } from "@/lib/actions";

export function NavBar() {
  return (
    <header className="border-b">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-semibold tracking-tight">
            Topfy<span className="text-muted-foreground"> Affiliate OS</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Dashboard
            </Link>
            <Link
              href="/campanhas"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Campanhas
            </Link>
            <Link
              href="/campanhas/nova"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Nova campanha
            </Link>
            <Link
              href="/sistema"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Sistema
            </Link>
            <Link
              href="/integracoes"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Integrações
            </Link>
          </nav>
        </div>
        <form action={signOut}>
          <button
            type="submit"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Sair
          </button>
        </form>
      </div>
    </header>
  );
}
