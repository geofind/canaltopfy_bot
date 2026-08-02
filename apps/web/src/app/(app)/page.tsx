import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { connectMercadoLivre } from "@/lib/actions";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const STATUS_LABEL: Record<string, string> = {
  IMPORTED: "Importado",
  VALIDATING: "Validando",
  READY: "Pronto",
  CONTENT_GENERATING: "Gerando conteúdo",
  REVIEW_REQUIRED: "Revisão",
  APPROVED: "Aprovado",
  SCHEDULED: "Agendado",
  PUBLISHING: "Publicando",
  PUBLISHED: "Publicado",
  MONITORING: "Monitorando",
  SCALE: "Escalando",
  REWORK: "Revisar",
  ARCHIVED: "Arquivado",
  FAILED: "Falhou",
};

export default async function DashboardPage() {
  const supabase = await createClient();

  const [{ count: totalCampanhas }, { count: publicadas }, { count: cliques }] =
    await Promise.all([
      supabase.from("campaigns").select("*", { count: "exact", head: true }),
      supabase
        .from("campaigns")
        .select("*", { count: "exact", head: true })
        .eq("status", "PUBLISHED"),
      supabase
        .from("affiliate_clicks")
        .select("*", { count: "exact", head: true }),
    ]);

  const { data: recentes } = await supabase
    .from("campaigns")
    .select("id, title, status, created_at")
    .order("created_at", { ascending: false })
    .limit(5);

  const { data: mlCred } = await supabase
    .from("ml_credentials")
    .select("expires_at")
    .maybeSingle();
  const mlConectado = Boolean(mlCred);
  const mlExpirado =
    mlCred && mlCred.expires_at && new Date(mlCred.expires_at) <= new Date();

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <Link
          href="/campanhas/nova"
          className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Nova campanha
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Campanhas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{totalCampanhas ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Publicadas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{publicadas ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Cliques
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{cliques ?? 0}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mercado Livre</CardTitle>
          <CardDescription>
            Importação manual de produtos (automação é proibida pela
            plataforma). Conecte a conta para importar links com seu código
            de afiliado.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-4">
          {mlConectado ? (
            <Badge variant={mlExpirado ? "destructive" : "secondary"}>
              {mlExpirado ? "Conectado (token expirado)" : "Conectado"}
            </Badge>
          ) : (
            <Badge variant="outline">Não conectado</Badge>
          )}
          <form action={connectMercadoLivre}>
            <button
              type="submit"
              className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-4 text-sm font-medium transition-colors hover:bg-muted"
            >
              {mlConectado ? "Reconectar" : "Conectar"}
            </button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Campanhas recentes</h2>
        {!recentes || recentes.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              Nenhuma campanha ainda — crie a primeira colando a URL de um
              produto.
            </CardContent>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Título</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Criada em</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {recentes.map((c) => (
                  <tr
                    key={c.id}
                    className="transition-colors hover:bg-muted/50"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/campanhas/${c.id}`}
                        className="hover:underline"
                      >
                        {c.title || "Sem título"}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary">
                        {STATUS_LABEL[c.status] ?? c.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(c.created_at).toLocaleDateString("pt-BR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
