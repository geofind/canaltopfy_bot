import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/app/app-shell";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();

  const [{ data: conversions }, { count: cliques }] = await Promise.all([
    supabase.from("conversions").select("commission_brl"),
    supabase
      .from("affiliate_clicks")
      .select("*", { count: "exact", head: true }),
  ]);

  const comissao = (conversions ?? []).reduce(
    (soma, c) => soma + (Number(c.commission_brl) || 0),
    0,
  );

  return (
    <AppShell comissao={comissao} cliques={cliques ?? 0}>
      {children}
    </AppShell>
  );
}
