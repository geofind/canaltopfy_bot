import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Send,
  Sparkles,
} from "lucide-react";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Achados e ofertas — CanalTopfy",
  description:
    "Achados selecionados pelo CanalTopfy, com dados disponíveis de preço, desconto e loja.",
};

const LOJA_LABEL: Record<string, string> = {
  aliexpress: "AliExpress",
  amazon: "Amazon",
  mercadolivre: "Mercado Livre",
  mercadolibre: "Mercado Livre",
};

const CARD_TONES = [
  "bg-[#FBE9EC]",
  "bg-[#EAF0F7]",
  "bg-[#F6EFD9]",
  "bg-[#EAF2EC]",
];

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
  return (
    "categoria-" +
    category
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "")
  );
}

function OfertaCard({
  oferta,
  tone,
}: {
  oferta: Oferta;
  tone: string;
}) {
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
      href={"/c/" + oferta.slug}
      className="group flex h-full flex-col rounded-[1.8rem] border border-black/[0.07] bg-white p-2 shadow-[0_18px_55px_rgba(31,40,55,0.08)] transition duration-300 hover:-translate-y-1 hover:shadow-[0_24px_70px_rgba(31,40,55,0.14)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary motion-reduce:transform-none"
    >
      <div
        className={
          "relative aspect-[4/3] overflow-hidden rounded-[1.35rem] " + tone
        }
      >
        {produto?.image_url ? (
          // A origem das imagens varia por marketplace e é salva no banco.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={produto.image_url}
            alt={titulo}
            className="h-full w-full object-contain p-5 transition-transform duration-500 group-hover:scale-[1.035] motion-reduce:transform-none"
          />
        ) : (
          <div className="grid h-full place-items-center p-8 text-center">
            <div>
              <Image
                src="/brand/logo-mark.png"
                alt=""
                width={86}
                height={61}
                className="mx-auto h-auto w-16 opacity-20"
              />
              <span className="mt-4 block font-display text-base font-bold leading-snug text-muted-foreground">
                {titulo}
              </span>
            </div>
          </div>
        )}
        {desconto != null && (
          <span className="absolute left-3 top-3 rounded-full bg-primary px-3 py-1.5 text-xs font-extrabold text-white shadow-sm">
            −{desconto}%
          </span>
        )}
        {score != null && (
          <span className="absolute right-3 top-3 rounded-full border border-white/70 bg-white/90 px-3 py-1.5 font-mono text-[10px] font-bold text-[#1F2837] backdrop-blur">
            TOPFY {score}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col px-3 pb-3 pt-4">
        <div className="flex items-center justify-between gap-3 font-mono text-[9px] font-bold uppercase tracking-[1.4px] text-muted-foreground">
          <span>{nomeDaLoja(produto?.source_name)}</span>
          <span className="truncate text-right">
            {nomeDaCategoria(produto?.category)}
          </span>
        </div>
        <h3 className="mt-3 line-clamp-2 text-[15px] font-bold leading-snug">
          {titulo}
        </h3>
        <div className="mt-auto pt-5">
          {original != null && preco != null && original > preco && (
            <p className="text-xs text-muted-foreground line-through">
              {brl.format(original)}
            </p>
          )}
          <div className="mt-0.5 flex items-end justify-between gap-3">
            <span className="font-display text-2xl font-bold tracking-tight">
              {preco != null ? brl.format(preco) : "Conferir preço"}
            </span>
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-[#1F2837] text-white transition-colors group-hover:bg-primary">
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
  const produtoDestaque = destaque?.product ?? null;
  const tituloDestaque =
    produtoDestaque?.title ?? destaque?.title ?? "Novo achado";
  const precoDestaque = produtoDestaque?.discounted_price_brl;
  const originalDestaque = produtoDestaque?.original_price_brl;
  const descontoDestaque =
    produtoDestaque?.discount_pct != null && produtoDestaque.discount_pct > 0
      ? Math.round(produtoDestaque.discount_pct)
      : null;
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
    <main className="min-h-screen flex-1 bg-white text-foreground">
      <header className="relative z-30 bg-[#F7F8FA]">
        <div className="mx-auto flex h-20 w-full max-w-7xl items-center justify-between px-4 sm:px-8">
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
              className="h-auto w-[112px]"
            />
          </Link>
          <nav className="flex items-center gap-2 sm:gap-5" aria-label="Principal">
            {grupos.length > 0 && (
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
              className="inline-flex h-11 items-center gap-2 rounded-full bg-[#1F2837] px-5 text-sm font-bold text-white transition-colors hover:bg-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
            >
              <Send className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Receber no Telegram</span>
              <span className="sm:hidden">Telegram</span>
            </Link>
          </nav>
        </div>
      </header>

      <section className="relative isolate overflow-hidden bg-[#F7F8FA] px-4 pb-16 pt-10 sm:px-8 sm:pb-24 sm:pt-16">
        <div className="pointer-events-none absolute left-[-11rem] top-20 size-80 rounded-full bg-[#FBE9EC]" />
        <div className="pointer-events-none absolute right-[-9rem] top-60 size-72 rounded-full bg-[#EAF0F7]" />

        <div className="relative mx-auto max-w-4xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#D71931]/15 bg-[#FBE9EC] px-4 py-2 font-mono text-[10px] font-bold uppercase tracking-[1.8px] text-primary">
            <Sparkles className="size-3.5" aria-hidden="true" />
            Curadoria CanalTopfy
          </div>
          <h1 className="mx-auto mt-7 max-w-4xl font-display text-5xl font-bold leading-[0.98] tracking-[-0.04em] text-[#1F2837] sm:text-6xl lg:text-[5.1rem]">
            Seu atalho para achados que{" "}
            <span className="relative inline-block text-primary">
              valem o clique.
              <span className="absolute -bottom-1 left-[4%] -z-10 h-3 w-[92%] rounded-full bg-[#F6C7CE]" />
            </span>
          </h1>
          <p className="mx-auto mt-7 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Tecnologia, casa e utilidades passam pelo Radar Topfy antes de
            aparecer aqui. Você economiza tempo e confirma preço, estoque e
            condições direto na loja.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            {ofertas.length > 0 && (
              <a
                href={
                  grupos.length > 0
                    ? "#achados"
                    : "/c/" + (destaque?.slug ?? "")
                }
                className="inline-flex h-12 items-center gap-2 rounded-full bg-primary px-6 text-sm font-bold text-white shadow-[0_10px_28px_rgba(215,25,49,0.24)] transition-transform hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary motion-reduce:transform-none"
              >
                {grupos.length > 0 ? "Ver achados de hoje" : "Ver o achado de hoje"}
                <ArrowRight className="size-4" aria-hidden="true" />
              </a>
            )}
            <Link
              href="https://t.me/canaltopfy_bot"
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-12 items-center rounded-full border border-[#1F2837]/15 bg-white px-6 text-sm font-bold transition-colors hover:border-[#1F2837]/35"
            >
              Acompanhar no Telegram
            </Link>
          </div>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-xs text-muted-foreground">
            {[
              "Dados sem invenção",
              "Seleção com revisão",
              "Preço confirmado na loja",
            ].map((item) => (
              <span key={item} className="inline-flex items-center gap-2">
                <span className="grid size-5 place-items-center rounded-full bg-[#EAF2EC] text-emerald-700">
                  <Check className="size-3" aria-hidden="true" />
                </span>
                {item}
              </span>
            ))}
          </div>
        </div>

        <div className="relative mx-auto mt-14 max-w-6xl rounded-[2.2rem] border border-black/[0.07] bg-white p-2 shadow-[0_32px_90px_rgba(31,40,55,0.13)] sm:p-3">
          <div className="overflow-hidden rounded-[1.7rem] border border-black/[0.06] bg-[#FBFBFC]">
            <div className="flex h-12 items-center justify-between border-b border-black/[0.06] bg-white px-4 sm:px-6">
              <div className="flex gap-1.5" aria-hidden="true">
                <span className="size-2.5 rounded-full bg-[#F3A6B0]" />
                <span className="size-2.5 rounded-full bg-[#E9D58E]" />
                <span className="size-2.5 rounded-full bg-[#A9D1B8]" />
              </div>
              <div className="inline-flex items-center gap-2 font-mono text-[9px] font-bold uppercase tracking-[1.4px] text-muted-foreground">
                <span className="size-1.5 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]" />
                Radar Topfy · atualizado
              </div>
            </div>

            <div className="grid lg:grid-cols-[240px_1fr]">
              <aside className="border-b border-black/[0.06] bg-[#F1F3F6] p-5 lg:border-b-0 lg:border-r">
                <p className="font-mono text-[9px] font-bold uppercase tracking-[1.7px] text-muted-foreground">
                  Visão da vitrine
                </p>
                <div className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-1">
                  <div className="rounded-2xl bg-white p-4 shadow-sm">
                    <p className="font-display text-3xl font-bold">
                      {ofertas.length}
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {ofertas.length === 1
                        ? "oferta publicada"
                        : "ofertas publicadas"}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-[#1F2837] p-4 text-white shadow-sm">
                    <p className="font-display text-3xl font-bold">{lojas}</p>
                    <p className="mt-1 text-[11px] text-white/55">
                      {lojas === 1 ? "loja no radar" : "lojas no radar"}
                    </p>
                  </div>
                </div>
                {categorias.length > 0 && (
                  <div className="mt-5 space-y-2">
                    {categorias.slice(0, 4).map((categoria, index) => (
                      <div
                        key={categoria}
                        className={
                          "flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold " +
                          (index === 0
                            ? "bg-[#FBE9EC] text-primary"
                            : "text-muted-foreground")
                        }
                      >
                        <span className="size-1.5 rounded-full bg-current opacity-70" />
                        <span className="truncate">{categoria}</span>
                      </div>
                    ))}
                  </div>
                )}
              </aside>

              <div className="p-5 sm:p-7 lg:p-9">
                {destaque ? (
                  <div className="grid items-center gap-7 lg:grid-cols-[0.85fr_1.15fr]">
                    <div className="relative aspect-square overflow-hidden rounded-[1.7rem] bg-[#FBE9EC]">
                      {produtoDestaque?.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={produtoDestaque.image_url}
                          alt={tituloDestaque}
                          className="h-full w-full object-contain p-7"
                        />
                      ) : (
                        <div className="grid h-full place-items-center">
                          <Image
                            src="/brand/logo-mark.png"
                            alt=""
                            width={120}
                            height={85}
                            className="h-auto w-24 opacity-20"
                          />
                        </div>
                      )}
                      {descontoDestaque != null && (
                        <span className="absolute left-4 top-4 rounded-full bg-primary px-3 py-1.5 text-xs font-extrabold text-white">
                          −{descontoDestaque}%
                        </span>
                      )}
                    </div>
                    <div>
                      <p className="font-mono text-[9px] font-bold uppercase tracking-[1.8px] text-primary">
                        Destaque mais recente ·{" "}
                        {nomeDaLoja(produtoDestaque?.source_name)}
                      </p>
                      <h2 className="mt-3 font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
                        {tituloDestaque}
                      </h2>
                      <div className="mt-5 flex flex-wrap items-end gap-x-3 gap-y-1">
                        {originalDestaque != null &&
                          precoDestaque != null &&
                          originalDestaque > precoDestaque && (
                            <span className="pb-1 text-sm text-muted-foreground line-through">
                              {brl.format(originalDestaque)}
                            </span>
                          )}
                        <span className="font-display text-4xl font-bold tracking-tight">
                          {precoDestaque != null
                            ? brl.format(precoDestaque)
                            : "Conferir preço"}
                        </span>
                      </div>
                      <p className="mt-5 max-w-lg text-sm leading-relaxed text-muted-foreground">
                        Veja os dados disponíveis e abra a página da oferta
                        antes de seguir para a loja.
                      </p>
                      <Link
                        href={"/c/" + destaque.slug}
                        className="mt-7 inline-flex h-11 items-center gap-2 rounded-full bg-[#1F2837] px-5 text-sm font-bold text-white transition-colors hover:bg-primary"
                      >
                        Ver detalhes
                        <ArrowRight className="size-4" aria-hidden="true" />
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="grid min-h-80 place-items-center text-center">
                    <div className="max-w-md">
                      <Image
                        src="/brand/logo-mark.png"
                        alt=""
                        width={120}
                        height={85}
                        className="mx-auto h-auto w-24 opacity-20"
                      />
                      <h2 className="mt-6 font-display text-3xl font-bold">
                        O radar está buscando novos achados.
                      </h2>
                      <p className="mt-3 text-sm text-muted-foreground">
                        Acompanhe o Telegram para receber as próximas seleções.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-black/[0.06] px-4 py-12 sm:px-8">
        <div className="mx-auto grid max-w-6xl gap-8 md:grid-cols-3">
          {[
            {
              titulo: "Garimpo com critério",
              texto:
                "Cada produto entra com fonte, dados disponíveis e Topfy Score.",
            },
            {
              titulo: "Decisão antes da automação",
              texto:
                "A oferta passa pelo fluxo de revisão antes de ser publicada.",
            },
            {
              titulo: "Transparência no clique",
              texto:
                "Preço e estoque são confirmados na loja; links de afiliado são sinalizados.",
            },
          ].map((item, index) => (
            <div key={item.titulo} className="flex gap-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-[#FBE9EC] font-mono text-xs font-bold text-primary">
                0{index + 1}
              </span>
              <div>
                <h2 className="text-sm font-bold">{item.titulo}</h2>
                <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                  {item.texto}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {grupos.length > 0 && (
        <div
          id="achados"
          className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-16 sm:px-8 sm:py-24"
        >
          <div className="mx-auto max-w-3xl text-center">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[2px] text-primary">
              Explore o radar
            </p>
            <h2 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
              Encontre seu próximo achado.
            </h2>
            <p className="mt-4 text-sm text-muted-foreground">
              Navegue pelas categorias com produtos publicados agora.
            </p>
          </div>

          <nav
            aria-label="Categorias de ofertas"
            className="mt-9 flex justify-start gap-2 overflow-x-auto py-2 [scrollbar-width:none] sm:justify-center [&::-webkit-scrollbar]:hidden"
          >
            {grupos.map(({ categoria }) => (
              <a
                key={categoria}
                href={"#" + idDaCategoria(categoria)}
                className="shrink-0 rounded-full border border-[#1F2837]/10 bg-[#F7F8FA] px-5 py-2.5 text-xs font-bold transition-colors hover:border-[#1F2837] hover:bg-[#1F2837] hover:text-white"
              >
                {categoria}
              </a>
            ))}
          </nav>

          {grupos.map(({ categoria, ofertas: ofertasDaCategoria }, groupIndex) => (
            <section
              key={categoria}
              id={idDaCategoria(categoria)}
              aria-labelledby={idDaCategoria(categoria) + "-titulo"}
              className="scroll-mt-28 pt-16"
            >
              <div className="flex items-end justify-between gap-4 border-b border-black/[0.08] pb-5">
                <div>
                  <p className="font-mono text-[9px] font-bold uppercase tracking-[1.5px] text-muted-foreground">
                    Coleção CanalTopfy
                  </p>
                  <h2
                    id={idDaCategoria(categoria) + "-titulo"}
                    className="mt-1 font-display text-3xl font-bold tracking-tight sm:text-4xl"
                  >
                    {categoria}
                  </h2>
                </div>
                <span className="rounded-full bg-[#FBE9EC] px-3 py-1.5 font-mono text-[9px] font-bold text-primary">
                  {ofertasDaCategoria.length}{" "}
                  {ofertasDaCategoria.length === 1 ? "ACHADO" : "ACHADOS"}
                </span>
              </div>
              <div className="mt-7 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {ofertasDaCategoria.map((oferta, index) => (
                  <OfertaCard
                    key={oferta.id}
                    oferta={oferta}
                    tone={CARD_TONES[(index + groupIndex) % CARD_TONES.length]}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <section className="mx-auto max-w-7xl px-4 pb-6 sm:px-8 sm:pb-8">
        <div className="relative overflow-hidden rounded-[2.2rem] bg-primary px-6 py-12 text-white sm:px-12 sm:py-16 lg:flex lg:items-center lg:justify-between lg:gap-10">
          <div className="pointer-events-none absolute -right-16 -top-28 size-72 rounded-full border-[48px] border-white/10" />
          <div className="relative max-w-2xl">
            <p className="font-mono text-[9px] font-bold uppercase tracking-[2px] text-white/65">
              CanalTopfy no Telegram
            </p>
            <h2 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
              O radar encontrou. Você recebe.
            </h2>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-white/72">
              Acompanhe os próximos achados e abra cada oferta quando fizer
              sentido para você.
            </p>
          </div>
          <Link
            href="https://t.me/canaltopfy_bot"
            target="_blank"
            rel="noreferrer"
            className="relative mt-7 inline-flex h-12 items-center gap-2 rounded-full bg-white px-6 text-sm font-bold text-primary transition-transform hover:-translate-y-0.5 lg:mt-0 motion-reduce:transform-none"
          >
            <Send className="size-4" aria-hidden="true" />
            Abrir Telegram
          </Link>
        </div>
      </section>

      <footer className="mt-10 bg-[#1F2837] text-white">
        <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-10 sm:px-8 md:grid-cols-[1fr_1.3fr] md:items-end">
          <div>
            <Image
              src="/brand/logo-full.png"
              alt="CanalTopfy"
              width={118}
              height={94}
              className="h-auto w-[108px] rounded bg-white px-2 py-1"
            />
            <p className="mt-4 text-xs text-white/45">
              Curadoria antes do clique.
            </p>
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
