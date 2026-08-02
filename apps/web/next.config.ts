import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

loadEnvConfig(path.resolve(__dirname, "../.."));

const nextConfig: NextConfig = {
  // loadEnvConfig acima só populou o processo Node principal — o
  // middleware roda no Edge runtime e só recebe env var que o Next
  // embute em build-time via este campo (webpack/turbopack DefinePlugin).
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  },
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
