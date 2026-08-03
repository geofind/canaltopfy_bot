import { createClient } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { QueueForm } from "@/components/app/divulgacao-forms";
import { QueueEditor, type QueueEditorItem } from "@/components/app/queue-editor";
import { toggleQueue, deleteQueue } from "@/lib/actions";

export const dynamic = "force-dynamic";

type ProductRow = {
  source_name: string | null;
  category: string | null;
  score: number | null;
  discounted_price_brl: number | null;
  discount_pct: number | null;
};

type CampaignRow = {
  id: string;
  title: string | null;
  product: ProductRow | ProductRow[] | null;
};

type ContentRow = { id: string; copy_text: string };

type QueueItemRow = {
  id: string;
  queue_id: string;
  campaign_id: string;
  content_id: string | null;
  scheduled_at: string;
  campaign: CampaignRow | CampaignRow[] | null;
  content: ContentRow | ContentRow[] | null;
};

type DispatchRow = {
  queue_id: string;
  dispatched_at: string;
};

function one<T>(value: T | T[] | null | undefined): T | null {
  return Array.isArray(value) ? value[0] ?? null : value ?? null;
}

export default async function FilasPage() {
  const supabase = await createClient();

  const [
    { data: filas },
    { data: grupos },
    { data: itens },
    { data: vinculos },
    { data: despachos },
  ] = await Promise.all([
    supabase.from("queues").select("*").order("created_at"),
    supabase.from("channel_groups").select("id, name").order("name"),
    supabase
      .from("queue_items")
      .select(
        "id, queue_id, campaign_id, content_id, scheduled_at, " +
        "campaign:campaigns(id, title, product:products(source_name, category, score, discounted_price_brl, discount_pct)), " +
        "content:contents(id, copy_text)",
      )
      .eq("status", "PENDING")
      .order("scheduled_at", { ascending: true })
      .limit(200),
    supabase.from("queue_groups").select("queue_id, group_id"),
    supabase
      .from("queue_items")
      .select("queue_id, dispatched_at")
      .not("dispatched_at", "is", null)
      .order("dispatched_at", { ascending: false })
      .limit(200),
  ]);

  const gruposPorId = new Map((grupos ?? []).map((group) => [group.id, group.name]));
  const queueItems = (itens ?? []) as unknown as QueueItemRow[];
  const ultimoDespachoPorFila = new Map<string, string>();
  for (const despacho of (despachos ?? []) as DispatchRow[]) {
    if (!ultimoDespachoPorFila.has(despacho.queue_id)) {
      ultimoDespachoPorFila.set(despacho.queue_id, despacho.dispatched_at);
    }
  }
  // O worker publica no máximo um item por intervalo. Arredondar o instante
  // atual para o próximo minuto evita mostrar segundos que a interface omite.
  const proximoMinuto = Math.ceil(Date.now() / 60_000) * 60_000;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <p className="eyebrow">Operação</p>
          <h1 className="text-2xl font-semibold tracking-tight">Fila de publicação</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Controle a ordem real do Telegram, o mix por marketplace e o texto
            de cada oferta. Alterações aqui entram no próximo ciclo do worker.
          </p>
        </div>
        <Badge variant="secondary">
          {queueItems.length} oferta(s) aguardando publicação
        </Badge>
      </div>

      {!filas || filas.length === 0 ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <Card>
            <CardContent className="py-16 text-center text-sm text-muted-foreground">
              Nenhuma fila ainda. Crie a primeira para começar a programação.
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-sm">Nova fila</CardTitle></CardHeader>
            <CardContent>
              <QueueForm grupos={(grupos ?? []).map((group) => ({
                id: group.id,
                name: group.name,
                telegram_chat_id: "",
              }))} />
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="space-y-10">
          {filas.map((fila) => {
            const gruposDaFila = (vinculos ?? [])
              .filter((link) => link.queue_id === fila.id)
              .map((link) => gruposPorId.get(link.group_id) ?? link.group_id);
            const intervaloMs = Number(fila.interval_minutes ?? 5) * 60_000;
            const ultimoDespacho = ultimoDespachoPorFila.get(fila.id);
            let proximaJanela = Math.max(
              proximoMinuto,
              ultimoDespacho
                ? new Date(ultimoDespacho).getTime() + intervaloMs
                : proximoMinuto,
            );
            const editorItems: QueueEditorItem[] = queueItems
              .filter((item) => item.queue_id === fila.id)
              .map((item) => {
                const campaign = one(item.campaign);
                const product = one(campaign?.product);
                const content = one(item.content);
                const horarioSalvo = new Date(item.scheduled_at).getTime();
                const horarioEfetivo = Math.max(
                  Number.isFinite(horarioSalvo) ? horarioSalvo : 0,
                  proximaJanela,
                );
                proximaJanela = horarioEfetivo + intervaloMs;
                return {
                  id: item.id,
                  campaignId: item.campaign_id,
                  contentId: item.content_id ?? "",
                  title: campaign?.title ?? "Campanha sem título",
                  copyText: content?.copy_text ?? "Conteúdo ainda não disponível.",
                  scheduledAt: new Date(horarioEfetivo).toISOString(),
                  sourceName: product?.source_name ?? "",
                  category: product?.category ?? null,
                  score: product?.score == null ? null : Number(product.score),
                  price: product?.discounted_price_brl == null
                    ? null : Number(product.discounted_price_brl),
                  discount: product?.discount_pct == null
                    ? null : Number(product.discount_pct),
                };
              });

            return (
              <section key={fila.id} className="space-y-6">
                <Card className="border-[#D8DCE3] bg-[#15171A] text-white">
                  <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="font-bold">{fila.name}</h2>
                        <Badge variant={fila.is_active ? "secondary" : "outline"}>
                          {fila.is_active ? "Ativa" : "Pausada"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-white/65">
                        A cada {fila.interval_minutes} min
                        {fila.window_start && fila.window_end
                          ? ` · janela ${fila.window_start}–${fila.window_end}`
                          : " · 24 horas"}
                        {gruposDaFila.length
                          ? ` · ${gruposDaFila.join(", ")}`
                          : " · sem grupo vinculado"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <form action={toggleQueue.bind(null, fila.id, !fila.is_active)}>
                        <button type="submit" className="rounded-lg border border-white/20 px-3 py-2 text-xs font-bold hover:bg-white/10">
                          {fila.is_active ? "Pausar fila" : "Ativar fila"}
                        </button>
                      </form>
                      <form action={deleteQueue.bind(null, fila.id)}>
                        <button type="submit" className="rounded-lg border border-red-300/30 px-3 py-2 text-xs font-bold text-red-200 hover:bg-red-400/10">
                          Remover fila
                        </button>
                      </form>
                    </div>
                  </CardContent>
                </Card>

                <QueueEditor
                  queue={{
                    id: fila.id,
                    name: fila.name,
                    intervalMinutes: fila.interval_minutes,
                    shopeeTargetPercent: Number(fila.shopee_target_percent ?? 50),
                    aliexpressTargetPercent: Number(fila.aliexpress_target_percent ?? 20),
                    mercadolivreTargetPercent: Number(fila.mercadolivre_target_percent ?? 30),
                    magaluTargetPercent: Number(fila.magalu_target_percent ?? 0),
                    manualOrderLocked: Boolean(fila.manual_order_locked),
                  }}
                  initialItems={editorItems}
                />
              </section>
            );
          })}

          <details className="rounded-2xl border bg-white p-5">
            <summary className="cursor-pointer text-sm font-bold">Criar outra fila</summary>
            <div className="mt-5 max-w-xl">
              <QueueForm grupos={(grupos ?? []).map((group) => ({
                id: group.id,
                name: group.name,
                telegram_chat_id: "",
              }))} />
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
