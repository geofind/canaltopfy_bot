import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

const LOJA_LABEL: Record<string, string> = {
  aliexpress: "AliExpress",
  amazon: "Amazon",
  mercadolivre: "Mercado Livre",
  mercadolibre: "Mercado Livre",
};

function formatarPreco(v: number | null) {
  return v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default async function SugestoesPage() {
  const supabase = await createClient();

  const { data: produtos } = await supabase
    .from("products")
    .select(
      "id, title, image_url, original_price_brl, discounted_price_brl, commission_pct, score, source_name, source_url, rating, sales_count, created_at, campaigns(id)",
    )
    .order("score", { ascending: false, nullsFirst: false })
    .limit(50);

  const sugestoes = (produtos ?? []).filter(
    (p) => !p.campaigns || p.campaigns.length === 0,
  );

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <p className="eyebrow">Sugestões do dia</p>
        <h1 className="text-2xl font-semibold tracking-tight">
          Produtos para testar
        </h1>
        <p className="text-sm text-muted-foreground">
          Produtos curados (melhor Topfy Score) que ainda não viraram
          campanha. Importe um para executar o pipeline completo e publicar.
        </p>
      </div>

      {sugestoes.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Nenhum produto disponível — importe produtos pela página{" "}
            <Link href="/campanhas/nova" className="underline">
              Nova campanha
            </Link>{" "}
            ou aplique o seed de produtos de teste.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {sugestoes.map((p) => {
            const loja = LOJA_LABEL[p.source_name?.toLowerCase()] ?? p.source_name;
            return (
              <Card key={p.id} className="overflow-hidden">
                <div className="flex h-44 items-center justify-center bg-muted/40 p-4">
                  {p.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={p.image_url}
                      alt={p.title}
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      Sem imagem
                    </span>
                  )}
                </div>
                <CardContent className="space-y-3 p-4">
                  <p className="line-clamp-2 text-sm font-medium leading-snug">
                    {p.title}
                  </p>
                  <div className="flex items-end gap-2">
                    <span className="text-lg font-semibold">
                      {formatarPreco(p.discounted_price_brl)}
                    </span>
                    {p.original_price_brl != null &&
                      p.original_price_brl > 0 && (
                        <span className="pb-0.5 text-xs text-muted-foreground line-through">
                          {formatarPreco(p.original_price_brl)}
                        </span>
                      )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {loja && <Badge variant="secondary">{loja}</Badge>}
                    {p.commission_pct != null && (
                      <Badge variant="outline">
                        {p.commission_pct.toLocaleString("pt-BR")}% comissão
                      </Badge>
                    )}
                    {p.score != null && (
                      <Badge
                        variant={p.score >= 80 ? "default" : "secondary"}
                      >
                        Score {p.score.toLocaleString("pt-BR")}
                      </Badge>
                    )}
                  </div>
                  <Link
                    href={`/campanhas/nova?url=${encodeURIComponent(p.source_url ?? "")}`}
                    className="inline-flex h-9 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                  >
                    Importar como campanha
                  </Link>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
