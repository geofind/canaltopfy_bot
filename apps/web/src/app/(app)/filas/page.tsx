import { createClient } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { QueueForm } from "@/components/app/divulgacao-forms";
import { toggleQueue, deleteQueue } from "@/lib/actions";

export const dynamic = "force-dynamic";

const ITEM_STATUS_LABEL: Record<string, string> = {
  PENDING: "Pendente",
  DISPATCHED: "Despachando",
  DONE: "Concluído",
  CANCELLED: "Cancelado",
};

export default async function FilasPage() {
  const supabase = await createClient();

  const [{ data: filas }, { data: grupos }, { data: itens }] = await Promise.all([
    supabase.from("queues").select("*").order("created_at"),
    supabase.from("channel_groups").select("id, name").order("name"),
    supabase
      .from("queue_items")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(20),
  ]);

  const { data: vinculos } = await supabase
    .from("queue_groups")
    .select("queue_id, group_id");

  const gruposPorId = new Map((grupos ?? []).map((g) => [g.id, g.name]));

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <p className="eyebrow">Divulgação</p>
        <h1 className="text-2xl font-semibold tracking-tight">Filas</h1>
        <p className="text-sm text-muted-foreground">
          Sequências de ofertas enviadas no piloto automático: o worker publica
          um item por vez, respeitando o intervalo e a janela diária, para
          todos os grupos da fila.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <h2 className="text-lg font-semibold">Filas ativas</h2>
          {!filas || filas.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                Nenhuma fila ainda — crie a primeira ao lado e adicione ofertas
                pela página da campanha.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {filas.map((fila) => {
                const gruposDaFila = (vinculos ?? [])
                  .filter((v) => v.queue_id === fila.id)
                  .map((v) => gruposPorId.get(v.group_id) ?? v.group_id);
                return (
                  <Card key={fila.id}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0">
                      <div>
                        <CardTitle className="text-sm">{fila.name}</CardTitle>
                        <p className="mt-1 text-xs text-muted-foreground">
                          A cada {fila.interval_minutes} min
                          {fila.window_start && fila.window_end
                            ? ` · janela ${fila.window_start}–${fila.window_end}`
                            : ""}
                          {gruposDaFila.length > 0
                            ? ` · grupos: ${gruposDaFila.join(", ")}`
                            : " · sem grupos"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <form
                          action={toggleQueue.bind(null, fila.id, !fila.is_active)}
                        >
                          <button
                            type="submit"
                            className="rounded-md border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                          >
                            {fila.is_active ? "Pausar" : "Ativar"}
                          </button>
                        </form>
                        <form action={deleteQueue.bind(null, fila.id)}>
                          <button
                            type="submit"
                            className="rounded-md border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                          >
                            Remover
                          </button>
                        </form>
                      </div>
                    </CardHeader>
                    <CardContent className="border-t pt-3">
                      <Badge variant={fila.is_active ? "default" : "secondary"}>
                        {fila.is_active ? "Ativa" : "Pausada"}
                      </Badge>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Itens recentes</h2>
            {!itens || itens.length === 0 ? (
              <Card>
                <CardContent className="py-10 text-center text-sm text-muted-foreground">
                Nada na fila ainda — use &quot;Adicionar à fila&quot; na página da
                campanha.
                </CardContent>
              </Card>
            ) : (
              <div className="overflow-hidden rounded-md border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Campanha</th>
                      <th className="px-4 py-3 font-medium">Programado</th>
                      <th className="px-4 py-3 font-medium">Tentativas</th>
                      <th className="px-4 py-3 font-medium">Erro</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {itens.map((item) => (
                      <tr key={item.id} className="hover:bg-muted/50">
                        <td className="px-4 py-3">
                          <Badge
                            variant={
                              item.status === "DONE"
                                ? "default"
                                : item.status === "CANCELLED"
                                  ? "destructive"
                                  : "secondary"
                            }
                          >
                            {ITEM_STATUS_LABEL[item.status] ?? item.status}
                          </Badge>
                        </td>
                        <td className="max-w-[220px] truncate px-4 py-3">
                          {item.campaign_id.slice(0, 8)}…
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {new Date(item.scheduled_at).toLocaleString("pt-BR")}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {item.attempts}
                        </td>
                        <td className="max-w-[220px] truncate px-4 py-3 text-destructive">
                          {item.error ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Nova fila</CardTitle>
            </CardHeader>
            <CardContent>
              <QueueForm
                grupos={(grupos ?? []).map((g) => ({
                  id: g.id,
                  name: g.name,
                  telegram_chat_id: "",
                }))}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Como funciona</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                1. Crie a fila com os grupos de destino.
              </p>
              <p>
              2. Adicione ofertas pela página da campanha (botão &quot;Adicionar à
              fila&quot;).
              </p>
              <p>
                3. O worker despacha 1 item por fila a cada intervalo, dentro
                da janela diária, para todos os grupos da fila.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
