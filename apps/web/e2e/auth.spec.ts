import { test, expect } from "@playwright/test";
import { E2E_USER } from "./fixtures";

test.describe("autenticação", () => {
  test("login com credenciais válidas leva ao dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill(E2E_USER.email);
    await page.locator("#password").fill(E2E_USER.password);
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).toHaveURL("/");
  });

  test("login com senha errada mostra erro e permanece em /login", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill(E2E_USER.email);
    await page.locator("#password").fill("senha-errada-123");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page.getByText("E-mail ou senha inválidos.")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("acessar rota autenticada sem sessão redireciona para /login", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/campanhas");
    await expect(page).toHaveURL(/\/login/);
  });
});
