"use server";

import { randomUUID, randomBytes, createHash } from "node:crypto";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";

const URL_PRODUTO = z.string().url().refine(
  (url) => url.includes("aliexpress.") ||
    url.includes("mercadolivre.") || url.includes("mercadolibre.") ||
    url.includes("meli.la") ||
    url.includes("amazon.") || url.includes("amzn.") ||
    url.includes("shopee.") || url.includes("shope.ee") ||
    url.includes("magazinevoce.") || url.includes("magazineluiza.") ||
    url.includes("magalu."),
  {
    message:
      "Aceitamos URLs da AliExpress, Mercado Livre, Amazon, Shopee e Magalu, inclusive os links curtos oficiais.",
  },
);

const URL_AFILIADO_ML = z.string().url().refine((value) => {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.toLowerCase();
    const allowed = ["meli.la", "mercadolivre.com.br", "mercadolibre.com.br"];
    return parsed.protocol === "https:" && allowed.some(
      (domain) => host === domain || host.endsWith(`.${domain}`),
    );
  } catch {
    return false;
  }
}, {
  message: "Use o link HTTPS devolvido pelo Gerador oficial (normalmente meli.la).",
});

function sourceNameFromUrl(url: string): string {
  if (url.includes("aliexpress.")) {
    return "aliexpress";
  }
  if (url.includes("mercadolivre.") || url.includes("mercadolibre.") ||
      url.includes("meli.la")) {
    return "mercadolivre";
  }
  if (url.includes("amazon.") || url.includes("amzn.")) {
    return "amazon";
  }
  if (url.includes("shopee.") || url.includes("shope.ee")) {
    return "shopee";
  }
  if (url.includes("magazinevoce.") || url.includes("magazineluiza.") ||
      url.includes("magalu.")) {
    return "magalu";
  }
  return "mercadolivre";
}

export type AuthActionState = { error?: string };

// Cria organization+profile se ainda não existirem para este usuário.
// Precisa ser chamada com uma sessão já ativa (RLS de organizations exige
// auth.uid() não nulo) — por isso signUp() sozinho não basta quando o
// projeto exige confirmação de e-mail: signUp() não estabelece sessão até
// a confirmação, então o insert falhava em silêncio. Chamar isso de novo
// em signIn() faz a conta se autocurar no primeiro login real.
async function ensureProfile(
  supabase: Awaited<ReturnType<typeof createClient>>,
  userId: string,
  email: string,
): Promise<void> {
  const { data: profile } = await supabase
    .from("profiles")
    .select("id")
    .eq("id", userId)
    .maybeSingle();
  if (profile) {
    return;
  }

  const orgName = email.split("@")[0] || "Minha Organização";
  const { data: org, error: orgError } = await supabase
    .from("organizations")
    .insert({ name: orgName, slug: `org-${Date.now()}` })
    .select()
    .single();
  if (!orgError && org) {
    await supabase.from("profiles").insert({
      id: userId,
      organization_id: org.id,
      full_name: orgName,
      role: "owner",
    });
  }
}

export async function signIn(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    return { error: "E-mail ou senha inválidos." };
  }
  if (data.user) {
    await ensureProfile(supabase, data.user.id, email);
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

  if (data.user && data.session) {
    // Só existe sessão aqui quando o projeto não exige confirmação de
    // e-mail; caso exija, ensureProfile roda no primeiro signIn.
    await ensureProfile(supabase, data.user.id, email);
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
  // PKCE (RFC 7636) — o app do Mercado Livre exige code_challenge/
  // code_verifier além do state; sem isso o /oauth/token responde
  // "code_verifier is a required parameter".
  const codeVerifier = randomBytes(32).toString("base64url");
  const codeChallenge = createHash("sha256").update(codeVerifier).digest("base64url");

  const cookieStore = await cookies();
  cookieStore.set("ml_oauth_state", state, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });
  cookieStore.set("ml_oauth_verifier", codeVerifier, {
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
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
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
    payload: {
      source_name: sourceName,
      url,
      product_id: product.id,
      campaign_id: campaignId,
    },
  });

  if (jobError) {
    return { error: "Campanha criada, mas falha ao enfileirar o worker." };
  }

  revalidatePath("/");
  revalidatePath("/campanhas");
  return { ok: true };
}

