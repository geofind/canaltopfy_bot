import { test, expect } from "@playwright/test";

test.describe("vitrine pública (sem sessão)", () => {
  test("slug inexistente devolve 404", async ({ page }) => {
    const res = await page.goto("/c/slug-que-nao-existe-e2e");
    expect(res?.status()).toBe(404);
  });

  test("card com id inexistente devolve 404", async ({ request }) => {
    const res = await request.get(
      "/og/card/00000000-0000-0000-0000-000000000000",
    );
    expect(res.status()).toBe(404);
  });

  test("redirect /r/<id> inexistente manda para / (nunca para link bruto)", async ({
    request,
  }) => {
    const res = await request.get("/r/00000000-0000-0000-0000-000000000000", {
      maxRedirects: 0,
    });
    expect(res.status()).toBe(302);
    expect(new URL(res.headers()["location"]).pathname).toBe("/");
  });
});
