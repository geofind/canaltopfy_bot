import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Radio, Send, ShieldCheck } from "lucide-react";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Achados e ofertas — CanalTopfy",
  description:
    "A vitrine do CanalTopfy reúne achados selecionados, com dados disponíveis de preço, desconto e loja.",
};

const LOJA_LABEL: Record<string, string> = {
  aliexpress: "AliExpress",
  amazon: "Amazon",
  mercadolivre: "Mercado Livre",
  mercadolibre: "Mercado Livre",
};

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

type ProdutoOferta = {
  title: string | null;
  image_url: string | null;
  source_name: string | null;
  category: string | null;
  original_price_brl: number | null;
  discounted_price_brl: number | null;
  discount_pct: number | null;
  score: number | null;
};

type Oferta = {
  id: string;
  slug: string;
  title: string | null;
  status: string;
  product: ProdutoOferta | null;
};

function nomeDaLoja(sourceName: string | null | undefined) {
  return sourceName ? LOJA_LABEL[sourceName] ?? sourceName : "Loja parceira";
}

function nomeDaCategoria(category: string | null | undefined) {
  return category?.trim() || "Achadinhos";
}

function idDaCategoria(category: string) {
  return `categoria-${category
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")}`;
}

function OfertaCard({ oferta }: { oferta: Oferta }) {
  const produto = oferta.product;
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
  const titulo = produto?.title ?? oferta.title ?? "Oferta";

  return (
    <Link
      href={`/c/${oferta.slug}`}
      className="group flex h-full flex-col overflow-hidden rounded-[1.35rem] border border-border bg-card shadow-soft-sm transition duration-300 hover:-translate-y-1 hover:border-[#1F2837]/25 hover:shadow-soft focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary motion-reduce:transform-none"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-[#ECEEF2]">
        {produto?.image_url ? (
          // A origem das imagens varia por marketplace e é salva no banco.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={produto.image_url}
            alt={titulo}
            className="h-full w-full object-contain p-4 transition-transform duration-500 group-hover:scale-[1.035] motion-reduce:transform-none"
          />
        ) : (
          <div className="grid h-full place-items-center p-8 text-center">
            <Image
              src="/brand/logo-mark.png"
              alt=""
              width={86}
              height={61}
              className="mb-4 h-auto w-16 opacity-20"
            />
            <span className="font-display text-base font-bold leading-snug text-muted-foreground">
              {titulo}
            </span>
          </div>
        )}

        {desconto != null && (
          <span className="absolute left-3 top-3 rounded-full bg-primary px-3 py-1.5 text-xs font-extrabold text-white shadow-sm">
            −{desconto}%
          </span>
        )}
        {score != null && (
          <span className="absolute right-3 top-3 rounded-full border border-white/60 bg-[#1F2837]/90 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[1.5px] text-white backdrop-blur">
            Sinal {score}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-center justify-between gap-3 text-[10px] font-extrabold uppercase tracking-[1.7px] text-muted-foreground">
          <span>{nomeDaLoja(produto?.source_name)}</span>
          <span className="truncate text-right">
            {nomeDaCategoria(produto?.category)}
          </span>
        </div>
        <h3 className="mt-3 line-clamp-2 text-[15px] font-bold leading-snug text-foreground">
          {titulo}
        </h3>
        <div className="mt-auto pt-5">
          {original != null && preco != null && original > preco && (
            <p className="text-xs text-muted-foreground line-through">
              {brl.format(original)}
            </p>
          )}
          <div className="mt-0.5 flex items-end justify-between gap-3">
            <span className="font-display text-2xl font-bold tracking-tight text-foreground">
              {preco != null ? brl.format(preco) : "Conferir preço"}
            </span>
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[#1F2837] text-white transition-colors group-hover:bg-primary">
              <ArrowUpRight className="size-4" aria-hidden="true" />
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default async function OfertasPage() {
  const supabase = await createClient();

  const { data } = await supabase
    .from("campaigns")
    .select(
      "id, slug, title, status, product:products(source_name, title, image_url, category, original_price_brl, discounted_price_brl, discount_pct, score)",
    )
    .eq("public_page", true)
    .eq("status", "PUBLISHED")
    .order("created_at", { ascending: false })
    .limit(36);

  const ofertas: Oferta[] = (data ?? []).map((row) => ({
    ...row,
    product: Array.isArray(row.product)
      ? (row.product[0] ?? null)
      : row.product,
  }));

  const destaque = ofertas[0] ?? null;
  const demaisOfertas = destaque ? ofertas.slice(1) : ofertas;
  const categorias = Array.from(
    new Set(ofertas.map((oferta) => nomeDaCategoria(oferta.product?.category))),
  );
  const lojas = new Set(
    ofertas
      .map((oferta) => oferta.product?.source_name)
      .filter((loja): loja is string => Boolean(loja)),
  ).size;

  const grupos = categorias
    .map((categoria) => ({
      categoria,
      ofertas: demaisOfertas.filter(
        (oferta) => nomeDaCategoria(oferta.product?.category) === categoria,
      ),
    }))
    .filter((grupo) => grupo.ofertas.length > 0);

  return (
    <main className="min-h-screen flex-1 bg-[#F5F5F5] text-foreground">
      <header className="sticky top-0 z-30 border-b border-black/5 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-[72px] w-full max-w-7xl items-center justify-between px-4 sm:px-8">
          <Link
            href="/ofertas"
            aria-label="CanalTopfy — início da vitrine"
            className="rounded-md focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
          >
            <Image
              src="/brand/logo-full.png"
              alt="CanalTopfy"
              width={118}
              height={94}
              priority
              className="h-auto w-[108px]"
            />
          </Link>
          <nav className="flex items-center gap-2 sm:gap-5" aria-label="Principal">
            {ofertas.length > 0 && (
              <a
                href="#achados"
                className="hidden text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground sm:block"
              >
                Explorar achados
              </a>
            )}
            <Link
              href="https://t.me/canaltopfy_bot"
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-full bg-[#1F2837] px-4 text-sm font-bold text-white transition-colors hover:bg-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
            >
              <Send className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Receber no Telegram</span>
              <span className="sm:hidden">Telegram</span>
            </Link>
          </nav>
        </div>
      </header>

      <section className="relative isolate overflow-hidden bg-[#1F2837] text-white">
        <div className="pointer-events-none absolute -right-20 top-1/2 size-[420px] -translate-y-1/2 rounded-full border-[70px] border-white/[0.035]" />
        <div className="pointer-events-none absolute right-[86px] top-1/2 size-2 -translate-y-1/2 rounded-full bg-primary shadow-[0_0_0_14px_rgba(215,25,49,0.12),0_0_0_32px_rgba(215,25,49,0.05)]" />
        <div className="mx-auto grid w-full max-w-7xl gap-10 px-4 py-14 sm:px-8 sm:py-20 lg:grid-cols-[1.08fr_0.92fr] lg:items-end lg:py-24">
          <div className="relative z-10 max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[2px] text-white/75">
              <Radio className="size-3.5 text-primary" aria-hidden="true" />
              Radar CanalTopfy
            </div>
            <h1 className="mt-6 max-w-2xl font-display text-5xl font-bold leading-[0.98] tracking-[-0.035em] sm:text-6xl lg:text-7xl">
              Achados que valem o clique.
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-white/68 sm:text-lg">
              Tecnologia, casa e utilidades escolhidas para poupar seu tempo.
              Você vê os dados disponíveis aqui e confirma preço e estoque na
              loja antes de comprar.
            </p>
          </div>

          <aside className="relative z-10 border-l border-white/15 pl-6 lg:justify-self-end lg:pl-8">
            <p className="text-[10px] font-extrabold uppercase tracking-[2px] text-white/45">
              No radar agora
            </p>
            <div className="mt-4 flex gap-8 sm:gap-12">
              <div>
                <p className="font-display text-4xl font-bold">{ofertas.length}</p>
                <p className="mt-1 text-xs text-white/55">
                  {ofertas.length === 1 ? "oferta publicada" : "ofertas publicadas"}
                </p>
              </div>
              <div>
                <p className="font-display text-4xl font-bold">{lojas}</p>
                <p className="mt-1 text-xs text-white/55">
                  {lojas === 1 ? "loja no radar" : "lojas no radar"}
                </p>
              </div>
            </div>
            <div className="mt-7 flex items-start gap-2.5 text-xs leading-relaxed text-white/58">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              <span>Sem preço inventado: dados ausentes ficam claramente sinalizados.</span>
            </div>
          </aside>
        </div>
      </section>

      {ofertas.length === 0 ? (
        <section className="mx-auto grid min-h-[420px] w-full max-w-7xl place-items-center px-4 py-20 sm:px-8">
          <div className="max-w-lg text-center">
            <Image
              src="/brand/logo-mark.png"
              alt=""
              width={120}
              height={85}
              className="mx-auto h-auto w-24 opacity-25"
            />
            <h2 className="mt-7 font-display text-3xl font-bold">
              O radar está buscando novos achados.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Nenhuma oferta está publicada neste momento. Entre no Telegram
              para acompanhar as próximas seleções do CanalTopfy.
            </p>
            <Link
              href="https://t.me/canaltopfy_bot"
              target="_blank"
              rel="noreferrer"
              className="mt-7 inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-bold text-white hover:bg-[#b81427]"
            >
              <Send className="size-4" aria-hidden="true" />
              Acompanhar no Telegram
            </Link>
          </div>
        </section>
      ) : (
        <div id="achados" className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-14 sm:px-8 sm:py-20">
          {destaque && (
            <section aria-labelledby="destaque-titulo">
              <div className="mb-6 flex items-end justify-between gap-4">
                <div>
                  <p className="text-[10px] font-extrabold uppercase tracking-[2.5px] text-primary">
                    Acabou de entrar
                  </p>
                  <h2 id="destaque-titulo" className="mt-1 font-display text-3xl font-bold tracking-tight">
                    Destaque do radar
                  </h2>
                </div>
                <p className="hidden max-w-xs text-right text-xs leading-relaxed text-muted-foreground sm:block">
                  A seleção mais recente publicada pelo CanalTopfy.
                </p>
              </div>
              <div className="max-w-md">
                <OfertaCard oferta={destaque} />
              </div>
            </section>
          )}

          {grupos.length > 0 && (
            <>
              <nav
                aria-label="Categorias de ofertas"
                className="mt-16 flex gap-2 overflow-x-auto border-y border-border py-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              >
                {grupos.map(({ categoria }) => (
                  <a
                    key={categoria}
                    href={`#${idDaCategoria(categoria)}`}
                    className="shrink-0 rounded-full border border-border bg-white px-4 py-2 text-xs font-bold text-foreground transition-colors hover:border-[#1F2837] hover:bg-[#1F2837] hover:text-white"
                  >
                    {categoria}
                  </a>
                ))}
              </nav>

              {grupos.map(({ categoria, ofertas: ofertasDaCategoria }) => (
                <section
                  key={categoria}
                  id={idDaCategoria(categoria)}
                  aria-labelledby={`${idDaCategoria(categoria)}-titulo`}
                  className="scroll-mt-28 pt-14 sm:pt-16"
                >
                  <div className="flex items-baseline justify-between gap-4 border-b border-border pb-4">
                    <h2
                      id={`${idDaCategoria(categoria)}-titulo`}
                      className="font-display text-2xl font-bold tracking-tight sm:text-3xl"
                    >
                      {categoria}
                    </h2>
                    <span className="text-xs font-bold text-muted-foreground">
                      {ofertasDaCategoria.length} {ofertasDaCategoria.length === 1 ? "achado" : "achados"}
                    </span>
                  </div>
                  <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {ofertasDaCategoria.map((oferta) => (
                      <OfertaCard key={oferta.id} oferta={oferta} />
                    ))}
                  </div>
                </section>
              ))}
            </>
          )}
        </div>
      )}

      <footer className="border-t border-white/10 bg-[#1F2837] text-white">
        <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-10 sm:px-8 md:grid-cols-[1fr_1.3fr] md:items-end">
          <div>
            <Image
              src="/brand/logo-full.png"
              alt="CanalTopfy"
              width={118}
              height={94}
              className="h-auto w-[108px] rounded bg-white px-2 py-1"
            />
            <p className="mt-4 text-xs text-white/45">Curadoria antes do clique.</p>
          </div>
          <div className="text-xs leading-relaxed text-white/48 md:text-right">
            <p>
              Alguns links são de afiliado: o CanalTopfy pode receber comissão
              por compras qualificadas, sem custo extra para você.
            </p>
            <p className="mt-1">
              Preço, estoque e condições podem mudar. Confirme tudo na loja.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
