import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const supabase = await createClient();

  const { data: campanha } = await supabase
    .from("campaigns")
    .select("id, title")
    .eq("slug", slug)
    .eq("public_page", true)
    .maybeSingle();

  if (!campanha) {
    return {};
  }

  return {
    title: campanha.title,
    openGraph: {
      title: campanha.title,
      images: [{ url: `/og/card/${campanha.id}`, width: 1024, height: 1024 }],
    },
  };
}

export default async function ShowcasePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const supabase = await createClient();

  const { data: campanha } = await supabase
    .from("campaigns")
    .select("*, product:products(*), content:contents(*)")
    .eq("slug", slug)
    .eq("public_page", true)
    .single();

  if (!campanha) {
    notFound();
  }

  const { data: publicacao } = await supabase
    .from("publications")
    .select("id")
    .eq("campaign_id", campanha.id)
    .eq("status", "PUBLISHED")
    .maybeSingle();

  const produto = campanha.product;
  const aprovado =
    campanha.content && campanha.content.status === "APPROVED"
      ? campanha.content
      : null;
  const ctaUrl = publicacao ? `/r/${publicacao.id}` : null;

  return (
    <main className="flex flex-1 items-start justify-center px-4 py-16">
      <div className="w-full max-w-2xl space-y-8">
        <header className="text-center space-y-2">
          <p className="text-sm text-muted-foreground">Topfy · afiliados</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            {produto?.title ?? campanha.title}
          </h1>
          {produto?.category && (
            <Badge variant="secondary">{produto.category}</Badge>
          )}
        </header>

        {produto?.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={produto.image_url}
            alt={produto.title || "Imagem do produto"}
            className="mx-auto aspect-square w-full max-w-md rounded-lg border object-cover"
          />
        )}

        <div className="space-y-3 text-center">
          {produto?.original_price_brl != null &&
            produto?.discounted_price_brl != null && (
              <p className="text-muted-foreground line-through">
                R$ {Number(produto.original_price_brl).toFixed(2)}
              </p>
            )}
          {produto?.discounted_price_brl != null && (
            <p className="text-4xl font-bold">
              R$ {Number(produto.discounted_price_brl).toFixed(2)}
            </p>
          )}
        </div>

        {aprovado ? (
          <div className="space-y-4">
            <div className="rounded-lg border bg-muted/50 p-6 text-sm leading-relaxed whitespace-pre-wrap">
              {aprovado.copy_text}
            </div>
            <div className="flex flex-col items-center gap-2">
              <a
                href={ctaUrl ?? "#"}
                className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-8 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Ver oferta na loja
              </a>
              <p className="text-xs text-muted-foreground">
                Link de afiliado: ao comprar por aqui, o Topfy pode ganhar uma
                comissão sem custo extra para você.
              </p>
            </div>
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Conteúdo em revisão — volte em breve.
          </p>
        )}

        <footer className="pt-8 text-center text-xs text-muted-foreground">
          Preço e disponibilidade podem mudar — confira na loja antes de
          comprar.
        </footer>
      </div>
    </main>
  );
}