export async function completeMercadoLivreAutomation(
  campaignId: string,
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }

  const parsedLink = URL_AFILIADO_ML.safeParse(
    String(formData.get("affiliate_url") ?? "").trim(),
  );
  if (!parsedLink.success) {
    return { error: parsedLink.error.issues[0]?.message ?? "Link inválido." };
  }
  const queueId = String(formData.get("queue_id") ?? "").trim();
  if (!queueId) {
    return { error: "Selecione a fila automática do Telegram." };
  }

  const { data: campaign } = await supabase
    .from("campaigns")
    .select("id, product_id")
    .eq("id", campaignId)
    .eq("organization_id", organizationId)
    .maybeSingle();
  if (!campaign) {
    return { error: "Campanha não encontrada nesta organização." };
  }
  const [{ data: product }, { data: queue }] = await Promise.all([
    supabase
      .from("products")
      .select("id, source_name")
      .eq("id", campaign.product_id)
      .eq("organization_id", organizationId)
      .maybeSingle(),
    supabase
      .from("queues")
      .select("id")
      .eq("id", queueId)
      .eq("organization_id", organizationId)
      .eq("is_active", true)
      .maybeSingle(),
  ]);
  if (!product || product.source_name !== "mercadolivre") {
    return { error: "Esta campanha não pertence ao Mercado Livre." };
  }
  if (!queue) {
    return { error: "A fila selecionada não existe ou está desativada." };
  }

  const { error } = await supabase.from("jobs").insert({
    organization_id: organizationId,
    type: "mercadolivre.link.ready",
    payload: {
      campaign_id: campaignId,
      affiliate_url: parsedLink.data,
      official_tool_confirmed: true,
      auto_approve: true,
      queue_id: queueId,
      agent: "hermes",
    },
  });
  if (error) {
    return { error: "Não foi possível entregar o link ao agente." };
  }

  revalidatePath(`/campanhas/${campaignId}`);
  revalidatePath("/filas");
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

  const orgId = await getOrgId(supabase);
  await supabase.from("audit_log").insert({
    organization_id: orgId,
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

async function getOrgId(
  supabase: Awaited<ReturnType<typeof createClient>>,
): Promise<string | null> {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return null;
  }
  const { data: profile } = await supabase
    .from("profiles")
    .select("organization_id")
    .eq("id", user.id)
    .single();
  return profile?.organization_id ?? null;
}

export async function saveChannelGroup(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }

  const name = String(formData.get("name") ?? "").trim();
  const telegramChatId = String(formData.get("telegram_chat_id") ?? "").trim();
  if (!name || !telegramChatId) {
    return { error: "Informe nome e chat_id do grupo." };
  }

  const { data: grupo, error } = await supabase
    .from("channel_groups")
    .insert({ organization_id: organizationId, name, telegram_chat_id: telegramChatId })
    .select("id")
    .single();

  if (error || !grupo) {
    return { error: "Não foi possível salvar o grupo. Verifique o chat_id (evite duplicar)." };
  }

  revalidatePath("/grupos");
  return { ok: true };
}

export async function deleteChannelGroup(groupId: string) {
  const supabase = await createClient();
  await supabase.from("channel_groups").delete().eq("id", groupId);
  revalidatePath("/grupos");
}

export async function sendGroupMessage(
  groupId: string,
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }
  const text = String(formData.get("text") ?? "").trim();
  if (!text) {
    return { error: "Escreva a mensagem antes de enviar." };
  }

  const { error: jobError } = await supabase.from("jobs").insert({
    organization_id: organizationId,
    type: "telegram.send",
    payload: { group_id: groupId, text },
  });

  if (jobError) {
    return { error: "Falha ao enfileirar o envio." };
  }
  return { ok: true };
}

