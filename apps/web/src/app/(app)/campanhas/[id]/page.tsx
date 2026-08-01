import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  ApproveContentButton,
  SchedulePublicationForm,
} from "@/components/app/campaign-actions";
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

const SCORE_LABEL: Record<string, string> = {
  desconto_real: "Desconto real",
  vendas: "Vendas",
  avaliacao: "Avaliação",
  comissao: "Comissão",
  tendencia: "Tendência",
  apelo_visual: "Apelo visual",
  concorrencia: "Concorrência",
  confiabilidade: "Confiabilidade",
};

const SCORE_MAX: Record<string, number> = {
  desconto_real: 20,
  vendas: 15,
  avaliacao: 15,
  comissao: 15,
  tendencia: 10,
  apelo_visual: 10,
  concorrencia: 10,
  confiabilidade: 5,
};

export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: campanha } = await supabase
    .from("campaigns")
    .select("*, product:products(*)")
    .eq("id", id)
    .single();

  if (!campanha) {
    notFound();
  }

  const [{ data: contents }, { data: publications }] = await Promise.all([
    supabase
      .from("contents")
      .select("*")
      .eq("campaign_id", id)
      .order("version", { ascending: true }),
    supabase
      .from("publications")
      .select("*")
      .eq("campaign_id", id)
      .order("created_at", { ascending: false }),
  ]);

  const produto = campanha.product;
  const aprovadoContent = contents?.find((c) => c.status === "APPROVED");
  const canApprove = campanha.status === "CONTENT_GENERATING" ||
    campanha.status === "REVIEW_REQUIRED" || campanha.status === "READY";
  const canPublish = campanha.status === "APPROVED" ||
    campanha.status === "SCHEDULED" || campanha.status === "PUBLISHED";

  const breakdown = (produto?.score_breakdown ?? {}) as Record<string, number>;

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <Link
          href="/campanhas"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Campanhas
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            {campanha.title || produto?.title || "Campanha"}
          </h1>
          <Badge variant="secondary">
            {STATUS_LABEL[campanha.status] ?? campanha.status}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Produto</CardTitle>
            <CardDescription>
              Ficha importada do marketplace
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {produto?.image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={produto.image_url}
                alt={produto.title || "Imagem do produto"}
                className="aspect-square w-full rounded-md border object-cover"
              />
            )}
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Título</dt>
                <dd className="text-right">{produto?.title}</dd>
              </div>
              {produto?.discounted_price_brl != null && (
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Preço atual</dt>
                  <dd>
                    R$ {Number(produto.discounted_price_brl).toFixed(2)}
                  </dd>
                </div>
              )}
              {produto?.original_price_brl != null && (
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Preço original</dt>
                  <dd>
                    R$ {Number(produto.original_price_brl).toFixed(2)}
                  </dd>
                </div>
              )}
              {produto?.commission_pct != null && (
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Comissão</dt>
                  <dd>{Number(produto.commission_pct).toFixed(1)}%</dd>
                </div>
              )}
              {produto?.sales_count != null && (
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Vendidos</dt>
                  <dd>{Number(produto.sales_count).toLocaleString("pt-BR")}</dd>
                </div>
              )}
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Fonte</dt>
                <dd>
                  {produto?.source_name} · {produto?.method} ·{" "}
                  {produto?.confidence}
                </dd>
              </div>
              {produto?.affiliate_link && (
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Link afiliado</dt>
                  <dd className="text-right">
                    <a
                      href={produto.affiliate_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {produto.affiliate_link_status === "VERIFIED"
                        ? "Verificado"
                        : produto.affiliate_link_status}
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Topfy Score</CardTitle>
            <CardDescription>
              {produto?.score != null
                ? `Score ${Number(produto.score).toFixed(0)}/100 — decomposto abaixo`
                : "O worker ainda não calculou o score."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {produto?.score != null ? (
              <div className="space-y-3">
                {Object.entries(SCORE_LABEL).map(([key, label]) => {
                  const valor = breakdown[key] ?? 0;
                  const max = SCORE_MAX[key];
                  return (
                    <div key={key} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span>{label}</span>
                        <span className="text-muted-foreground">
                          {Math.round(valor)}/{max}
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${Math.min((valor / max) * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Aguardando o worker processar a ficha do produto.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Cópias geradas</h2>
        {!contents || contents.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              Nenhuma cópia ainda — o worker gera 3 variações após importar o
              produto.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {contents.map((c) => (
              <Card
                key={c.id}
                className={c.status === "APPROVED" ? "border-primary" : ""}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">
                      Cópia {c.version}
                    </CardTitle>
                    <Badge variant={c.status === "APPROVED" ? "default" : "secondary"}>
                      {c.status === "APPROVED"
                        ? "Aprovada"
                        : c.status === "REJECTED"
                          ? "Rejeitada"
                          : "Revisão"}
                    </Badge>
                  </div>
                  <CardDescription>
                    {c.provider}
                    {c.model ? ` · ${c.model}` : ""}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {c.copy_text}
                  </p>
                  {c.status !== "APPROVED" && c.status !== "REJECTED" && (
                    <ApproveContentButton
                      campaignId={campanha.id}
                      contentId={c.id}
                      disabled={!canApprove}
                    />
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Publicação</h2>
        {publications && publications.length > 0 ? (
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Canal</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Quando</th>
                  <th className="px-4 py-3 font-medium">Link externo</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {publications.map((p) => (
                  <tr key={p.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">{p.channel}</td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary">{p.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {p.published_at
                        ? new Date(p.published_at).toLocaleString("pt-BR")
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {p.external_id ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Card>
            <CardContent className="py-8">
              {aprovadoContent ? (
                <SchedulePublicationForm
                  campaignId={campanha.id}
                  contentId={aprovadoContent.id}
                  canPublish={canPublish}
                />
              ) : (
                <p className="text-center text-sm text-muted-foreground">
                  Aprove uma das cópias para liberar a publicação.
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
