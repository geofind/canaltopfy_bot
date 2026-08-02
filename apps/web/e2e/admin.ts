import path from "node:path";
import { loadEnvConfig } from "@next/env";
import { createClient } from "@supabase/supabase-js";

loadEnvConfig(path.resolve(__dirname, "../../.."));

// Cliente service_role para setup/limpeza de dados nos testes — nunca
// usado para exercitar o app em si (isso é sempre via UI/Playwright page).
export const adminClient = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { autoRefreshToken: false, persistSession: false } },
);