export async function createQueue(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }

  const name = String(formData.get("name") ?? "").trim();
  const intervalMinutes = Number(formData.get("interval_minutes") ?? 5);
  const windowStart = String(formData.get("window_start") ?? "").trim() || null;
  const windowEnd = String(formData.get("window_end") ?? "").trim() || null;
  const groupIds = formData.getAll("group_ids").map(String);

  if (!name) {
    return { error: "Dê um nome para a fila." };
  }
  if (groupIds.length === 0) {
    return { error: "Selecione pelo menos um grupo de destino." };
  }
  if (!Number.isFinite(intervalMinutes) || intervalMinutes < 1 || intervalMinutes > 240) {
    return { error: "Intervalo deve estar entre 1 e 240 minutos." };
  }
  if ((windowStart && !windowEnd) || (!windowStart && windowEnd)) {
    return {
      error:
        "Preencha início e fim da janela ou deixe os dois em branco (24h).",
    };
  }

  const { data: fila, error } = await supabase
    .from("queues")
    .insert({
      organization_id: organizationId,
      name,
      interval_minutes: intervalMinutes,
      window_start: windowStart,
      window_end: windowEnd,
    })
    .select("id")
    .single();

  if (error || !fila) {
    return { error: "Não foi possível criar a fila." };
  }

  const linhas = groupIds.map((group_id) => ({
    queue_id: fila.id,
    group_id,
  }));
  const { error: gruposError } = await supabase.from("queue_groups").insert(linhas);
  if (gruposError) {
    return { error: "Fila criada, mas falha ao vincular os grupos." };
  }

  revalidatePath("/filas");
  return { ok: true };
}

export async function toggleQueue(queueId: string, isActive: boolean) {
  const supabase = await createClient();
  await supabase.from("queues").update({ is_active: isActive }).eq("id", queueId);
  revalidatePath("/filas");
}

export async function deleteQueue(queueId: string) {
  const supabase = await createClient();
  await supabase.from("queues").delete().eq("id", queueId);
  revalidatePath("/filas");
}

