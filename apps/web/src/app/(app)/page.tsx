import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  BadgeCheck,
  Boxes,
  Clock3,
  TicketCheck,
  Zap,
} from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { LiveCampaignFlow } from "@/components/app/live-campaign-flow";
import { PublicationCountdown } from "@/components/app/publication-countdown";
import { comissaoEstimadaPorUnidade } from "@/lib/commission";

export const dynamic = "force-dynamic";

type JsonRecord = Record<string, unknown>;
type Product = {
  id?: string;
  title?: string | null;
  source_name?: string | null;
  category?: string | null;
  discount_pct?: number | null;
  score?: number | null;
  discounted_price_brl?: number | null;
  commission_pct?: number | null;
  commission_brl?: number | null;
  collected_at?: string | null;
};

type Campaign = {
  id: string;
  status: string;
  created_at: string;
  product: Product | Product[] | null;
};

type QueueItem = {
  id: string;
  scheduled_at: string;
  campaign: {
    id?: string;
    status?: string;
    product?: Product | Product[] | null;
  } | null;
};

function one<T>(value: T | T[] | null | undefined): T | null {
  return Array.isArray(value) ? value[0] ?? null : value ?? null;
}

function numberValue(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatDuration(hours: number) {
  const safeMinutes = Math.max(0, Math.round(hours * 60));
  const h = Math.floor(safeMinutes / 60);
  const m = safeMinutes % 60;
  return `${h}h${String(m).padStart(2, "0")}`;
}

function formatMoney(value: number | null | undefined) {
  if (value == null) return "Preço não informado";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

function formatTime(value: string | Date) {
  return new Date(value).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  });
}

function formatFreshness(value: string | null | undefined) {
  if (!value) return "Sem telemetria";
  const minutes = Math.max(
    0,
    Math.round((Date.now() - new Date(value).getTime()) / 60_000),
  );
  if (minutes < 1) return "agora";
  if (minutes < 60) return `há ${minutes} min`;
  return `há ${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, "0")}`;
}

function sourceLabel(source: string | null | undefined) {
  if (source === "mercadolivre") return "Mercado Livre";
  if (source === "shopee") return "Shopee";
  return "AliExpress";
}

