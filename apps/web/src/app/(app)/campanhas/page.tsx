import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { CaptureLab } from "@/components/app/capture-lab";
import type {
  CaptureLabBlockword,
  CaptureLabCandidate,
  CaptureLabCategory,
  CaptureLabKeyword,
} from "@/components/app/capture-lab";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 10;
const CAMPAIGN_RETENTION_LIMIT = 200;

const CAPTURE_LAB_ACTIONS = [
  "auto_pipeline_aprovado",
  "auto_pipeline_rejeitado",
  "auto_pipeline_bloqueado_por_palavra",
  "auto_pipeline_categoria_bloqueada",
  "auto_pipeline_categoria_recente_demais",
  "auto_pipeline_produto_similar_ja_existe",
  "mercadolivre_oferta_descoberta",
  "mercadolivre_bloqueado_por_palavra",
  "mercadolivre_categoria_bloqueada",
];

type CampanhasPageProps = {
  searchParams: Promise<{ page?: string | string[] }>;
};

function pageHref(page: number) {
  return page === 1 ? "/campanhas" : `/campanhas?page=${page}`;
}

export default async function CampanhasPage({ searchParams }: CampanhasPageProps) {
  const query = await searchParams;
  const rawPage = Array.isArray(query.page) ? query.page[0] : query.page;
  const parsedPage = Number.parseInt(rawPage ?? "1", 10);
  const currentPage = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const from = (currentPage - 1) * PAGE_SIZE;

  const supabase = await createClient();
  const { data: campanhas, count, error } = await supabase
    .from("campaigns")
    .select("id, title, status, platform, created_at", { count: "exact" })
    .order("created_at", { ascending: false })
    .order("id", { ascending: false })
    .range(from, from + PAGE_SIZE - 1);

  // eslint-disable-next-line react-hooks/purity -- Server Component: calculado uma vez por requisição, não em render de cliente.
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  const [
    { data: settingsRow },
    { data: categoryRows },
    { data: keywordRows },
    { data: blockRows },
    { data: recentCategoryRows },
    { data: auditRows },
  ] = await Promise.all([
    supabase.from("discovery_settings").select("min_score").maybeSingle(),
    supabase
      .from("discovery_categories")
      .select("id, family_key, label, active, min_score, target_percent, locked_until, locked_reason")
      .order("label"),
    supabase
      .from("discovery_keywords")
      .select("id, source_name, term, active")
      .order("term"),
    supabase
      .from("discovery_blocklist")
      .select("id, term, is_permanent, expires_at, reason")
      .order("created_at", { ascending: false }),
    supabase
      .from("products")
      .select("category")
      .not("category", "is", null)
      .gte("collected_at", thirtyDaysAgo)
      .limit(500),
    supabase
      .from("audit_log")
      .select("id, created_at, action, metadata")
      .in("action", CAPTURE_LAB_ACTIONS)
      .order("created_at", { ascending: false })
      .limit(40),
  ]);

  const captureCategories: CaptureLabCategory[] = (categoryRows ?? []).map((row) => ({
    id: row.id,
    familyKey: row.family_key,
    label: row.label,
    active: row.active,
    minScore: row.min_score,
    targetPercent: row.target_percent,
    lockedUntil: row.locked_until,
    lockedReason: row.locked_reason,
  }));

  const captureKeywords: CaptureLabKeyword[] = (keywordRows ?? []).map((row) => ({
    id: row.id,
    sourceName: row.source_name,
    term: row.term,
    active: row.active,
  }));

  const captureBlocklist: CaptureLabBlockword[] = (blockRows ?? []).map((row) => ({
    id: row.id,
    term: row.term,
    isPermanent: row.is_permanent,
    expiresAt: row.expires_at,
    reason: row.reason,
  }));

  const existingLabels = new Set(
    captureCategories.map((category) => category.label.trim().toLowerCase()),
  );
  const suggestedCategories = Array.from(
    new Set(
      (recentCategoryRows ?? [])
        .map((row) => (row.category ?? "").trim())
        .filter((value) => value && !existingLabels.has(value.toLowerCase())),
    ),
  ).slice(0, 8);

  const captureCandidates: CaptureLabCandidate[] = (auditRows ?? [])
    .map((row) => {
      const metadata = (row.metadata ?? {}) as Record<string, unknown>;
      return {
        id: row.id,
        createdAt: row.created_at,
        action: row.action,
        title: typeof metadata.title === "string" ? metadata.title : null,
        category: typeof metadata.category === "string" ? metadata.category : null,
        score: typeof metadata.score === "number" ? metadata.score : null,
        reason:
          typeof metadata.motivo === "string"
            ? metadata.motivo
            : typeof metadata.termo === "string"
              ? metadata.termo
              : null,
      };
    })
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
    .slice(0, 20);

  const total = count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (!error && total > 0 && currentPage > totalPages) {
    redirect(pageHref(totalPages));
  }

  const statusLabel: Record<string, string> = {
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

  const firstItem = total === 0 ? 0 : from + 1;
  const lastItem = Math.min(from + PAGE_SIZE, total);

  return (
    <div className="space-y-10">
      <div className="space-y-1">
        <p className="eyebrow">Operação</p>
        <h1 className="text-2xl font-semibold tracking-tight">Laboratório de Captura</h1>
        <p className="text-sm text-muted-foreground">
          Escolha categorias, cure as palavras-chave buscadas em cada fonte, defina o corte de
          score e bloqueie palavras — o worker lê esta configuração a cada ciclo de descoberta.
        </p>
      </div>

      <CaptureLab
        minScore={settingsRow?.min_score ?? 60}
        categories={captureCategories}
        keywords={captureKeywords}
        blocklist={captureBlocklist}
        suggestedCategories={suggestedCategories}
        candidates={captureCandidates}
      />

      <div className="flex flex-wrap items-end justify-between gap-3 border-t pt-8">
        <div className="space-y-1">
          <p className="eyebrow">Histórico</p>
          <h2 className="text-xl font-semibold tracking-tight">Campanhas recentes</h2>
          <p className="text-sm text-muted-foreground">
            {total} de {CAMPAIGN_RETENTION_LIMIT} campanhas armazenadas · 10 por página
          </p>
        </div>
        <Link
          href="/campanhas/nova"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Nova campanha
        </Link>
      </div>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          Não foi possível carregar as campanhas. Tente novamente.
        </div>
      ) : !campanhas || campanhas.length === 0 ? (
        <div className="rounded-md border border-dashed py-16 text-center text-sm text-muted-foreground">
          Nenhuma campanha ainda.{" "}
          <Link href="/campanhas/nova" className="text-primary hover:underline">
            Criar a primeira
          </Link>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[680px] text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Título</th>
                  <th className="px-4 py-3 font-medium">Plataforma</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Criada em</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {campanhas.map((campaign) => (
                  <tr key={campaign.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/campanhas/${campaign.id}`}
                        className="font-medium hover:underline"
                      >
                        {campaign.title || "Sem título"}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {campaign.platform}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium">
                        {statusLabel[campaign.status] ?? campaign.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(campaign.created_at).toLocaleDateString("pt-BR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <nav
            className="flex flex-wrap items-center justify-between gap-3"
            aria-label="Paginação das campanhas"
          >
            <p className="text-sm text-muted-foreground">
              Mostrando {firstItem}–{lastItem} de {total}
            </p>
            <div className="flex flex-wrap items-center justify-end gap-1">
              {currentPage > 1 ? (
                <Link
                  href={pageHref(currentPage - 1)}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                >
                  Anterior
                </Link>
              ) : null}
              {Array.from({ length: totalPages }, (_, index) => index + 1).map((page) => (
                <Link
                  key={page}
                  href={pageHref(page)}
                  aria-current={page === currentPage ? "page" : undefined}
                  className={
                    page === currentPage
                      ? "rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
                      : "rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  }
                >
                  {page}
                </Link>
              ))}
              {currentPage < totalPages ? (
                <Link
                  href={pageHref(currentPage + 1)}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                >
                  Próxima
                </Link>
              ) : null}
            </div>
          </nav>
        </>
      )}

      <p className="rounded-md border border-dashed px-4 py-3 text-xs text-muted-foreground">
        Retenção automática: ao entrar a campanha 201, a mais antiga e seus dados
        operacionais relacionados são removidos do banco.
      </p>
    </div>
  );
}
