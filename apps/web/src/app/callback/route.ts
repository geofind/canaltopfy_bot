import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

const ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token";

type MlTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  scope: string;
  user_id: string;
  refresh_token: string;
};

async function exchangeCode(
  code: string,
  redirectUri: string,
): Promise<MlTokenResponse> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: process.env.ML_CLIENT_ID ?? "",
    client_secret: process.env.ML_CLIENT_SECRET ?? "",
    code,
    redirect_uri: redirectUri,
  });

  const res = await fetch(ML_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Mercado Livre rejeitou a troca do code: ${res.status}`);
  }
  return res.json();
}

function home(request: NextRequest, result: string) {
  const url = request.nextUrl.clone();
  url.pathname = "/";
  url.search = `?ml=${result}`;
  return NextResponse.redirect(url);
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const code = params.get("code");
  const state = params.get("state");

  const cookieStore = await cookies();
  const stateCookie = cookieStore.get("ml_oauth_state")?.value;

  if (!stateCookie || state !== stateCookie) {
    return home(request, "invalid_state");
  }
  cookieStore.delete("ml_oauth_state");

  if (!code) {
    return home(request, "error");
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return home(request, "auth_required");
  }

  const redirectUri = process.env.ML_REDIRECT_URI;
  if (!redirectUri) {
    return home(request, "not_configured");
  }

  let token: MlTokenResponse;
  try {
    token = await exchangeCode(code, redirectUri);
  } catch {
    return home(request, "exchange_failed");
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("organization_id")
    .eq("id", user.id)
    .single();
  if (!profile) {
    return home(request, "profile_missing");
  }

  const expiresAt = new Date(Date.now() + token.expires_in * 1000).toISOString();

  const { error: upsertError } = await supabase.from("ml_credentials").upsert(
    {
      organization_id: profile.organization_id,
      user_id: user.id,
      access_token: token.access_token,
      refresh_token: token.refresh_token,
      expires_at: expiresAt,
      scope: token.scope ?? null,
      ml_user_id: token.user_id ?? null,
    },
    { onConflict: "organization_id" },
  );

  if (upsertError) {
    return home(request, "save_failed");
  }

  await supabase.from("audit_log").insert({
    organization_id: profile.organization_id,
    actor_type: "user",
    action: "mercadolivre_conectado",
    entity_type: "organization",
    entity_id: profile.organization_id,
    metadata: { expires_at: expiresAt },
  });

  return home(request, "connected");
}