export async function updateQueueSourceMix(
  queueId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const mix = {
    shopee_target_percent: Number(formData.get("shopee") ?? 0),
    aliexpress_target_percent: Number(formData.get("aliexpress") ?? 0),
    mercadolivre_target_percent: Number(formData.get("mercadolivre") ?? 0),
    magalu_target_percent: Number(formData.get("magalu") ?? 0),
  };
  const values = Object.values(mix);
  if (values.some((value) => !Number.isInteger(value) || value < 0 || value > 100)) {
    return { error: "Use percentuais inteiros entre 0 e 100." };
  }
  if (values.reduce((sum, value) => sum + value, 0) !== 100) {
    return { error: "Os percentuais precisam somar exatamente 100%." };
  }

  const { error } = await supabase
    .from("queues")
    .update({ ...mix, updated_at: new Date().toISOString() })
    .eq("id", queueId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível salvar o mix da fila." };

  revalidatePath("/filas");
  revalidatePath("/");
  return { ok: true };
}

export async function forceQueueMixAlignment(
  queueId: string,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const { error } = await supabase.from("jobs").insert({
    organization_id: organizationId,
    type: "queue.force_align_mix",
    payload: { queue_id: queueId },
  });
  if (error) return { error: "Não foi possível enfileirar o ajuste do mix." };

  revalidatePath("/filas");
  return { ok: true };
}

export async function reorderQueueItems(
  queueId: string,
  orderedIds: string[],
): Promise<CampaignActionState> {
  const parsed = z.array(z.string().uuid()).min(1).max(200).safeParse(orderedIds);
  if (!parsed.success || new Set(parsed.data).size !== parsed.data.length) {
    return { error: "A ordem enviada é inválida. Recarregue a fila." };
  }
  const supabase = await createClient();
  if (!(await getOrgId(supabase))) {
    return { error: "Sessão expirada — entre novamente." };
  }
  const { error } = await supabase.rpc("reorder_queue_items", {
    p_queue_id: queueId,
    p_item_ids: parsed.data,
  });
  if (error) {
    return { error: "A fila mudou durante a edição. Recarregue e tente novamente." };
  }
  revalidatePath("/filas");
  revalidatePath("/");
  return { ok: true };
}

export async function setQueueManualOrder(
  queueId: string,
  enabled: boolean,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const { error } = await supabase
    .from("queues")
    .update({ manual_order_locked: enabled, updated_at: new Date().toISOString() })
    .eq("id", queueId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível alterar o modo de ordenação." };

  revalidatePath("/filas");
  return { ok: true };
}

export async function updateQueuedCampaignText(
  queueItemId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const title = String(formData.get("title") ?? "").trim();
  const copyText = String(formData.get("copy_text") ?? "").trim();
  if (title.length < 3 || title.length > 180) {
    return { error: "O título precisa ter entre 3 e 180 caracteres." };
  }
  if (copyText.length < 10 || copyText.length > 5000) {
    return { error: "A descrição precisa ter entre 10 e 5.000 caracteres." };
  }

  const { data: item } = await supabase
    .from("queue_items")
    .select("campaign_id, content_id, status")
    .eq("id", queueItemId)
    .eq("organization_id", organizationId)
    .maybeSingle();
  if (!item || item.status !== "PENDING" || !item.content_id) {
    return { error: "Esta campanha já saiu da fila ou não pode mais ser editada." };
  }

  const [{ error: campaignError }, { error: contentError }] = await Promise.all([
    supabase
      .from("campaigns")
      .update({ title, updated_at: new Date().toISOString() })
      .eq("id", item.campaign_id)
      .eq("organization_id", organizationId),
    supabase
      .from("contents")
      .update({ copy_text: copyText, updated_at: new Date().toISOString() })
      .eq("id", item.content_id)
      .eq("campaign_id", item.campaign_id),
  ]);
  if (campaignError || contentError) {
    return { error: "Não foi possível salvar o título e a descrição." };
  }

  revalidatePath("/filas");
  revalidatePath(`/campanhas/${item.campaign_id}`);
  return { ok: true };
}

export async function removeQueueItem(
  queueItemId: string,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const { data: item } = await supabase
    .from("queue_items")
    .select("campaign_id, queue_id, status")
    .eq("id", queueItemId)
    .eq("organization_id", organizationId)
    .maybeSingle();
  if (!item || item.status !== "PENDING") {
    return { error: "Esta campanha já saiu da fila e não pode ser removida." };
  }
  const { error } = await supabase
    .from("queue_items")
    .update({ status: "CANCELLED", error: null })
    .eq("id", queueItemId)
    .eq("status", "PENDING")
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível remover a campanha da fila." };

  const { count } = await supabase
    .from("queue_items")
    .select("id", { count: "exact", head: true })
    .eq("campaign_id", item.campaign_id)
    .in("status", ["PENDING", "DISPATCHED"]);
  if (!count) {
    await supabase
      .from("campaigns")
      .update({ status: "APPROVED", updated_at: new Date().toISOString() })
      .eq("id", item.campaign_id)
      .eq("organization_id", organizationId);
  }

  revalidatePath("/filas");
  revalidatePath("/");
  revalidatePath(`/campanhas/${item.campaign_id}`);
  return { ok: true };
}

export async function addToQueue(
  campaignId: string,
  contentId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }

  const queueId = String(formData.get("queue_id") ?? "").trim();
  const whenRaw = String(formData.get("when") ?? "").trim();
  if (!queueId) {
    return { error: "Selecione a fila." };
  }

  const scheduledAt = whenRaw
    ? new Date(whenRaw).toISOString()
    : new Date().toISOString();

  const { error } = await supabase.from("queue_items").insert({
    organization_id: organizationId,
    queue_id: queueId,
    campaign_id: campaignId,
    content_id: contentId,
    scheduled_at: scheduledAt,
  });

  if (error) {
    return { error: "Não foi possível adicionar à fila." };
  }

  await supabase.from("campaigns").update({ status: "SCHEDULED" }).eq("id", campaignId);
  revalidatePath(`/campanhas/${campaignId}`);
  revalidatePath("/filas");
  return { ok: true };
}

export async function publishNow(
  campaignId: string,
  contentId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }

  const groupId = String(formData.get("group_id") ?? "").trim();
  const chatId = String(formData.get("chat_id") ?? "").trim();
  if (!groupId && !chatId) {
    return { error: "Escolha o grupo de destino." };
  }

  let chatDestino: string | null = null;
  if (groupId) {
    const { data: grupo } = await supabase
      .from("channel_groups")
      .select("telegram_chat_id")
      .eq("id", groupId)
      .maybeSingle();
    chatDestino = grupo?.telegram_chat_id ?? null;
  } else {
    chatDestino = chatId;
  }
  if (!chatDestino) {
    return { error: "Grupo não encontrado." };
  }

  const whenRaw = String(formData.get("when") ?? "").trim();
  const scheduledFor = whenRaw
    ? new Date(whenRaw).toISOString()
    : new Date().toISOString();

  const { data: publication, error: pubError } = await supabase
    .from("publications")
    .insert({
      campaign_id: campaignId,
      content_id: contentId,
      channel: "telegram",
      mode: "production",
      status: "SCHEDULED",
      scheduled_at: scheduledFor,
      chat_id: chatDestino,
    })
    .select("id")
    .single();

  if (pubError || !publication) {
    return { error: "Não foi possível criar a publicação." };
  }

  const payload: Record<string, string> = {
    campaign_id: campaignId,
    content_id: contentId,
  };
  if (groupId) {
    payload.group_id = groupId;
  } else {
    payload.chat_id = chatDestino;
  }

  const { error: jobError } = await supabase.from("jobs").insert({
    organization_id: organizationId,
    type: "publication.telegram",
    payload,
    scheduled_for: scheduledFor,
  });

  if (jobError) {
    return { error: "Publicação criada, mas falha ao enfileirar o worker." };
  }

  await supabase.from("campaigns").update({ status: "SCHEDULED" }).eq("id", campaignId);
  revalidatePath(`/campanhas/${campaignId}`);
  return { ok: true };
}

