"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Ban,
  ChevronLeft,
  ChevronRight,
  Lock,
  LockOpen,
  Plus,
  Save,
  Shuffle,
  Trash2,
  TrendingUp,
} from "lucide-react";
import {
  addDiscoveryBlockword,
  addDiscoveryKeyword,
  forceCaptureCategoryRedistribution,
  lockDiscoveryCategory,
  removeDiscoveryBlockword,
  removeDiscoveryKeyword,
  setDiscoveryCategoryMinScore,
  setDiscoveryCategoryMlId,
  setDiscoveryCategoryTargetPercent,
  toggleDiscoveryCategory,
  toggleDiscoveryCategoryBestsellerPriority,
  toggleDiscoveryKeyword,
  unlockDiscoveryCategory,
  updateDiscoveryMinScore,
  upsertDiscoveryCategory,
} from "@/lib/actions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

export type CaptureLabCategory = {
  id: string;
  familyKey: string;
  label: string;
  active: boolean;
  minScore: number | null;
  targetPercent: number | null;
  lockedUntil: string | null;
  lockedReason: string | null;
  prioritizeBestsellers: boolean;
  mlCategoryId: string | null;
};

export type CaptureLabKeyword = {
  id: string;
  sourceName: string;
  term: string;
  active: boolean;
};

export type CaptureLabBlockword = {
  id: string;
  term: string;
  isPermanent: boolean;
  expiresAt: string | null;
  reason: string | null;
};

export type CaptureLabCandidate = {
  id: string;
  createdAt: string;
  action: string;
  title: string | null;
  category: string | null;
  score: number | null;
  reason: string | null;
};

export type CaptureLabCategorySuggestion = {
  familyKey: string;
  label: string;
};

type CaptureLabProps = {
  minScore: number;
  categories: CaptureLabCategory[];
  keywords: CaptureLabKeyword[];
  blocklist: CaptureLabBlockword[];
  suggestedCategories: CaptureLabCategorySuggestion[];
  candidates: CaptureLabCandidate[];
};

const SOURCES: { key: string; label: string }[] = [
  { key: "aliexpress", label: "AliExpress" },
  { key: "shopee", label: "Shopee" },
  { key: "mercadolivre", label: "Mercado Livre" },
  { key: "magalu", label: "Magalu" },
];

const DURATIONS: { value: string; label: string }[] = [
  { value: "1h", label: "1 hora" },
  { value: "6h", label: "6 horas" },
  { value: "24h", label: "24 horas" },
  { value: "7d", label: "7 dias" },
];

const APPROVED_ACTIONS = new Set([
  "auto_pipeline_aprovado",
  "mercadolivre_oferta_descoberta",
  "campaign_aprovada",
]);

const RANKING_PAGE_SIZE = 20;

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  });
}

function candidateReason(action: string, reason: string | null) {
  if (reason) return reason;
  switch (action) {
    case "auto_pipeline_aprovado":
    case "mercadolivre_oferta_descoberta":
    case "campaign_aprovada":
      return "Aprovado";
    case "auto_pipeline_rejeitado":
      return "Score abaixo do corte";
    case "auto_pipeline_bloqueado_por_palavra":
    case "mercadolivre_bloqueado_por_palavra":
      return "Palavra bloqueada";
    case "auto_pipeline_categoria_bloqueada":
    case "mercadolivre_categoria_bloqueada":
      return "Categoria pausada/travada";
    case "auto_pipeline_categoria_recente_demais":
      return "Categoria repetida recentemente";
    case "auto_pipeline_produto_similar_ja_existe":
      return "Produto parecido já capturado";
    default:
      return action;
  }
}

