"use server";

import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";

const URL_PRODUTO = z.string().url().refine(
  (url) => url.includes("aliexpress.") ||
    url.includes("mercadolivre.") || url.includes("mercadolibre."),
  {
    message:
      "Por enquanto aceitamos URLs da AliExpress ou do Mercado Livre.",
  },
);

function sourceNameFromUrl(url: string): string {
  if (url.includes("aliexpress.")) {
    return "aliexpress";
  }
  return "mercadolivre";
}

export type AuthActionState = { error?: string };

export async function signIn(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    return { error: "E-mail ou senha inválidos." };
  }
  redirect("/");
}

export async function signUp(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  if (password.length < 6) {
    return { error: "A senha precisa de pelo menos 6 caracteres." };
  }

  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) {
    return { error: "Não foi possível criar a conta. Verifique o e-mail." };
  }

  if (data.user) {
    const orgName = email.split("@")[0] || "Minha Organização";
    const { data: org, error: orgError } = await supabase
      .from("organizations")
      .insert({ name: orgName, slug: `org-${Date.now()}` })
      .select()
      .single();
    if (!orgError && org) {
      await supabase.from("profiles").insert({
        id: data.user.id,
        organization_id: org.id,
        full_name: orgName,
        role: "owner",
      });
    }
  }

  redirect("/");
}

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

export async function connectMercadoLivre() {
  const clientId = process.env.ML_CLIENT_ID;
  const redirectUri = process.env.ML_REDIRECT_URI;
  if (!clientId || !redirectUri) {
    redirect("/?ml=not_configured");
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    redirect("/login");
  }

  const state = randomUUID();
  const cookieStore = await cookies();
  cookieStore.set("ml_oauth_state", state, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });

  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    state,
  });

  redirect(`https://auth.mercadolivre.com.br/authorization?${params.toString()}`);
}

export async function disconnectMercadoLivre() {
  const supabase = await createClient();
  await supabase.from("ml_credentials").delete().neq("organization_id", "");
  revalidatePath("/integracoes");
  revalidatePath("/");
}

export type CampaignActionState = { error?: string; ok?: boolean };

export async function createCampaignFromUrl(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const url = String(formData.get("url") ?? "").trim();

  const parsed = URL_PRODUTO.safeParse(url);
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message ?? "URL inválida." };
  }
  const sourceName = sourceNameFromUrl(url);

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return { error: "Sessão expirada — entre novamente." };
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("organization_id")
    .eq("id", user.id)
    .single();

  if (!profile) {
    return { error: "Perfil não encontrado. Recrie a conta." };
  }

  const { data: product, error: productError } = await supabase
    .from("products")
    .insert({
      organization_id: profile.organization_id,
      source_name: sourceName,
      source_url: url,
      method: "MANUAL",
      confidence: "UNKNOWN",
      status: "IMPORTED",
      title: "Importando produto…",
      collected_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (productError || !product) {
    return { error: "Não foi possível criar o produto." };
  }

  const campaignId = randomUUID();
  const { data: campaign, error: campaignError } = await supabase
    .from("campaigns")
    .insert({
      id: campaignId,
      organization_id: profile.organization_id,
      product_id: product.id,
      status: "IMPORTED",
      platform: "telegram",
      mode: "simulated",
      title: "Nova campanha",
      slug: campaignId,
    })
    .select()
    .single();

  if (campaignError || !campaign) {
    return { error: "Não foi possível criar a campanha." };
  }

  const { error: jobError } = await supabase.from("jobs").insert({
    organization_id: profile.organization_id,
    type: "product.import",
    payload: { source_name: sourceName, url },
  });

  if (jobError) {
    return { error: "Campanha criada, mas falha ao enfileirar o worker." };
  }

  revalidatePath("/");
  revalidatePath("/campanhas");
  return { ok: true };
}

export async function approveCampaignContent(
  campaignId: string,
  contentId: string,
): Promise<CampaignActionState> {
  const supabase = await createClient();

  const { error: contentError } = await supabase
    .from("contents")
    .update({ status: "APPROVED", reviewed_at: new Date().toISOString() })
    .eq("id", contentId);

  if (contentError) {
    return { error: "Não foi possível aprovar o conteúdo." };
  }

  const { data: outros, error: outrosError } = await supabase
    .from("contents")
    .select("id")
    .eq("campaign_id", campaignId)
    .neq("id", contentId);
  if (!outrosError && outros) {
    for (const outro of outros) {
      await supabase
        .from("contents")
        .update({ status: "REJECTED" })
        .eq("id", outro.id);
    }
  }

  const { error: campanhaError } = await supabase
    .from("campaigns")
    .update({ status: "APPROVED" })
    .eq("id", campaignId);
  if (campanhaError) {
    return { error: "Conteúdo aprovado, mas falha ao atualizar a campanha." };
  }

  await supabase.from("audit_log").insert({
    actor_type: "user",
    action: "campanha_aprovada",
    entity_type: "campaign",
    entity_id: campaignId,
    metadata: { content_id: contentId },
  });

  revalidatePath(`/campanhas/${campaignId}`);
  return { ok: true };
}

export async function schedulePublication(
  campaignId: string,
  contentId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const chatId = String(formData.get("chat_id") ?? "").trim();

  if (!chatId) {
    return { error: "Informe o chat_id (canal/grupo) do Telegram." };
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return { error: "Sessão expirada." };
  }
  const { data: profile } = await supabase
    .from("profiles")
    .select("organization_id")
    .eq("id", user.id)
    .single();
  if (!profile) {
    return { error: "Perfil não encontrado." };
  }

  const { data: publication, error: pubError } = await supabase
    .from("publications")
    .insert({
      campaign_id: campaignId,
      content_id: contentId,
      channel: "telegram",
      mode: "simulated",
      status: "SCHEDULED",
      scheduled_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (pubError || !publication) {
    return { error: "Não foi possível criar a publicação." };
  }

  const { error: jobError } = await supabase.from("jobs").insert({
    organization_id: profile.organization_id,
    type: "publication.telegram",
    payload: {
      campaign_id: campaignId,
      content_id: contentId,
      chat_id: chatId,
    },
  });

  if (jobError) {
    return { error: "Publicação criada, mas falha ao enfileirar o worker." };
  }

  await supabase
    .from("campaigns")
    .update({ status: "SCHEDULED", channel_config: { telegram_chat_id: chatId } })
    .eq("id", campaignId);

  revalidatePath(`/campanhas/${campaignId}`);
  return { ok: true };
}
