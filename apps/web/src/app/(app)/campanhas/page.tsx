import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

export default async function CampanhasPage() {
  const supabase = await createClient();

  const { data: campanhas } = await supabase
    .from("campaigns")
    .select("id, title, status, platform, created_at")
    .order("created_at", { ascending: false });

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

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="eyebrow">Operação</p>
        <h1 className="text-2xl font-semibold tracking-tight">Campanhas</h1>
      </div>

      {!campanhas || campanhas.length === 0 ? (
        <div className="rounded-md border border-dashed py-16 text-center text-sm text-muted-foreground">
          Nenhuma campanha ainda.{" "}
          <Link href="/campanhas/nova" className="text-primary hover:underline">
            Criar a primeira
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Título</th>
                <th className="px-4 py-3 font-medium">Plataforma</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Criada em</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {campanhas.map((c) => (
                <tr key={c.id} className="hover:bg-muted/50">
                  <td className="px-4 py-3">
                    <a
                      href={`/campanhas/${c.id}`}
                      className="font-medium hover:underline"
                    >
                      {c.title || "Sem título"}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {c.platform}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium">
                      {statusLabel[c.status] ?? c.status}
                    </span>
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
  );
}
