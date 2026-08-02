import path from "node:path";
import { loadEnvConfig } from "@next/env";
import { createClient } from "@supabase/supabase-js";
import { E2E_USER } from "./fixtures";

// Provisiona o usuário/organização de teste direto via Admin API
// (service_role) — evita depender do formulário de signup e de
// confirmação de e-mail. Idempotente: roda em toda suíte, só cria o
// que ainda não existe.
export default async function globalSetup() {
  loadEnvConfig(path.resolve(__dirname, "../../.."));

  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error(
      "e2e global-setup: defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env da raiz.",
    );
  }

  const admin = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data: existing, error: listError } = await admin.auth.admin.listUsers();
  if (listError) {
    throw new Error(`e2e global-setup: falha ao listar usuários: ${listError.message}`);
  }

  let userId = existing.users.find((u) => u.email === E2E_USER.email)?.id;

  if (!userId) {
    const { data: created, error: createError } = await admin.auth.admin.createUser({
      email: E2E_USER.email,
      password: E2E_USER.password,
      email_confirm: true,
    });
    if (createError || !created.user) {
      throw new Error(
        `e2e global-setup: falha ao criar usuário de teste: ${createError?.message}`,
      );
    }
    userId = created.user.id;
  }

  const { data: profile } = await admin
    .from("profiles")
    .select("organization_id")
    .eq("id", userId)
    .maybeSingle();

  if (!profile) {
    const { data: org, error: orgError } = await admin
      .from("organizations")
      .insert({ name: "E2E Test Org", slug: `e2e-org-${userId}` })
      .select()
      .single();
    if (orgError || !org) {
      throw new Error(`e2e global-setup: falha ao criar organização: ${orgError?.message}`);
    }
    const { error: profileError } = await admin.from("profiles").insert({
      id: userId,
      organization_id: org.id,
      full_name: "E2E Test",
      role: "owner",
    });
    if (profileError) {
      throw new Error(`e2e global-setup: falha ao criar profile: ${profileError.message}`);
    }
  }
}
