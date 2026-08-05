import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { MarketplaceLogo, marketplaceLabel } from "@/components/app/marketplace-logo";

export const dynamic = "force-dynamic";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const CUPOM_IMAGEM_POR_FONTE: Record<string, string> = {
  mercadolivre: "mercadolivre.png",
  shopee: "shopee.png",
  amazon: "amazon.png",
};

// Campanha de cupom (coupon_discovery.py) anuncia o próprio cupom, não um
// produto — usa o selo oficial da loja em vez de uma foto de item.
function cupomImagemUrl(
  sourceName: string | null | undefined,
  cardConfig: Record<string, unknown> | null | undefined,
): string | null {
  if (!cardConfig || !("coupon_offer" in cardConfig)) {
    return null;
  }
  const arquivo = sourceName ? CUPOM_IMAGEM_POR_FONTE[sourceName] : undefined;
  return arquivo ? `/cupons/${arquivo}` : null;
}

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
      description: "Oferta selecionada pelo CanalTopfy — confira na loja.",
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
    .select("*, product:products(*)")
    .eq("slug", slug)
    .eq("public_page", true)
    .single();

  if (!campanha) {
    notFound();
  }

  const { data: conteudoAprovado } = await supabase
    .from("contents")
    .select("copy_text")
    .eq("campaign_id", campanha.id)
    .eq("status", "APPROVED")
    .limit(1)
    .maybeSingle();

  const { data: publicacao } = await supabase
    .from("publications")
    .select("id")
    .eq("campaign_id", campanha.id)
    .eq("status", "PUBLISHED")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  const { data: maisOfertas } = await supabase
    .from("campaigns")
    .select(
      "slug, title, product:products(title, image_url, source_name, discounted_price_brl)",
    )
    .eq("public_page", true)
    .eq("status", "PUBLISHED")
    .neq("id", campanha.id)
    .order("created_at", { ascending: false })
    .limit(3);

  const produto = campanha.product as unknown as {
    title: string | null;
    image_url: string | null;
    original_price_brl: number | null;
    discounted_price_brl: number | null;
    discount_pct: number | null;
    score: number | null;
    source_name: string | null;
    sales_count: number | null;
    rating: number | null;
    seller: string | null;
    category: string | null;
    card_config: Record<string, unknown> | null;
  } | null;

  const aprovado = conteudoAprovado?.copy_text
    ? (conteudoAprovado as unknown as { copy_text: string })
    : null;
  const ctaUrl = publicacao ? `/r/${publicacao.id}` : null;
  const loja = produto?.source_name ? marketplaceLabel(produto.source_name) : null;
  const preco = produto?.discounted_price_brl;
  const original = produto?.original_price_brl;
  const desconto =
    produto?.discount_pct != null && produto.discount_pct > 0
      ? Math.round(produto.discount_pct)
      : null;
  const score =
    produto?.score != null && produto.score > 0
      ? Math.round(produto.score)
      : null;
  const imagemExibida =
    cupomImagemUrl(produto?.source_name, produto?.card_config) ?? produto?.image_url;

  const fatos = [
    preco != null ? `Preço atual: ${brl.format(preco)}` : null,
    original != null ? `De ${brl.format(original)}` : null,
    desconto != null ? `Desconto real de ${desconto}%` : null,
    produto?.sales_count != null
      ? `${produto.sales_count.toLocaleString("pt-BR")} vendidos`
      : null,
    produto?.rating != null ? `${produto.rating.toFixed(1)}/5 de avaliação` : null,
  ].filter((f): f is string => f != null);

  return (
    <main className="flex flex-1 flex-col bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-8">
          <Link href="/ofertas" className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-[10px] bg-[#1F2837] p-1.5">
              <Image
                src="/brand/logo-mark.png"
                alt="CanalTopfy"
                width={26}
                height={26}
                className="h-full w-full object-contain"
              />
            </span>
            <span className="font-display text-base font-bold text-foreground">
              CanalTopfy
            </span>
          </Link>
          <Link
            href="/ofertas"
            className="inline-flex h-9 items-center rounded-lg border border-border bg-background px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            Ver todas as ofertas
          </Link>
        </div>
      </header>

      <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-8 sm:py-14">
        <div className="grid items-start gap-10 lg:grid-cols-2">
          <section className="mx-auto w-full max-w-lg">
            <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-soft">
              <div className="relative aspect-square bg-muted">
                {imagemExibida ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={imagemExibida}
                    alt={produto?.title ?? "Imagem do produto"}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="grid h-full w-full place-items-center p-10 text-center">
                    <span className="font-display text-xl font-bold text-muted-foreground">
                      {produto?.title ?? campanha.title ?? "Oferta"}
                    </span>
                  </div>
                )}
                {desconto != null && (
                  <span className="absolute left-4 top-4 rounded-full bg-[#D71931] px-4 py-1.5 text-sm font-bold text-white shadow">
                    −{desconto}%
                  </span>
                )}
              </div>
            </div>
            {fatos.length > 0 && (
              <ul className="mt-6 space-y-2.5 rounded-2xl border border-border bg-card p-6">
                <li className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
                  O que já está confirmado
                </li>
                {fatos.map((fato) => (
                  <li
                    key={fato}
                    className="flex items-center gap-2 text-sm text-foreground"
                  >
                    <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
                    {fato}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mx-auto w-full max-w-lg lg:pt-4">
            {loja && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-bold uppercase tracking-[2px] text-muted-foreground">
                <MarketplaceLogo source={produto?.source_name} size={14} />
                {loja}
              </span>
            )}
            <h1 className="mt-4 font-display text-3xl font-bold leading-tight tracking-tight text-foreground sm:text-4xl">
              {produto?.title ?? campanha.title ?? "Oferta em destaque"}
            </h1>

            <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2">
              {original != null && (
                <span className="text-lg text-muted-foreground line-through">
                  {brl.format(original)}
                </span>
              )}
              {preco != null ? (
                <span className="text-5xl font-extrabold tracking-tight text-foreground">
                  {brl.format(preco)}
                </span>
              ) : (
                <span className="text-3xl font-bold text-foreground">
                  Ver oferta
                </span>
              )}
              {score != null && (
                <span className="ml-auto rounded-full border border-amber-300/50 bg-amber-400/10 px-3 py-1 text-sm font-bold text-amber-600">
                  Topfy {score}
                </span>
              )}
            </div>

            {aprovado ? (
              <div className="mt-6 rounded-2xl border border-border bg-card p-6">
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {aprovado.copy_text}
                </p>
              </div>
            ) : (
              <div className="mt-6 rounded-2xl border border-dashed bg-card p-6">
                <p className="text-sm text-muted-foreground">
                  Conteúdo em revisão — a oferta estará completa em breve.
                </p>
              </div>
            )}

            {ctaUrl ? (
              <a
                href={ctaUrl}
                className="mt-8 inline-flex h-14 w-full items-center justify-center rounded-xl bg-[#D71931] text-base font-bold text-white shadow transition-colors hover:bg-[#b81427]"
              >
                Ver oferta na loja
              </a>
            ) : (
              <div className="mt-8 flex h-14 w-full items-center justify-center rounded-xl bg-muted text-base font-bold text-muted-foreground">
                Em breve
              </div>
            )}
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Link de afiliado: ao comprar por aqui, o CanalTopfy pode ganhar
              comissão sem custo extra para você.
            </p>
          </section>
        </div>

        {maisOfertas && maisOfertas.length > 0 && (
          <section className="mt-20">
            <div className="flex items-end justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[3px] text-primary">
                  Vitrine CanalTopfy
                </p>
                <h2 className="font-display text-2xl font-bold text-foreground">
                  Mais ofertas
                </h2>
              </div>
              <Link
                href="/ofertas"
                className="text-sm font-medium text-primary hover:underline"
              >
                Ver todas →
              </Link>
            </div>
            <div className="mt-6 grid gap-5 sm:grid-cols-3">
              {maisOfertas.map((outra) => {
                const outroProduto = outra.product as unknown as {
                  title: string | null;
                  image_url: string | null;
                  source_name: string | null;
                  discounted_price_brl: number | null;
                } | null;
                const outroPreco = outroProduto?.discounted_price_brl;
                const outraLoja = outroProduto?.source_name
                  ? marketplaceLabel(outroProduto.source_name)
                  : null;
                return (
                  <Link
                    key={outra.slug}
                    href={`/c/${outra.slug}`}
                    className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-soft transition-shadow hover:shadow-lg"
                  >
                    <div className="relative aspect-[4/3] overflow-hidden bg-muted">
                      {outroProduto?.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={outroProduto.image_url}
                          alt={outroProduto.title ?? "Oferta"}
                          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                        />
                      ) : (
                        <div className="grid h-full w-full place-items-center p-4 text-center">
                          <span className="font-display text-sm font-bold text-muted-foreground">
                            {outroProduto?.title ?? outra.title ?? "Oferta"}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-1 flex-col p-4">
                      <p className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
                        <MarketplaceLogo source={outroProduto?.source_name} size={12} />
                        {outraLoja ?? "Loja"}
                      </p>
                      <h3 className="mt-1 line-clamp-2 text-sm font-semibold text-foreground">
                        {outroProduto?.title ?? outra.title ?? "Oferta"}
                      </h3>
                      {outroPreco != null && (
                        <p className="mt-auto pt-3 text-lg font-bold text-foreground">
                          {brl.format(outroPreco)}
                        </p>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        <footer className="mt-20 border-t border-border pt-8 text-center text-xs text-muted-foreground">
          <p>
            Preço e disponibilidade podem mudar — confira na loja antes de
            comprar. CanalTopfy Affiliate OS.
          </p>
        </footer>
      </div>
    </main>
  );
}
