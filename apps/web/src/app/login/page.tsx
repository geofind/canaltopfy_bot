import { LoginForm } from "@/components/app/login-form";

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-1 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Topfy</h1>
          <p className="text-sm text-muted-foreground">
            Affiliate OS — entre para gerenciar suas campanhas
          </p>
        </div>
        <LoginForm />
      </div>
    </main>
  );
}