export default async function DashboardPage() {
  const supabase = await createClient();
  // eslint-disable-next-line react-hooks/purity -- Server Component: calculado uma vez por requisição, não em render de cliente.
  const agora = Date.now();
  const oneDayAgo = new Date(agora - 24 * 60 * 60 * 1000).toISOString();

  const [
    { data: heartbeatRows },
    { data: queueRows },
    { data: campaignRows },
    { count: activeCoupons },
    { data: publicationRows },
    { data: jobRows },
    { data: eventRows },
    { data: queueConfigRows },
  ] = await Promise.all([
    supabase
      .from("audit_log")
      .select("created_at, entity_id, metadata")
      .eq("action", "worker_heartbeat")
      .order("created_at", { ascending: false })
      .limit(1),
    supabase
      .from("queue_items")
      .select(
        "id, scheduled_at, campaign:campaigns(id, status, product:products(id, title, source_name, category, discount_pct, score, discounted_price_brl))",
      )
      .eq("status", "PENDING")
      .order("scheduled_at", { ascending: true })
      .limit(150),
    supabase
      .from("campaigns")
      .select(
        "id, status, created_at, product:products(id, title, source_name, category, discount_pct, score, discounted_price_brl, commission_pct, commission_brl, collected_at)",
      )
      .order("created_at", { ascending: false })
      .limit(120),
    supabase
      .from("coupon_codes")
      .select("*", { count: "exact", head: true })
      .eq("is_active", true),
    supabase
      .from("publications")
      .select("published_at, status")
      .eq("status", "PUBLISHED")
      .gte("published_at", oneDayAgo),
    supabase
      .from("jobs")
      .select("status, created_at")
      .order("created_at", { ascending: false })
      .limit(100),
    supabase
      .from("audit_log")
      .select("id, action, created_at, metadata")
      .eq("actor_type", "worker")
      .neq("action", "worker_heartbeat")
      .order("created_at", { ascending: false })
      .limit(12),
    supabase
      .from("queues")
      .select("id, name, interval_minutes, is_active")
      .eq("is_active", true)
      .limit(1),
  ]);

  const heartbeat = heartbeatRows?.[0] ?? null;
  const config = (heartbeat?.metadata ?? {}) as JsonRecord;
  const heartbeatAge = heartbeat
    ? agora - new Date(heartbeat.created_at).getTime()
    : Number.POSITIVE_INFINITY;
  const workerOnline = heartbeatAge <= 12 * 60 * 1000;

  const queueItems = (queueRows ?? []) as unknown as QueueItem[];
  const campaigns = (campaignRows ?? []) as unknown as Campaign[];
  const intervalMinutes = numberValue(
    config.queue_interval_minutes,
    numberValue(queueConfigRows?.[0]?.interval_minutes, 5),
  );
  const lastScheduled = queueItems.at(-1)?.scheduled_at;
  const reserveHours = lastScheduled
    ? Math.max(0, (new Date(lastScheduled).getTime() - agora) / 3_600_000)
    : (queueItems.length * intervalMinutes) / 60;

  const recentOffers = campaigns
    .map((campaign) => ({ campaign, product: one(campaign.product) }))
    .filter(
      (row): row is { campaign: Campaign; product: Product } =>
        Boolean(row.product?.title && numberValue(row.product.discount_pct) > 0),
    )
    .sort(
      (a, b) =>
        numberValue(b.product.discount_pct) - numberValue(a.product.discount_pct),
    )
    .slice(0, 5);

  const cycleMinutes = numberValue(config.ml_cycle_minutes, intervalMinutes);
  const completedJobs = (jobRows ?? []).filter((job) => job.status === "done").length;
  const failedJobs = (jobRows ?? []).filter((job) => job.status === "failed").length;
  const nextQueueItem = queueItems[0] ?? null;
  const nextCampaign = one(nextQueueItem?.campaign);
  const nextProduct = one(nextCampaign?.product);
  const nextPublicationEpochMs = nextQueueItem
    ? new Date(nextQueueItem.scheduled_at).getTime()
    : null;
  const initialRemainingSeconds = nextPublicationEpochMs
    ? Math.max(0, Math.ceil((nextPublicationEpochMs - agora) / 1_000))
    : 0;
  const nextCampaignFlow =
    nextQueueItem && nextCampaign?.id && nextProduct?.title
      ? {
          id: nextCampaign.id,
          title: nextProduct.title,
          source: sourceLabel(nextProduct.source_name),
          scheduledTime: formatTime(nextQueueItem.scheduled_at),
          isDue: new Date(nextQueueItem.scheduled_at).getTime() <= agora,
          priceLabel: formatMoney(nextProduct.discounted_price_brl),
          score: Math.round(numberValue(nextProduct.score)),
          discount: numberValue(nextProduct.discount_pct),
        }
      : null;

  const overviewNav = [
    ["#achados", "Achados"],
    ["#atividade", "Atividade"],
  ] as const;

  return (
    <div className="space-y-8 pb-10">
      <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2">
            <span
              className={`size-2.5 rounded-full ${workerOnline ? "bg-emerald-500 shadow-[0_0_0_5px_rgba(16,185,129,.12)]" : "bg-amber-500"}`}
            />
            <p className="eyebrow">
              Motor {workerOnline ? "online" : "sem heartbeat recente"}
            </p>
          </div>
          <h1 className="mt-3 font-display text-4xl font-bold tracking-[-0.035em] sm:text-5xl">
            Sala de controle das ofertas
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            Captação, qualidade e reserva calculadas direto da operação. Cada
            bloco leva ao detalhe que explica o número.
          </p>
        </div>
        <nav
          aria-label="Seções do dashboard"
          className="flex flex-wrap gap-2 rounded-xl border bg-white p-1.5 shadow-soft-sm"
        >
          {overviewNav.map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="rounded-lg px-3 py-2 text-xs font-bold text-muted-foreground transition-colors hover:bg-[#1F2837] hover:text-white focus-visible:ring-2 focus-visible:ring-primary"
            >
              {label}
            </a>
          ))}
        </nav>
      </header>

      <LiveCampaignFlow
        nextCampaign={nextCampaignFlow}
        workerOnline={workerOnline}
        refreshedAtLabel={formatTime(new Date())}
      />

      <section className="overflow-hidden rounded-2xl bg-[#1F2837] text-white shadow-soft">
        <div className="grid lg:grid-cols-[1.15fr_.85fr]">
          <div className="relative overflow-hidden border-b border-white/10 p-7 sm:p-9 lg:border-b-0 lg:border-r">
            <div className="absolute -right-24 -top-24 size-72 rounded-full border-[42px] border-[#D71931]/15" />
            <div className="relative grid gap-7 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#F65A6C]">
                  Autonomia de publicação
                </p>
                <div className="mt-5 flex flex-wrap items-end gap-x-5 gap-y-2">
                  <strong className="font-display text-7xl font-bold leading-none tracking-[-0.06em] sm:text-8xl">
                    {formatDuration(reserveHours)}
                  </strong>
                  <div className="pb-2 text-sm text-white/55">
                    <p>{queueItems.length} ofertas prontas</p>
                    <p>intervalo de {intervalMinutes} minutos</p>
                  </div>
                </div>
              </div>
              <PublicationCountdown
                targetEpochMs={nextPublicationEpochMs}
                initialRemainingSeconds={initialRemainingSeconds}
                scheduledTimeLabel={
                  nextQueueItem ? formatTime(nextQueueItem.scheduled_at) : "—"
                }
                productTitle={nextProduct?.title ?? null}
              />
            </div>
            <div className="relative mt-7 h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-[#D71931]"
                style={{
                  width: `${Math.min(100, (queueItems.length / Math.max(1, numberValue(config.queue_target_items, 96))) * 100)}%`,
                }}
              />
            </div>
            <div className="relative mt-3 flex justify-between text-[10px] text-white/40">
              <span>gatilho {numberValue(config.queue_min_items, 84)} itens</span>
              <span>alvo {numberValue(config.queue_target_items, 96)} itens</span>
            </div>
          </div>

          <div className="grid grid-cols-2">
            <div className="border-b border-r border-white/10 p-6">
              <Activity className="size-5 text-emerald-400" aria-hidden="true" />
              <p className="mt-5 text-2xl font-bold">
                {workerOnline ? "Ativo" : "Atenção"}
              </p>
              <p className="mt-1 text-xs text-white/45">
                PID {String(config.pid ?? heartbeat?.entity_id ?? "—")}
              </p>
            </div>
            <div className="border-b border-white/10 p-6">
              <Clock3 className="size-5 text-[#F65A6C]" aria-hidden="true" />
              <p className="mt-5 text-2xl font-bold">{cycleMinutes} min</p>
              <p className="mt-1 text-xs text-white/45">ritmo de descoberta</p>
            </div>
            <div className="border-r border-white/10 p-6">
              <TicketCheck className="size-5 text-amber-300" aria-hidden="true" />
              <p className="mt-5 text-2xl font-bold">{activeCoupons ?? 0}</p>
              <p className="mt-1 text-xs text-white/45">cupons ativos verificados</p>
            </div>
            <div className="p-6">
              <Zap className="size-5 text-sky-300" aria-hidden="true" />
              <p className="mt-5 text-2xl font-bold">{publicationRows?.length ?? 0}</p>
              <p className="mt-1 text-xs text-white/45">posts nas últimas 24h</p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 px-7 py-4 text-xs text-white/45 sm:px-9">
          <span>Telemetria recebida {formatFreshness(heartbeat?.created_at)}</span>
          <Link href="/sistema" className="font-bold text-white hover:text-[#F65A6C]">
            Abrir diagnóstico <ArrowUpRight className="ml-1 inline size-3" />
          </Link>
        </div>
      </section>

      <section id="achados" className="scroll-mt-24 space-y-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Dados atuais</p>
            <h2 className="mt-1 text-xl font-bold">Maiores descontos encontrados</h2>
          </div>
          <Link href="/campanhas" className="text-xs font-bold text-primary hover:underline">
            Todas as campanhas →
          </Link>
        </div>

        <div className="overflow-hidden rounded-2xl border bg-white shadow-soft-sm">
          {recentOffers.length ? (
            recentOffers.map(({ campaign, product }, index) => {
              const comissao = comissaoEstimadaPorUnidade(product);
              return (
              <Link
                key={campaign.id}
                href={`/campanhas/${campaign.id}`}
                className="group grid gap-3 border-b px-5 py-4 transition-colors last:border-b-0 hover:bg-[#FFF7F8] sm:grid-cols-[42px_1fr_auto_auto] sm:items-center"
              >
                <span className="font-mono text-xs font-bold text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold group-hover:text-primary">
                    {product.title}
                  </p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {sourceLabel(product.source_name)} · score {Math.round(numberValue(product.score))} · {formatMoney(product.discounted_price_brl)}
                    {comissao != null && (
                      <>
                        {" · "}
                        <span className="font-bold text-emerald-700">
                          comissão {formatMoney(comissao)}/un.
                        </span>
                      </>
                    )}
                  </p>
                </div>
                <span className="w-fit rounded-full bg-[#D71931] px-3 py-1 text-xs font-black text-white">
                  -{numberValue(product.discount_pct).toFixed(2).replace(".", ",")}%
                </span>
                <ArrowUpRight className="hidden size-4 text-muted-foreground sm:block" aria-hidden="true" />
              </Link>
              );
            })
          ) : (
            <p className="p-10 text-center text-sm text-muted-foreground">
              Nenhuma oferta com desconto confirmado foi encontrada ainda.
            </p>
          )}
        </div>
      </section>

      <section id="atividade" className="scroll-mt-24 space-y-4">
        <div>
          <p className="eyebrow">Auditoria</p>
          <h2 className="mt-1 text-xl font-bold">Atividade recente do motor</h2>
        </div>
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <div className="overflow-hidden rounded-2xl border bg-white shadow-soft-sm">
            {(eventRows ?? []).map((event) => (
              <div key={event.id} className="flex items-center gap-3 border-b px-5 py-3.5 last:border-b-0">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted">
                  <Activity className="size-3.5 text-primary" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-bold">{event.action.replaceAll("_", " ")}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    {new Date(event.created_at).toLocaleString("pt-BR")}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-2xl border bg-white p-6 shadow-soft-sm">
            <Boxes className="size-5 text-primary" aria-hidden="true" />
            <h3 className="mt-5 text-sm font-bold">Últimos 100 jobs</h3>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-emerald-50 p-4">
                <p className="font-display text-3xl font-bold text-emerald-700">{completedJobs}</p>
                <p className="text-[10px] font-bold text-emerald-700/70">concluídos</p>
              </div>
              <div className="rounded-xl bg-red-50 p-4">
                <p className="font-display text-3xl font-bold text-red-700">{failedJobs}</p>
                <p className="text-[10px] font-bold text-red-700/70">falhas</p>
              </div>
            </div>
            <Link href="/sistema" className="mt-5 inline-flex items-center text-xs font-bold text-primary hover:underline">
              Examinar jobs e eventos <ArrowUpRight className="ml-1 size-3" />
            </Link>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-3 rounded-xl border border-dashed bg-white/55 p-4 text-xs text-muted-foreground">
        <BadgeCheck className="size-4 text-emerald-600" aria-hidden="true" />
        <span>Fonte: Supabase da organização autenticada.</span>
        <span>•</span>
        <span>Atualização: a cada abertura; heartbeat a cada 5 minutos.</span>
        <span>•</span>
        <span>Cupons sem código ativo nunca entram na copy.</span>
      </div>
    </div>
  );
}