export function CaptureLab({
  minScore,
  categories: initialCategories,
  keywords: initialKeywords,
  blocklist: initialBlocklist,
  suggestedCategories,
  candidates,
}: CaptureLabProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const [categories, setCategories] = useState(initialCategories);
  const [keywords, setKeywords] = useState(initialKeywords);
  const [blocklist, setBlocklist] = useState(initialBlocklist);
  const [lockPanelId, setLockPanelId] = useState<string | null>(null);
  const [blockMode, setBlockMode] = useState<"permanent" | "temporary">("permanent");
  const [now, setNow] = useState(() => Date.now());
  const [rankingPage, setRankingPage] = useState(1);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const targetPercentTotal = categories.reduce(
    (sum, category) => sum + (category.targetPercent ?? 0), 0);

  const totalRankingPages = Math.max(1, Math.ceil(candidates.length / RANKING_PAGE_SIZE));
  const safeRankingPage = Math.min(rankingPage, totalRankingPages);
  const rankingFrom = (safeRankingPage - 1) * RANKING_PAGE_SIZE;
  const rankingSlice = candidates.slice(rankingFrom, rankingFrom + RANKING_PAGE_SIZE);

  function report(error?: string, ok?: string) {
    setMessage(error ?? ok ?? null);
    if (!error) router.refresh();
  }

  function saveMinScore(formData: FormData) {
    startTransition(async () => {
      const result = await updateDiscoveryMinScore({}, formData);
      report(result.error, "Corte global salvo.");
    });
  }

  function addCategory(formData: FormData) {
    startTransition(async () => {
      const result = await upsertDiscoveryCategory({}, formData);
      report(result.error, result.info ?? "Categoria adicionada à curadoria.");
    });
  }

  function toggleCategory(category: CaptureLabCategory, active: boolean) {
    setCategories((current) =>
      current.map((row) => (row.id === category.id ? { ...row, active } : row)));
    startTransition(async () => {
      const result = await toggleDiscoveryCategory(category.id, active);
      if (result.error) {
        setCategories((current) =>
          current.map((row) => (row.id === category.id ? category : row)));
      }
      report(result.error, active ? "Categoria reativada." : "Categoria pausada.");
    });
  }

  function saveCategoryMinScore(categoryId: string, formData: FormData) {
    startTransition(async () => {
      const result = await setDiscoveryCategoryMinScore(categoryId, formData);
      report(result.error, "Corte da categoria salvo.");
    });
  }

  function saveCategoryTargetPercent(categoryId: string, formData: FormData) {
    startTransition(async () => {
      const result = await setDiscoveryCategoryTargetPercent(categoryId, formData);
      report(result.error, "Meta de distribuição salva.");
    });
  }

  function toggleBestsellerPriority(category: CaptureLabCategory, prioritizeBestsellers: boolean) {
    setCategories((current) =>
      current.map((row) => (row.id === category.id ? { ...row, prioritizeBestsellers } : row)));
    startTransition(async () => {
      const result = await toggleDiscoveryCategoryBestsellerPriority(
        category.id, prioritizeBestsellers);
      if (result.error) {
        setCategories((current) =>
          current.map((row) => (row.id === category.id ? category : row)));
      }
      report(
        result.error,
        prioritizeBestsellers
          ? "Categoria vai priorizar produtos mais vendidos."
          : "Prioridade de mais vendidos removida.",
      );
    });
  }

  function saveCategoryMlId(categoryId: string, formData: FormData) {
    startTransition(async () => {
      const result = await setDiscoveryCategoryMlId(categoryId, formData);
      report(result.error, "Categoria do Mercado Livre salva.");
    });
  }

  function forceRedistribution() {
    setMessage("Enfileirando redistribuição…");
    startTransition(async () => {
      const result = await forceCaptureCategoryRedistribution();
      report(
        result.error,
        "Redistribuição enfileirada — a fila deve refletir as metas em instantes.",
      );
    });
  }

  function lockCategory(categoryId: string, formData: FormData) {
    startTransition(async () => {
      const result = await lockDiscoveryCategory(categoryId, formData);
      if (!result.error) setLockPanelId(null);
      report(result.error, "Categoria travada temporariamente.");
    });
  }

  function unlockCategory(categoryId: string) {
    startTransition(async () => {
      const result = await unlockDiscoveryCategory(categoryId);
      report(result.error, "Categoria destravada.");
    });
  }

  function addKeyword(formData: FormData) {
    startTransition(async () => {
      const result = await addDiscoveryKeyword({}, formData);
      report(result.error, result.info ?? "Palavra-chave adicionada.");
    });
  }

  function toggleKeyword(keyword: CaptureLabKeyword, active: boolean) {
    setKeywords((current) =>
      current.map((row) => (row.id === keyword.id ? { ...row, active } : row)));
    startTransition(async () => {
      const result = await toggleDiscoveryKeyword(keyword.id, active);
      if (result.error) {
        setKeywords((current) =>
          current.map((row) => (row.id === keyword.id ? keyword : row)));
      }
      report(result.error);
    });
  }

  function removeKeyword(keywordId: string) {
    setKeywords((current) => current.filter((row) => row.id !== keywordId));
    startTransition(async () => {
      await removeDiscoveryKeyword(keywordId);
      router.refresh();
    });
  }

  function addBlockword(formData: FormData) {
    startTransition(async () => {
      const result = await addDiscoveryBlockword({}, formData);
      report(result.error, "Palavra bloqueada.");
    });
  }

  function removeBlockword(blockId: string) {
    setBlocklist((current) => current.filter((row) => row.id !== blockId));
    startTransition(async () => {
      await removeDiscoveryBlockword(blockId);
      router.refresh();
    });
  }

  return (
    <div className="space-y-10">
      {message && (
        <div aria-live="polite" className="animate-in fade-in rounded-xl border bg-white px-4 py-3 text-sm shadow-soft-sm">
          {message}
        </div>
      )}

      <section id="corte" className="scroll-mt-24 animate-in fade-in slide-in-from-bottom-2 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Corte de score</p>
            <h2 className="mt-1 text-xl font-bold">Score mínimo para aprovar sozinho</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Abaixo deste Topfy Score (0–100) a oferta é descartada e só fica no histórico de
              candidatos. Cada categoria pode sobrepor este corte.
            </p>
          </div>
          <Badge variant={targetPercentTotal > 100 ? "destructive" : "outline"}>
            Metas somam {targetPercentTotal}%
          </Badge>
        </div>

        <div className="overflow-hidden rounded-2xl border bg-white shadow-soft-sm">
          <div className="grid md:grid-cols-[auto_1fr]">
            <div className="border-b border-r border-border p-6 md:border-b-0 sm:p-7">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
                Corte global
              </span>
              <p className="mt-2 font-display text-6xl font-bold tracking-[-0.04em]">
                {minScore}
                <span className="text-primary">+</span>
              </p>
            </div>
            <form
              action={saveMinScore}
              className="flex flex-wrap items-end gap-3 border-b border-border p-6 sm:p-7 md:border-b-0"
            >
              <label className="block space-y-1.5 text-xs font-bold">
                Novo valor
                <Input
                  name="min_score"
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  defaultValue={minScore}
                  className="w-28 text-lg font-black tabular-nums"
                />
              </label>
              <Button type="submit" disabled={isPending}>
                <Save className="size-4" /> Salvar corte
              </Button>
              <p className="w-full text-xs leading-5 text-muted-foreground md:max-w-xs">
                O motor só enfileira ofertas acima do corte; abaixo, vira registro no ranking.
              </p>
            </form>
          </div>
        </div>
      </section>

      <section id="categorias" className="scroll-mt-24 animate-in fade-in slide-in-from-bottom-2 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Categorias</p>
            <h2 className="mt-1 text-xl font-bold">O que pode ser capturado</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Pausar ou travar por tempo determinado impede aprovação automática nessa categoria —
              vale para AliExpress, Shopee e Mercado Livre juntos. A meta de distribuição (%)
              orienta a ordem das filas; &ldquo;Aplicar agora&rdquo; força a redistribuição na hora.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={isPending || targetPercentTotal === 0}
            onClick={forceRedistribution}
          >
            <Shuffle className="size-4" /> Aplicar e redistribuir fila agora
          </Button>
        </div>

        <div className="overflow-hidden rounded-2xl border bg-white shadow-soft-sm">
          <div className="grid grid-cols-[2.5rem_1fr] items-center gap-3 border-b bg-[#F7F8FA] px-5 py-2.5 text-[10px] font-black uppercase tracking-[.08em] text-muted-foreground sm:grid-cols-[2.5rem_1fr_auto]">
            <span className="hidden sm:block">#</span>
            <span>Categoria</span>
            <span className="hidden sm:block">Corte / meta / pausa</span>
          </div>
          <div className="divide-y">
            {categories.map((category, index) => {
              const lockedUntil = category.lockedUntil ? new Date(category.lockedUntil) : null;
              const isLocked = !!lockedUntil && lockedUntil.getTime() > now;
              return (
                <div key={category.id} className="group p-4 transition-colors hover:bg-[#FFF7F8] sm:px-5">
                  <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-[2.5rem_1fr_auto]">
                    <span className="hidden font-mono text-xs text-muted-foreground sm:block">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div className="flex flex-wrap items-center gap-3">
                      <Switch
                        checked={category.active}
                        onCheckedChange={(checked) => toggleCategory(category, checked)}
                        disabled={isPending}
                      />
                      <span className="font-bold group-hover:text-primary">{category.label}</span>
                      {!category.active && <Badge variant="destructive">Pausada</Badge>}
                      {isLocked && (
                        <Badge variant="destructive">
                          Travada até {formatDateTime(category.lockedUntil as string)}
                        </Badge>
                      )}
                      {category.prioritizeBestsellers && (
                        <Badge variant="secondary">
                          <TrendingUp className="size-3" /> Mais vendidos
                        </Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                      <form
                        action={(formData) => saveCategoryMinScore(category.id, formData)}
                        className="flex items-center gap-1.5"
                      >
                        <Input
                          name="min_score"
                          type="number"
                          min={0}
                          max={100}
                          step={1}
                          placeholder="corte global"
                          defaultValue={category.minScore ?? ""}
                          className="h-8 w-20 text-sm"
                          aria-label={`Corte de score para ${category.label}`}
                        />
                        <Button type="submit" size="sm" variant="outline" disabled={isPending}>
                          Salvar
                        </Button>
                      </form>
                      <form
                        action={(formData) => saveCategoryTargetPercent(category.id, formData)}
                        className="flex items-center gap-1.5"
                      >
                        <Input
                          name="target_percent"
                          type="number"
                          min={0}
                          max={100}
                          step={1}
                          placeholder="meta %"
                          defaultValue={category.targetPercent ?? ""}
                          className="h-8 w-20 text-sm"
                          aria-label={`Meta de distribuição para ${category.label}`}
                        />
                        <Button type="submit" size="sm" variant="outline" disabled={isPending}>
                          Salvar
                        </Button>
                      </form>
                      <Button
                        type="button"
                        size="sm"
                        variant={category.prioritizeBestsellers ? "secondary" : "outline"}
                        disabled={isPending}
                        onClick={() =>
                          toggleBestsellerPriority(category, !category.prioritizeBestsellers)}
                      >
                        <TrendingUp className="size-4" /> Mais vendidos
                      </Button>
                      {isLocked ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={isPending}
                          onClick={() => unlockCategory(category.id)}
                        >
                          <LockOpen className="size-4" /> Reativar
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={isPending}
                          onClick={() => setLockPanelId(lockPanelId === category.id ? null : category.id)}
                        >
                          <Lock className="size-4" /> Pausar por tempo
                        </Button>
                      )}
                    </div>
                  </div>

                  {category.prioritizeBestsellers && (
                    <form
                      action={(formData) => saveCategoryMlId(category.id, formData)}
                      className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border bg-[#FBFBFC] p-3"
                    >
                      <label className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground">
                        ID da categoria no Mercado Livre (opcional)
                        <Input
                          name="ml_category_id"
                          placeholder="ex.: MLB1055"
                          defaultValue={category.mlCategoryId ?? ""}
                          className="h-8 w-32 text-sm"
                          aria-label={`Categoria oficial do Mercado Livre para ${category.label}`}
                        />
                      </label>
                      <Button type="submit" size="sm" variant="outline" disabled={isPending}>
                        Salvar
                      </Button>
                      <p className="w-full text-xs leading-5 text-muted-foreground">
                        Soma essa categoria à busca de &ldquo;mais vendidos&rdquo; do Mercado
                        Livre — encontre o ID em developers.mercadolivre.com.br (categorias).
                      </p>
                    </form>
                  )}

                  {lockPanelId === category.id && (
                    <form
                      action={(formData) => lockCategory(category.id, formData)}
                      className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border bg-[#FBFBFC] p-3"
                    >
                      <select
                        name="duration"
                        required
                        className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
                        defaultValue=""
                      >
                        <option value="" disabled>
                          Por quanto tempo?
                        </option>
                        {DURATIONS.map((duration) => (
                          <option key={duration.value} value={duration.value}>
                            {duration.label}
                          </option>
                        ))}
                      </select>
                      <Input
                        name="reason"
                        placeholder="Motivo (opcional)"
                        className="h-8 max-w-xs text-sm"
                      />
                      <Button type="submit" size="sm" disabled={isPending}>
                        Confirmar pausa
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setLockPanelId(null)}
                      >
                        Cancelar
                      </Button>
                    </form>
                  )}
                </div>
              );
            })}
            {categories.length === 0 && (
              <p className="p-5 text-sm text-muted-foreground">
                Nenhuma categoria cadastrada ainda — adicione abaixo.
              </p>
            )}
          </div>
        </div>

        {suggestedCategories.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>Vistas recentemente, sem curadoria ainda:</span>
            {suggestedCategories.map((suggestion) => (
              <form key={suggestion.familyKey} action={addCategory}>
                <input type="hidden" name="label" value={suggestion.label} />
                <input type="hidden" name="family_key" value={suggestion.familyKey} />
                <button
                  type="submit"
                  className="inline-flex items-center gap-1 rounded-full border bg-white px-2.5 py-1 transition-colors hover:border-primary hover:bg-[#FFF7F8]"
                >
                  <Plus className="size-3" /> {suggestion.label}
                </button>
              </form>
            ))}
          </div>
        )}

        <form action={addCategory} className="flex items-center gap-2">
          <Input name="label" placeholder="Nova categoria (ex.: fritadeiras)" className="max-w-xs" />
          <Button type="submit" size="sm" variant="outline" disabled={isPending}>
            <Plus className="size-4" /> Adicionar categoria
          </Button>
        </form>
      </section>

      <section id="finder" className="scroll-mt-24 animate-in fade-in slide-in-from-bottom-2 space-y-4">
        <div>
          <p className="eyebrow">Finder</p>
          <h2 className="mt-1 text-xl font-bold">Palavras-chave por fonte</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Termos de busca reais enviados a cada API — somam-se aos já configurados no worker,
            nunca os substituem.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {SOURCES.map((source) => {
            const items = keywords.filter((keyword) => keyword.sourceName === source.key);
            return (
              <div
                key={source.key}
                className="rounded-2xl border bg-white p-5 shadow-soft-sm transition-colors hover:border-primary/25"
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-black uppercase tracking-[.14em] text-muted-foreground">
                    {source.label}
                  </h3>
                  <span className="rounded-full bg-[#F7F8FA] px-2 py-0.5 font-mono text-[10px] font-bold text-muted-foreground">
                    {items.filter((item) => item.active).length}/{items.length}
                  </span>
                </div>
                <div className="mt-4 flex min-h-16 flex-wrap gap-1.5">
                  {items.map((keyword) => (
                    <span
                      key={keyword.id}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                        keyword.active
                          ? "bg-[#F7F8FA] hover:bg-[#FFF7F8]"
                          : "opacity-45 hover:opacity-80"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => toggleKeyword(keyword, !keyword.active)}
                        disabled={isPending}
                        title={keyword.active ? "Pausar termo" : "Reativar termo"}
                        className="font-medium"
                      >
                        {keyword.term}
                      </button>
                      <button
                        type="button"
                        onClick={() => removeKeyword(keyword.id)}
                        disabled={isPending}
                        aria-label={`Remover ${keyword.term}`}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </span>
                  ))}
                  {items.length === 0 && (
                    <span className="text-xs text-muted-foreground">Nenhum termo cadastrado.</span>
                  )}
                </div>
                <form action={addKeyword} className="mt-4 flex items-center gap-1.5 border-t border-border pt-3">
                  <input type="hidden" name="source_name" value={source.key} />
                  <Input name="term" placeholder="novo termo" className="h-8 text-sm" />
                  <Button type="submit" size="sm" variant="outline" disabled={isPending}>
                    <Plus className="size-4" />
                  </Button>
                </form>
              </div>
            );
          })}
        </div>
      </section>

      <section id="bloqueio" className="scroll-mt-24 animate-in fade-in slide-in-from-bottom-2 space-y-4">
        <div>
          <p className="eyebrow">Bloqueio de palavras</p>
          <h2 className="mt-1 text-xl font-bold">Nunca aprovar sozinho se o título tiver...</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Útil quando um tipo de produto está saturando o canal (ex.: muitos fones de ouvido
            seguidos).
          </p>
        </div>

        <div className="overflow-hidden rounded-2xl border bg-white shadow-soft-sm">
          <div className="divide-y">
            {blocklist.map((block) => {
              const expires = block.expiresAt ? new Date(block.expiresAt) : null;
              return (
                <div
                  key={block.id}
                  className="flex flex-wrap items-center gap-3 p-4 transition-colors hover:bg-[#FFF7F8] sm:px-5"
                >
                  <Ban className="size-4 shrink-0 text-destructive" />
                  <span className="font-bold">{block.term}</span>
                  <Badge variant={block.isPermanent ? "destructive" : "outline"}>
                    {block.isPermanent
                      ? "Permanente"
                      : `Expira em ${formatDateTime(block.expiresAt as string)}`}
                  </Badge>
                  {block.reason && (
                    <span className="text-xs text-muted-foreground">{block.reason}</span>
                  )}
                  {expires && expires.getTime() <= now && (
                    <span className="text-xs text-muted-foreground">
                      (já expirado, some no próximo ciclo)
                    </span>
                  )}
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="ml-auto hover:text-destructive"
                    disabled={isPending}
                    onClick={() => removeBlockword(block.id)}
                  >
                    <Trash2 className="size-4" /> Remover
                  </Button>
                </div>
              );
            })}
            {blocklist.length === 0 && (
              <p className="p-5 text-sm text-muted-foreground">Nenhuma palavra bloqueada.</p>
            )}
          </div>
        </div>

        <form
          action={addBlockword}
          className="flex flex-wrap items-end gap-2 rounded-2xl border bg-white p-5 shadow-soft-sm"
        >
          <label className="block space-y-1.5 text-xs font-bold">
            Palavra ou frase
            <Input name="term" placeholder="ex.: fone de ouvido" className="w-48" required />
          </label>
          <label className="block space-y-1.5 text-xs font-bold">
            Motivo (opcional)
            <Input name="reason" placeholder="ex.: saturado esta semana" className="w-56" />
          </label>
          <div className="flex items-center gap-3 pb-1.5 text-xs font-bold">
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="mode"
                value="permanent"
                checked={blockMode === "permanent"}
                onChange={() => setBlockMode("permanent")}
              />
              Permanente
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="mode"
                value="temporary"
                checked={blockMode === "temporary"}
                onChange={() => setBlockMode("temporary")}
              />
              Por tempo
            </label>
          </div>
          {blockMode === "temporary" && (
            <select
              name="duration"
              required
              defaultValue=""
              className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
            >
              <option value="" disabled>
                Por quanto tempo?
              </option>
              {DURATIONS.map((duration) => (
                <option key={duration.value} value={duration.value}>
                  {duration.label}
                </option>
              ))}
            </select>
          )}
          <Button type="submit" disabled={isPending}>
            <Ban className="size-4" /> Bloquear palavra
          </Button>
        </form>
      </section>

      <section id="ranking" className="scroll-mt-24 animate-in fade-in slide-in-from-bottom-2 space-y-4">
        <div>
          <p className="eyebrow">Ranking</p>
          <h2 className="mt-1 text-xl font-bold">Candidatos recentes</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Últimas ofertas avaliadas pelo worker, ordenadas por score — mostra onde o corte está
            caindo na prática.
          </p>
        </div>

        <div className="overflow-x-auto rounded-2xl border bg-white shadow-soft-sm">
          <table className="w-full text-sm">
            <thead className="border-b bg-[#F7F8FA] text-left text-[10px] font-black uppercase tracking-[.08em] text-muted-foreground">
              <tr>
                <th className="px-5 py-3 font-black">Score</th>
                <th className="px-5 py-3 font-black">Produto</th>
                <th className="px-5 py-3 font-black">Categoria</th>
                <th className="px-5 py-3 font-black">Resultado</th>
                <th className="px-5 py-3 font-black">Quando</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rankingSlice.map((candidate) => {
                const approved = APPROVED_ACTIONS.has(candidate.action);
                return (
                  <tr key={candidate.id} className="group transition-colors hover:bg-[#FFF7F8]">
                    <td className="px-5 py-3">
                      <span
                        className={`font-mono text-base font-black tabular-nums ${
                          approved ? "text-emerald-600" : "text-muted-foreground"
                        }`}
                      >
                        {candidate.score != null ? Math.round(candidate.score) : "—"}
                      </span>
                    </td>
                    <td className="max-w-xs truncate px-5 py-3 font-medium group-hover:text-primary">
                      {candidate.title ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">{candidate.category ?? "—"}</td>
                    <td className="px-5 py-3">
                      <Badge variant={approved ? "secondary" : "outline"}>
                        {candidateReason(candidate.action, candidate.reason)}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-muted-foreground">
                      {formatDateTime(candidate.createdAt)}
                    </td>
                  </tr>
                );
              })}
              {rankingSlice.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground">
                    Ainda sem candidatos registrados neste histórico.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {candidates.length > RANKING_PAGE_SIZE && (
          <nav
            className="flex flex-wrap items-center justify-between gap-3"
            aria-label="Paginação do ranking"
          >
            <p className="text-sm text-muted-foreground">
              Mostrando{" "}
              <span className="font-bold text-foreground">
                {candidates.length === 0 ? 0 : rankingFrom + 1}
              </span>
              –
              <span className="font-bold text-foreground">
                {Math.min(rankingFrom + RANKING_PAGE_SIZE, candidates.length)}
              </span>{" "}
              de <span className="font-bold text-foreground">{candidates.length}</span>
            </p>
            <div className="flex flex-wrap items-center justify-end gap-1.5">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safeRankingPage === 1}
                onClick={() => setRankingPage((page) => Math.max(1, page - 1))}
              >
                <ChevronLeft className="size-4" /> Anterior
              </Button>
              {Array.from({ length: totalRankingPages }, (_, index) => index + 1).map((page) => (
                <button
                  key={page}
                  type="button"
                  onClick={() => setRankingPage(page)}
                  aria-current={page === safeRankingPage ? "page" : undefined}
                  className={
                    page === safeRankingPage
                      ? "rounded-[10px] bg-primary px-3 py-1.5 text-sm font-bold text-primary-foreground"
                      : "rounded-[10px] border bg-white px-3 py-1.5 text-sm font-bold transition-colors hover:bg-[#F7F8FA]"
                  }
                >
                  {page}
                </button>
              ))}
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safeRankingPage === totalRankingPages}
                onClick={() => setRankingPage((page) => Math.min(totalRankingPages, page + 1))}
              >
                Próxima <ChevronRight className="size-4" />
              </Button>
            </div>
          </nav>
        )}
      </section>
    </div>
  );
}
