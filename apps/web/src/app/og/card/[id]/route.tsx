import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const WIDTH = 1024;
const HEIGHT = 1024;

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

type Font = {
  name: string;
  data: ArrayBuffer | Buffer;
  weight: 400 | 700;
  style: "normal" | "italic";
};

async function loadFonts(): Promise<Font[]> {
  const [regular, bold] = await Promise.all([
    readFile(join(process.cwd(), "src/assets/fonts/inter-400.woff")),
    readFile(join(process.cwd(), "src/assets/fonts/inter-700.woff")),
  ]);
  return [
    { name: "Inter", data: regular, weight: 400, style: "normal" },
    { name: "Inter", data: bold, weight: 700, style: "normal" },
  ];
}

async function fetchImageAsDataUrl(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(6000) });
    if (!res.ok) return null;
    const buf = Buffer.from(await res.arrayBuffer());
    const type = res.headers.get("content-type") ?? "image/jpeg";
    return `data:${type};base64,${buf.toString("base64")}`;
  } catch {
    return null;
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: campanha } = await supabase
    .from("campaigns")
    .select("*, product:products(*)")
    .eq("id", id)
    .eq("public_page", true)
    .maybeSingle();

  if (!campanha) {
    return new Response("Campanha não encontrada", { status: 404 });
  }

  const produto = campanha.product as unknown as {
    title: string | null;
    image_url: string | null;
    original_price_brl: number | null;
    discounted_price_brl: number | null;
    discount_pct: number | null;
    score: number | null;
  } | null;

  const titulo = produto?.title ?? campanha.title ?? "Oferta em destaque";
  const tituloLinhas = Math.min(
    2,
    Math.max(1, Math.ceil((titulo.length * 44) / 800)),
  );

  const imageUrl = produto?.image_url
    ? await fetchImageAsDataUrl(produto.image_url)
    : null;

  const hasPrice = produto?.discounted_price_brl != null;
  const desconto =
    produto?.discount_pct != null && produto.discount_pct > 0
      ? Math.round(produto.discount_pct)
      : null;
  const score =
    produto?.score != null && produto.score > 0
      ? Math.round(produto.score)
      : null;

  const pageUrl = `${req.nextUrl.origin}/c/${campanha.slug ?? ""}`;

  const fonts = await loadFonts();

  const card = (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        padding: "64px",
        background:
          "linear-gradient(160deg, #0B1220 0%, #101A2C 45%, #0D1524 100%)",
        color: "#F8FAFC",
        fontFamily: "Inter",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          <span style={{ fontSize: 30, fontWeight: 700, letterSpacing: 2 }}>
            TOPFY
          </span>
          <span
            style={{
              marginLeft: 14,
              fontSize: 22,
              fontWeight: 400,
              color: "#94A3B8",
            }}
          >
            oferta verificada
          </span>
        </div>
        {score != null && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "10px 22px",
              borderRadius: 999,
              background: "rgba(251, 191, 36, 0.12)",
              border: "1px solid rgba(251, 191, 36, 0.35)",
            }}
          >
            <span style={{ fontSize: 24, fontWeight: 700, color: "#FBBF24" }}>
              Topfy {score}
            </span>
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          paddingTop: 36,
          paddingBottom: 36,
        }}
      >
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={titulo}
            width={500}
            height={500}
            style={{
              borderRadius: 40,
              border: "1px solid rgba(148, 163, 184, 0.25)",
              objectFit: "cover",
            }}
          />
        ) : (
          <div
            style={{
              width: 500,
              height: 500,
              borderRadius: 40,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "linear-gradient(180deg, #16233B 0%, #0E1626 100%)",
              border: "1px solid rgba(148, 163, 184, 0.2)",
            }}
          >
            <span
              style={{
                fontSize: 40,
                fontWeight: 700,
                color: "#475569",
                textAlign: "center",
                padding: 40,
              }}
            >
              {titulo}
            </span>
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          minHeight: 96 + (tituloLinhas - 1) * 52,
        }}
      >
        <span
          style={{
            fontSize: 40,
            lineHeight: 1.3,
            fontWeight: 700,
            textAlign: "center",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {titulo}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          marginTop: 24,
        }}
      >
        {produto?.original_price_brl != null && (
          <span
            style={{
              fontSize: 30,
              fontWeight: 400,
              color: "#64748B",
              textDecoration: "line-through",
              marginRight: 18,
            }}
          >
            {brl.format(produto.original_price_brl)}
          </span>
        )}
        {desconto != null && (
          <span
            style={{
              fontSize: 26,
              fontWeight: 700,
              color: "#052E16",
              background: "#34D399",
              padding: "8px 20px",
              borderRadius: 999,
            }}
          >
            −{desconto}%
          </span>
        )}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "center",
          marginTop: 12,
        }}
      >
        <span
          style={{
            fontSize: hasPrice ? 76 : 48,
            fontWeight: 700,
            color: "#F8FAFC",
          }}
        >
          {hasPrice
            ? brl.format(produto!.discounted_price_brl!)
            : "Ver oferta"}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          marginTop: 44,
          borderTop: "1px solid rgba(148, 163, 184, 0.18)",
          paddingTop: 28,
        }}
      >
        <span style={{ fontSize: 22, fontWeight: 400, color: "#64748B" }}>
          {pageUrl}
        </span>
        <span style={{ fontSize: 22, fontWeight: 400, color: "#64748B" }}>
          comissão sem custo extra
        </span>
      </div>
    </div>
  );

  try {
    return new ImageResponse(card, {
      width: WIDTH,
      height: HEIGHT,
      fonts,
    });
  } catch (error) {
    console.error(`card ${id}:`, error);
    return new Response("Falha ao gerar o card", { status: 500 });
  }
}
