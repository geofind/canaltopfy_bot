// Usuário fixo de teste, provisionado (idempotente) por global-setup.ts
// via Supabase Admin API — nunca passa pelo formulário de signup, então
// não depende de confirmação de e-mail.
export const E2E_USER = {
  email: "e2e-topfy@example.com",
  password: "e2e-teste-topfy-12345",
};
