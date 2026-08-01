import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: publication } = await supabase
    .from("publications")
    .select("*, campaign:campaigns(product_id)")
    .eq("id", id)
    .maybeSingle();

  if (!publication) {
    return NextResponse.redirect(
      new URL("/", req.nextUrl.origin),
      { status: 302 },
    );
  }

  const campaignRel = publication.campaign as unknown as {
    product_id: string | null;
  } | null;

  const productId = campaignRel?.product_id ?? null;

  let affiliateUrl: string | null | undefined = null;
  if (productId) {
    const { data: produto } = await supabase
      .from("products")
      .select("affiliate_link")
      .eq("id", productId)
      .maybeSingle();
    affiliateUrl = produto?.affiliate_link;
  }

  if (affiliateUrl) {
    await supabase.from("affiliate_clicks").insert({
      publication_id: publication.id,
      campaign_id: publication.campaign_id,
      product_id: productId,
      referrer: req.headers.get("referer"),
      user_agent: req.headers.get("user-agent"),
      utm_source: req.nextUrl.searchParams.get("utm_source"),
      utm_medium: req.nextUrl.searchParams.get("utm_medium"),
      utm_campaign: req.nextUrl.searchParams.get("utm_campaign"),
    });
  }

  return NextResponse.redirect(
    new URL(affiliateUrl ?? "/", req.nextUrl.origin),
    { status: 302 },
  );
}
