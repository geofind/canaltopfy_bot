import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

const JOB_STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  running: "Em execução",
  done: "Concluído",
  failed: "Falhou",
  cancelled: "Cancelado",
};

export default async function SystemPage() {
  const supabase = await createClient();

  const [{ data: jobs }, { data: events }] = await Promise.all([
    supabase
      .from("jobs")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(30),
    supabase
      .from("audit_log")
      .select("*")
      .eq("actor_type", "worker")
      .order("created_at", { ascending: false })
      .limit(20),
  ]);

  const pending = jobs?.filter((j) => j.status === "pending").length ?? 0;
  const running = jobs?.filter((j) => j.status === "running").length ?? 0;
  const failed = jobs?.filter((j) => j.status === "failed").length ?? 0;
  const done = jobs?.filter((j) => j.status === "done").length ?? 0;

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Sistema</h1>
        <p className="text-sm text-muted-foreground">
          Saúde do worker (fila de jobs) — o worker consome a fila do banco
          a cada 5s quando está rodando.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Pendentes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{pending}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Em execução
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{running}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Concluídos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{done}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Falhas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{failed}</p>
          </CardContent>
        </Card>
      </div>

      {failed > 0 && (
        <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm">
          <p className="font-medium text-destructive">
            {failed} job(s) falhou — verifique a lista abaixo e o log do
            worker (`python -m main` em apps/worker).
          </p>
        </div>
      )}

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Jobs recentes</h2>
        {!jobs || jobs.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              Nenhum job ainda — crie uma campanha para enfileirar o
              processamento.
            </CardContent>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Tipo</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Criado</th>
                  <th className="px-4 py-3 font-medium">Erro</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">{job.type}</td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={
                          job.status === "failed" ? "destructive" : "secondary"
                        }
                      >
                        {JOB_STATUS_LABEL[job.status] ?? job.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(job.created_at).toLocaleString("pt-BR")}
                    </td>
                    <td className="max-w-xs truncate px-4 py-3 text-destructive">
                      {job.error ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Atividade do worker</h2>
        {!events || events.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              O worker ainda não registrou eventos — ele deve estar parado.
              Suba em apps/worker com `python -m main`.
            </CardContent>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Quando</th>
                  <th className="px-4 py-3 font-medium">Ação</th>
                  <th className="px-4 py-3 font-medium">Entidade</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {events.map((event) => (
                  <tr key={event.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">
                      {new Date(event.created_at).toLocaleString("pt-BR")}
                    </td>
                    <td className="px-4 py-3">{event.action}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {event.entity_type}: {event.entity_id}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Dúvidas sobre a fila? Veja <Link href="/campanhas" className="underline">Campanhas</Link> ou o{" "}
          <Link href="/integracoes" className="underline">estado das integrações</Link>.
        </p>
      </div>
    </div>
  );
}