export async function regenerateContents(
  campaignId: string,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }
  const { error } = await supabase.from("jobs").insert({
    organization_id: organizationId,
    type: "content.regenerate",
    payload: { campaign_id: campaignId },
  });
  if (error) {
    return { error: "Falha ao enfileirar a geração de textos." };
  }
  revalidatePath(`/campanhas/${campaignId}`);
  return { ok: true };
}

export async function updateCardConfig(
  productId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }
  const theme = String(formData.get("theme") ?? "navy");
  const border = String(formData.get("border") ?? "off") === "on";

  const { data: product, error: readError } = await supabase
    .from("products")
    .select("card_config")
    .eq("id", productId)
    .eq("organization_id", organizationId)
    .maybeSingle();
  if (readError || !product) {
    return { error: "Produto não encontrado nesta organização." };
  }
  const currentConfig =
    product.card_config && typeof product.card_config === "object"
      ? product.card_config
      : {};
  const { error } = await supabase
    .from("products")
    .update({ card_config: { ...currentConfig, theme, border } })
    .eq("id", productId)
    .eq("organization_id", organizationId);

  if (error) {
    return { error: "Não foi possível salvar o card." };
  }
  return { ok: true };
}

export async function saveCtaPhrase(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) {
    return { error: "Sessão expirada — entre novamente." };
  }

  const phrase = String(formData.get("phrase") ?? "").trim();
  if (!phrase) {
    return { error: "Escreva a frase do gatilho." };
  }

  const { error } = await supabase
    .from("cta_phrases")
    .insert({ organization_id: organizationId, phrase });

  if (error) {
    return { error: "Não foi possível salvar a frase." };
  }
  revalidatePath("/gatilhos");
  return { ok: true };
}

export async function deleteCtaPhrase(phraseId: string) {
  const supabase = await createClient();
  await supabase.from("cta_phrases").delete().eq("id", phraseId);
  revalidatePath("/gatilhos");
}

// ------------------------------------------------------------------
// Laboratório de Captura (/campanhas): curadoria de categorias,
// palavras-chave por fonte, corte de score e bloqueio de palavras que o
// worker lê a cada ciclo de descoberta (db.get_capture_lab_config).
// ------------------------------------------------------------------

