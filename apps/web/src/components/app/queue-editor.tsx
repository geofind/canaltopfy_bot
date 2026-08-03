"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowDown,
  ArrowUp,
  Check,
  Clock3,
  GripVertical,
  Pencil,
  RefreshCcw,
  Save,
  Shuffle,
  Trash2,
  X,
} from "lucide-react";
import {
  forceQueueMixAlignment,
  removeQueueItem,
  reorderQueueItems,
  setQueueManualOrder,
  updateQueuedCampaignText,
  updateQueueSourceMix,
} from "@/lib/actions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export type QueueEditorItem = {
  id: string;
  campaignId: string;
  contentId: string;
  title: string;
  copyText: string;
  scheduledAt: string;
  sourceName: string;
  category: string | null;
  score: number | null;
  price: number | null;
  discount: number | null;
};

type QueueEditorProps = {
  queue: {
    id: string;
    name: string;
    intervalMinutes: number;
    shopeeTargetPercent: number;
    aliexpressTargetPercent: number;
    mercadolivreTargetPercent: number;
    magaluTargetPercent: number;
    manualOrderLocked: boolean;
  };
  initialItems: QueueEditorItem[];
};

const SOURCE: Record<string, { label: string; color: string; dot: string }> = {
  shopee: { label: "Shopee", color: "bg-[#EE4D2D]", dot: "bg-[#EE4D2D]" },
  aliexpress: { label: "AliExpress", color: "bg-[#E52B37]", dot: "bg-[#E52B37]" },
  mercadolivre: { label: "Mercado Livre", color: "bg-[#FFE600]", dot: "bg-[#FFE600]" },
  magalu: { label: "Magalu", color: "bg-[#0086FF]", dot: "bg-[#0086FF]" },
};

function formatMoney(value: number | null) {
  if (value == null) return "Preço não informado";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  });
}

