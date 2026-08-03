import Link from "next/link";
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

function formatDuration(hours: number) {
  const safeMinutes = Math.max(0, Math.round(hours * 60));
  const h = Math.floor(safeMinutes / 60);
  const m = safeMinutes % 60;
  return `${h}h${String(m).padStart(2, "0")}`;
}

function sourceColor(source: string | null | undefined) {
  if (source === "mercadolivre") return "bg-[#FFE600]";
  if (source === "shopee") return "bg-[#EE4D2D]";
  if (source === "magalu") return "bg-[#0086FF]";
  return "bg-[#E52B37]";
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
  // eslint-disable-next-line react-hooks/purity -- Server Component: calculado uma vez por requisição.
  const proximoMinuto = Math.ceil(Date.now() / 60_000) * 60_000;

  // Visão geral do trilho (todas as filas juntas) — mesma leitura que já
  // existia no dashboard, agora ao lado de onde o mix é editado de verdade.
  const intervalMinutesGlobal = Number(filas?.[0]?.interval_minutes ?? 5);
  const ultimoAgendado = queueItems.at(-1)?.scheduled_at;
  // eslint-disable-next-line react-hooks/purity -- Server Component: calculado uma vez por requisição.
  const agora = Date.now();
  const reserveHours = ultimoAgendado
    ? Math.max(0, (new Date(ultimoAgendado).getTime() - agora) / 3_600_000)
    : (queueItems.length * intervalMinutesGlobal) / 60;
  const queueBySource = queueItems.reduce(
    (acc, item) => {
      const product = one(one(item.campaign)?.product);
      const source =
        product?.source_name === "mercadolivre" ? "mercadolivre"
        : product?.source_name === "shopee" ? "shopee"
        : product?.source_name === "magalu" ? "magalu"
        : "aliexpress";
      acc[source] += 1;
      return acc;
    },
    { aliexpress: 0, mercadolivre: 0, shopee: 0, magalu: 0 },
  );
  const totalParaShare = queueItems.length || 1;
  const aliShare = (queueBySource.aliexpress / totalParaShare) * 100;
  const mlShare = (queueBySource.mercadolivre / totalParaShare) * 100;
  const shopeeShare = (queueBySource.shopee / totalParaShare) * 100;
  const magaluShare = (queueBySource.magalu / totalParaShare) * 100;

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

      {queueItems.length > 0 && (
        <section className="space-y-4">
          <div>
            <p className="eyebrow">Fila navegável</p>
            <h2 className="mt-1 text-xl font-bold">Próximas ofertas no trilho</h2>
          </div>

          <div className="rounded-2xl border bg-white p-5 shadow-soft-sm sm:p-7">
            <div className="grid gap-7 lg:grid-cols-[1fr_280px]">
              <div className="min-w-0">
                <div className="flex h-14 items-center gap-2 overflow-x-auto rounded-xl bg-[#F0F2F5] px-4">
                  <span className="mr-1 shrink-0 text-[9px] font-black uppercase tracking-[.18em] text-muted-foreground">
                    agora
                  </span>
                  <div className="h-px min-w-4 flex-1 bg-[#CBD0D8]" />
                  {queueItems.slice(0, 24).map((item, index) => {
                    const campaign = one(item.campaign);
                    const product = one(campaign?.product);
                    return (
                      <Link
                        key={item.id}
                        href={campaign?.id ? `/campanhas/${campaign.id}` : "/filas"}
                        title={`${index + 1}. ${campaign?.title ?? "Oferta"} — ${new Date(item.scheduled_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`}
                        className={`grid size-4 shrink-0 place-items-center rounded-full ring-4 ring-white transition-transform hover:scale-150 focus-visible:scale-150 ${sourceColor(product?.source_name)}`}
                        aria-label={`Abrir próxima oferta ${index + 1}: ${campaign?.title ?? "sem título"}`}
                      >
                        <span className="size-1 rounded-full bg-black/20" />
                      </Link>
                    );
                  })}
                  <div className="h-px min-w-4 flex-1 bg-[#CBD0D8]" />
                  <span className="shrink-0 text-[9px] font-black uppercase tracking-[.18em] text-muted-foreground">
                    +{formatDuration(reserveHours)}
                  </span>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  Passe o cursor sobre um ponto ou use Tab para ver e abrir a oferta. Soma todas as filas ativas.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs font-bold">
                  <span>Mix das fontes</span>
                  <span>{queueItems.length} itens</span>
                </div>
                <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-muted">
                  <div className="bg-[#E52B37]" style={{ width: `${aliShare}%` }} />
                  <div className="bg-[#FFE600]" style={{ width: `${mlShare}%` }} />
                  <div className="bg-[#EE4D2D]" style={{ width: `${shopeeShare}%` }} />
                  <div className="bg-[#0086FF]" style={{ width: `${magaluShare}%` }} />
                </div>
                <div className="mt-3 flex flex-wrap justify-between gap-2 text-[10px] text-muted-foreground">
                  <span>AliExpress {queueBySource.aliexpress}</span>
                  <span>Mercado Livre {queueBySource.mercadolivre}</span>
                  <span>Shopee {queueBySource.shopee}</span>
                  <span>Magalu {queueBySource.magalu}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

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