const DISCOVERY_SOURCES = ["aliexpress", "shopee", "mercadolivre", "magalu"] as const;

const LOCK_DURATIONS_MS: Record<string, number> = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
};

function slugifyFamilyKey(label: string): string {
  return label
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export async function updateDiscoveryMinScore(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const minScore = Number(formData.get("min_score"));
  if (!Number.isFinite(minScore) || minScore < 0 || minScore > 100) {
    return { error: "O corte de score deve ficar entre 0 e 100." };
  }

  const { error } = await supabase.from("discovery_settings").upsert({
    organization_id: organizationId,
    min_score: minScore,
    updated_at: new Date().toISOString(),
  });
  if (error) return { error: "Não foi possível salvar o corte de score." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function upsertDiscoveryCategory(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const label = String(formData.get("label") ?? "").trim();
  if (label.length < 2 || label.length > 60) {
    return { error: "Dê um nome de 2 a 60 caracteres para a categoria." };
  }
  const familyKey = slugifyFamilyKey(label);
  if (!familyKey) {
    return { error: "Esse nome não gera uma identificação válida — use letras ou números." };
  }

  const { error } = await supabase.from("discovery_categories").upsert(
    { organization_id: organizationId, family_key: familyKey, label },
    { onConflict: "organization_id,family_key", ignoreDuplicates: true },
  );
  if (error) return { error: "Não foi possível adicionar a categoria." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function toggleDiscoveryCategory(
  categoryId: string,
  active: boolean,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const { error } = await supabase
    .from("discovery_categories")
    .update({ active })
    .eq("id", categoryId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível atualizar a categoria." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function setDiscoveryCategoryMinScore(
  categoryId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const raw = String(formData.get("min_score") ?? "").trim();
  const minScore = raw === "" ? null : Number(raw);
  if (minScore !== null && (!Number.isFinite(minScore) || minScore < 0 || minScore > 100)) {
    return { error: "O corte da categoria deve ficar entre 0 e 100 (ou em branco)." };
  }

  const { error } = await supabase
    .from("discovery_categories")
    .update({ min_score: minScore })
    .eq("id", categoryId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível salvar o corte da categoria." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function setDiscoveryCategoryTargetPercent(
  categoryId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const raw = String(formData.get("target_percent") ?? "").trim();
  const targetPercent = raw === "" ? null : Number(raw);
  if (
    targetPercent !== null &&
    (!Number.isInteger(targetPercent) || targetPercent < 0 || targetPercent > 100)
  ) {
    return { error: "A meta de distribuição deve ser um percentual inteiro entre 0 e 100." };
  }

  const { data: categories } = await supabase
    .from("discovery_categories")
    .select("id, target_percent")
    .eq("organization_id", organizationId);
  const otherTotal = (categories ?? [])
    .filter((row) => row.id !== categoryId)
    .reduce((sum, row) => sum + (row.target_percent ?? 0), 0);
  if (otherTotal + (targetPercent ?? 0) > 100) {
    return {
      error: `As metas por categoria já somam ${otherTotal}% nas demais — reduza antes de adicionar mais.`,
    };
  }

  const { error } = await supabase
    .from("discovery_categories")
    .update({ target_percent: targetPercent })
    .eq("id", categoryId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível salvar a meta de distribuição." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function forceCaptureCategoryRedistribution(): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const { data: categories } = await supabase
    .from("discovery_categories")
    .select("target_percent")
    .eq("organization_id", organizationId)
    .not("target_percent", "is", null);
  if (!categories || categories.length === 0) {
    return { error: "Defina ao menos uma meta de distribuição por categoria antes de aplicar." };
  }

  const { data: queues } = await supabase
    .from("queues")
    .select("id")
    .eq("organization_id", organizationId)
    .eq("is_active", true);
  if (!queues || queues.length === 0) {
    return { error: "Nenhuma fila ativa para redistribuir." };
  }

  const { error } = await supabase.from("jobs").insert(
    queues.map((queue) => ({
      organization_id: organizationId,
      type: "discovery.redistribute_categories",
      payload: { queue_id: queue.id },
    })),
  );
  if (error) return { error: "Não foi possível enfileirar a redistribuição." };

  revalidatePath("/campanhas");
  revalidatePath("/filas");
  return { ok: true };
}

export async function lockDiscoveryCategory(
  categoryId: string,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const duration = String(formData.get("duration") ?? "");
  const durationMs = LOCK_DURATIONS_MS[duration];
  if (!durationMs) {
    return { error: "Escolha por quanto tempo pausar a categoria." };
  }
  const reason = String(formData.get("reason") ?? "").trim() || null;
  const lockedUntil = new Date(Date.now() + durationMs).toISOString();

  const { error } = await supabase
    .from("discovery_categories")
    .update({ locked_until: lockedUntil, locked_reason: reason })
    .eq("id", categoryId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível travar a categoria." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function unlockDiscoveryCategory(
  categoryId: string,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const { error } = await supabase
    .from("discovery_categories")
    .update({ locked_until: null, locked_reason: null })
    .eq("id", categoryId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível reativar a categoria." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function addDiscoveryKeyword(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const sourceName = String(formData.get("source_name") ?? "");
  if (!DISCOVERY_SOURCES.includes(sourceName as (typeof DISCOVERY_SOURCES)[number])) {
    return { error: "Fonte inválida." };
  }
  const term = String(formData.get("term") ?? "").trim();
  if (term.length < 2 || term.length > 80) {
    return { error: "A palavra-chave precisa ter de 2 a 80 caracteres." };
  }

  const { error } = await supabase.from("discovery_keywords").upsert(
    { organization_id: organizationId, source_name: sourceName, term },
    { onConflict: "organization_id,source_name,term", ignoreDuplicates: true },
  );
  if (error) return { error: "Não foi possível adicionar a palavra-chave." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function toggleDiscoveryKeyword(
  keywordId: string,
  active: boolean,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const { error } = await supabase
    .from("discovery_keywords")
    .update({ active })
    .eq("id", keywordId)
    .eq("organization_id", organizationId);
  if (error) return { error: "Não foi possível atualizar a palavra-chave." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function removeDiscoveryKeyword(keywordId: string) {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return;
  await supabase
    .from("discovery_keywords")
    .delete()
    .eq("id", keywordId)
    .eq("organization_id", organizationId);
  revalidatePath("/campanhas");
}

export async function addDiscoveryBlockword(
  _prev: CampaignActionState,
  formData: FormData,
): Promise<CampaignActionState> {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return { error: "Sessão expirada — entre novamente." };

  const term = String(formData.get("term") ?? "").trim();
  if (term.length < 2 || term.length > 80) {
    return { error: "A palavra bloqueada precisa ter de 2 a 80 caracteres." };
  }
  const reason = String(formData.get("reason") ?? "").trim() || null;
  const isPermanent = String(formData.get("mode") ?? "permanent") === "permanent";

  let expiresAt: string | null = null;
  if (!isPermanent) {
    const duration = String(formData.get("duration") ?? "");
    const durationMs = LOCK_DURATIONS_MS[duration];
    if (!durationMs) {
      return { error: "Escolha por quanto tempo bloquear a palavra." };
    }
    expiresAt = new Date(Date.now() + durationMs).toISOString();
  }

  const { error } = await supabase.from("discovery_blocklist").insert({
    organization_id: organizationId,
    term,
    is_permanent: isPermanent,
    expires_at: expiresAt,
    reason,
  });
  if (error) return { error: "Não foi possível bloquear a palavra." };

  revalidatePath("/campanhas");
  return { ok: true };
}

export async function removeDiscoveryBlockword(blockId: string) {
  const supabase = await createClient();
  const organizationId = await getOrgId(supabase);
  if (!organizationId) return;
  await supabase
    .from("discovery_blocklist")
    .delete()
    .eq("id", blockId)
    .eq("organization_id", organizationId);
  revalidatePath("/campanhas");
}
