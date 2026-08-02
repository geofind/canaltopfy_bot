import { test, expect } from "@playwright/test";
import { E2E_USER } from "./fixtures";
import { adminClient } from "./admin";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.locator("#email").fill(E2E_USER.email);
  await page.locator("#password").fill(E2E_USER.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL("/");
});

test.describe("nova campanha", () => {
  test("criar campanha a partir de uma URL da AliExpress", async ({ page }) => {
    const url = `https://pt.aliexpress.com/item/e2e-${Date.now()}.html`;

    await page.goto("/campanhas/nova");
    await page.locator("#url").fill(url);
    await page
      .getByRole("button", { name: "Importar produto e criar campanha" })
      .click();

    await expect(page).toHaveURL("/campanhas");
    await expect(page.getByRole("cell", { name: "Nova campanha" }).first()).toBeVisible();

    // limpeza: apaga o produto criado neste teste (cascade apaga a campanha)
    await adminClient.from("products").delete().eq("source_url", url);
  });

  test("URL fora da AliExpress mostra erro de validação", async ({ page }) => {
    await page.goto("/campanhas/nova");
    await page.locator("#url").fill("https://www.amazon.com/dp/B000000000");
    await page
      .getByRole("button", { name: "Importar produto e criar campanha" })
      .click();

    await expect(
      page.getByText("Por enquanto aceitamos apenas URLs da AliExpress."),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/campanhas\/nova/);
  });
});
