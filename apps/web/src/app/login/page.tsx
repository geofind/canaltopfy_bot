import Image from "next/image";
import { LoginForm } from "@/components/app/login-form";

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center bg-background px-4 py-16">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span className="grid h-14 w-14 place-items-center rounded-[10px] bg-card p-2 shadow-soft-sm">
            <Image
              src="/brand/logo-mark.png"
              alt="CanalTopfy"
              width={40}
              height={40}
              className="h-full w-full object-contain"
              priority
            />
          </span>
          <div className="space-y-1">
            <p className="eyebrow">Affiliate OS</p>
            <h1 className="font-display text-2xl font-bold tracking-tight">
              CanalTopfy
            </h1>
            <p className="text-sm text-muted-foreground">
              Entre para gerenciar suas campanhas
            </p>
          </div>
        </div>
        <div className="border border-border bg-card p-6 shadow-soft">
          <LoginForm />
        </div>
      </div>
    </main>
  );
}