export function QueueEditor({ queue, initialItems }: QueueEditorProps) {
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [mix, setMix] = useState({
    shopee: queue.shopeeTargetPercent,
    aliexpress: queue.aliexpressTargetPercent,
    mercadolivre: queue.mercadolivreTargetPercent,
    magalu: queue.magaluTargetPercent,
  });
  const [manualOrderLocked, setManualOrderLocked] = useState(queue.manualOrderLocked);

  const mixTotal = mix.shopee + mix.aliexpress + mix.mercadolivre + mix.magalu;
  const actualMix = useMemo(() => {
    const counts = { shopee: 0, aliexpress: 0, mercadolivre: 0, magalu: 0 };
    for (const item of items) {
      if (item.sourceName in counts) {
        counts[item.sourceName as keyof typeof counts] += 1;
      }
    }
    return counts;
  }, [items]);

  function persistOrder(nextItems: QueueEditorItem[], previous: QueueEditorItem[]) {
    setItems(nextItems);
    setMessage("Salvando nova ordem…");
    startTransition(async () => {
      const result = await reorderQueueItems(queue.id, nextItems.map((item) => item.id));
      if (result.error) {
        setItems(previous);
        setMessage(result.error);
        return;
      }
      setManualOrderLocked(true);
      setMessage("Ordem salva e protegida contra o embaralhamento automático.");
      router.refresh();
    });
  }

  function moveItem(from: number, to: number) {
    if (to < 0 || to >= items.length || from === to || isPending) return;
    const previous = [...items];
    const next = [...items];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    persistOrder(next, previous);
  }

  function dropBefore(targetId: string) {
    if (!draggedId || draggedId === targetId || isPending) return;
    const from = items.findIndex((item) => item.id === draggedId);
    const to = items.findIndex((item) => item.id === targetId);
    setDraggedId(null);
    moveItem(from, to);
  }

  function enableAutomaticOrder() {
    setMessage("Reativando a ordem automática…");
    startTransition(async () => {
      const result = await setQueueManualOrder(queue.id, false);
      if (result.error) {
        setMessage(result.error);
        return;
      }
      setManualOrderLocked(false);
      setMessage("Ordem automática reativada. O próximo ciclo reorganizará a fila por mix e score.");
      router.refresh();
    });
  }

  async function saveMix(formData: FormData) {
    setMessage("Salvando mix…");
    startTransition(async () => {
      const result = await updateQueueSourceMix(queue.id, formData);
      setMessage(result.error ?? "Mix salvo. O próximo ciclo já usará esta distribuição.");
      if (!result.error) router.refresh();
    });
  }

  function forceMixAlignment() {
    setMessage("Enfileirando ajuste do mix…");
    startTransition(async () => {
      const result = await forceQueueMixAlignment(queue.id);
      setMessage(
        result.error ??
          "Ajuste enfileirado: ofertas fora da meta serão pausadas e outras capturadas para alinhar o mix em instantes.",
      );
      if (!result.error) router.refresh();
    });
  }

  async function saveText(item: QueueEditorItem, formData: FormData) {
    setMessage("Salvando texto…");
    startTransition(async () => {
      const result = await updateQueuedCampaignText(item.id, formData);
      if (result.error) {
        setMessage(result.error);
        return;
      }
      const title = String(formData.get("title") ?? "");
      const copyText = String(formData.get("copy_text") ?? "");
      setItems((current) => current.map((row) =>
        row.id === item.id ? { ...row, title, copyText } : row));
      setEditingId(null);
      setMessage("Título e descrição atualizados.");
      router.refresh();
    });
  }

  function removeItem(item: QueueEditorItem) {
    setMessage("Removendo da programação…");
    startTransition(async () => {
      const result = await removeQueueItem(item.id);
      if (result.error) {
        setMessage(result.error);
        return;
      }
      setItems((current) => current.filter((row) => row.id !== item.id));
      setConfirmingId(null);
      setMessage("Campanha removida da fila. Ela continua salva em Campanhas.");
      router.refresh();
    });
  }

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-2xl border bg-white shadow-soft-sm">
        <div className="border-b bg-[#F7F8FA] px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">Mix das fontes</p>
              <h2 className="mt-1 text-lg font-bold">Distribuição desejada</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                A meta orienta campanhas novas e aprovadas. A convergência ocorre sem apagar conteúdo.
              </p>
            </div>
            <Badge variant={mixTotal === 100 ? "secondary" : "destructive"}>
              Total {mixTotal}%
            </Badge>
          </div>
        </div>

        <form action={saveMix} className="space-y-5 p-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {([
              ["shopee", "Shopee", "#EE4D2D"],
              ["aliexpress", "AliExpress", "#E52B37"],
              ["mercadolivre", "Mercado Livre", "#D8BF00"],
              ["magalu", "Magalu", "#0086FF"],
            ] as const).map(([key, label, color]) => (
              <label key={key} className="rounded-xl border bg-[#FBFBFC] p-3">
                <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-[.12em]">
                  <span className="size-2.5 rounded-full" style={{ backgroundColor: color }} />
                  {label}
                </span>
                <span className="mt-3 flex items-center gap-2">
                  <Input
                    name={key}
                    type="number"
                    min={0}
                    max={100}
                    value={mix[key]}
                    onChange={(event) => setMix((current) => ({
                      ...current,
                      [key]: Number(event.target.value),
                    }))}
                    className="text-lg font-black tabular-nums"
                  />
                  <span className="font-bold text-muted-foreground">%</span>
                </span>
                <span className="mt-2 block text-[11px] text-muted-foreground">
                  Agora: {actualMix[key]} campanha(s)
                </span>
              </label>
            ))}
          </div>
          <div className="flex h-3 overflow-hidden rounded-full bg-muted">
            <span className="bg-[#EE4D2D] transition-[width]" style={{ width: `${mix.shopee}%` }} />
            <span className="bg-[#E52B37] transition-[width]" style={{ width: `${mix.aliexpress}%` }} />
            <span className="bg-[#FFE600] transition-[width]" style={{ width: `${mix.mercadolivre}%` }} />
            <span className="bg-[#0086FF] transition-[width]" style={{ width: `${mix.magalu}%` }} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={isPending || mixTotal !== 100}>
              <Save className="size-4" /> Salvar distribuição
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={isPending}
              onClick={forceMixAlignment}
              title="Pausa ofertas das fontes acima da meta e captura novas ofertas das fontes abaixo da meta, agora."
            >
              <RefreshCcw className="size-4" /> Forçar mix agora
            </Button>
          </div>
        </form>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Fila navegável</p>
            <h2 className="mt-1 text-xl font-bold">Próximas ofertas no trilho</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Arraste um cartão ou use as setas. O número 1 é a próxima publicação.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={manualOrderLocked ? "secondary" : "outline"}>
              {manualOrderLocked ? "Ordem manual protegida" : "Ordem automática"}
            </Badge>
            {manualOrderLocked && (
              <Button type="button" size="sm" variant="outline" disabled={isPending} onClick={enableAutomaticOrder}>
                <Shuffle className="size-4" /> Usar ordem automática
              </Button>
            )}
            <Badge variant="outline">{items.length} programadas · {queue.intervalMinutes} min</Badge>
          </div>
        </div>

        {message && (
          <div aria-live="polite" className="mb-4 rounded-xl border bg-white px-4 py-3 text-sm shadow-soft-sm">
            {message}
          </div>
        )}

        <div className="relative space-y-3 before:absolute before:bottom-6 before:left-[2.15rem] before:top-6 before:w-px before:bg-[#D8DCE3]">
          {items.map((item, index) => {
            const source = SOURCE[item.sourceName] ?? {
              label: item.sourceName || "Marketplace",
              color: "bg-slate-400",
              dot: "bg-slate-400",
            };
            const editing = editingId === item.id;
            const confirming = confirmingId === item.id;
            return (
              <article
                key={item.id}
                draggable={!isPending && !editing}
                onDragStart={() => setDraggedId(item.id)}
                onDragEnd={() => setDraggedId(null)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => dropBefore(item.id)}
                className={`relative grid grid-cols-[4.3rem_1fr] gap-3 rounded-2xl border bg-white p-3 shadow-soft-sm transition ${
                  draggedId === item.id ? "scale-[.99] border-primary opacity-60" : "hover:border-[#AAB0BA]"
                }`}
              >
                <div className="relative z-10 flex flex-col items-center gap-2">
                  <span className="grid size-11 place-items-center rounded-full border-4 border-white bg-[#15171A] text-sm font-black text-white shadow-sm">
                    {index + 1}º
                  </span>
                  <GripVertical className="size-5 cursor-grab text-muted-foreground active:cursor-grabbing" />
                </div>

                <div className="min-w-0">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`size-2.5 rounded-full ${source.dot}`} />
                        <span className="text-xs font-bold uppercase tracking-[.1em]">{source.label}</span>
                        {item.score != null && <Badge variant="secondary">Score {Math.round(item.score)}</Badge>}
                        {item.discount != null && item.discount > 0 && (
                          <Badge variant="outline">-{Math.round(item.discount)}%</Badge>
                        )}
                      </div>
                      <h3 className="mt-2 truncate text-sm font-bold sm:text-base">{item.title}</h3>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        <span
                          className="inline-flex items-center gap-1.5"
                          title="Horário programado conforme a posição da fila e o intervalo entre publicações"
                        >
                          <Clock3 className="size-3.5" /> {formatDate(item.scheduledAt)}
                        </span>
                        <span>{formatMoney(item.price)}</span>
                        {item.category && <span className="truncate">{item.category}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        disabled={isPending || index === 0}
                        onClick={() => moveItem(index, index - 1)}
                        aria-label="Adiantar uma posição"
                      ><ArrowUp /></Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        disabled={isPending || index === items.length - 1}
                        onClick={() => moveItem(index, index + 1)}
                        aria-label="Atrasar uma posição"
                      ><ArrowDown /></Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        disabled={isPending}
                        onClick={() => {
                          setEditingId(editing ? null : item.id);
                          setConfirmingId(null);
                        }}
                        aria-label="Editar título e descrição"
                      ><Pencil /></Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        disabled={isPending}
                        onClick={() => {
                          setConfirmingId(confirming ? null : item.id);
                          setEditingId(null);
                        }}
                        aria-label="Remover da fila"
                        className="hover:text-destructive"
                      ><Trash2 /></Button>
                    </div>
                  </div>

                  {editing && (
                    <form action={(formData) => saveText(item, formData)} className="mt-4 space-y-3 border-t pt-4">
                      <label className="block space-y-1.5 text-xs font-bold">
                        Título
                        <Input name="title" defaultValue={item.title} maxLength={180} required />
                      </label>
                      <label className="block space-y-1.5 text-xs font-bold">
                        Descrição da publicação
                        <Textarea name="copy_text" defaultValue={item.copyText} rows={7} maxLength={5000} required />
                      </label>
                      <p className="text-[11px] text-muted-foreground">
                        Preço, desconto, link afiliado, score e imagem permanecem bloqueados.
                      </p>
                      <div className="flex gap-2">
                        <Button type="submit" size="sm" disabled={isPending}><Check /> Salvar texto</Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => setEditingId(null)}>
                          <X /> Cancelar
                        </Button>
                      </div>
                    </form>
                  )}

                  {confirming && (
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/25 bg-destructive/5 p-3">
                      <p className="text-xs text-destructive">
                        Remover somente da programação? A campanha continuará salva.
                      </p>
                      <div className="flex gap-2">
                        <Button type="button" size="sm" variant="destructive" disabled={isPending} onClick={() => removeItem(item)}>
                          Remover da fila
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => setConfirmingId(null)}>
                          Cancelar
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>

        {items.length === 0 && (
          <div className="rounded-2xl border border-dashed bg-white px-6 py-14 text-center text-sm text-muted-foreground">
            Nenhuma campanha pendente. O reabastecedor adicionará novas ofertas conforme o mix salvo.
          </div>
        )}
      </section>
    </div>
  );
}
