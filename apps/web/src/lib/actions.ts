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
    url.includes("amazon.") || url.includes("amzn."),
  {
    message:
      "Por enquanto aceitamos URLs da AliExpress, Mercado Livre (inclusive links curtos meli.la) ou Amazon (amzn.to também).",
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
  const theme = String(formData.get("theme") ?? "navy");
  const border = String(formData.get("border") ?? "off") === "on";

  const { error } = await supabase
    .from("products")
    .update({ card_config: { theme, border } })
    .eq("id", productId);

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
