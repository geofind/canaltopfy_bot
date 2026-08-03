export type CommissionProduct = {
  discounted_price_brl?: number | null;
  commission_pct?: number | null;
  commission_brl?: number | null;
};

export function comissaoEstimadaPorUnidade(
  product: CommissionProduct | CommissionProduct[] | null | undefined,
): number | null {
  const row = Array.isArray(product) ? product[0] ?? null : product;
  if (!row) return null;
  const preco = Number(row.discounted_price_brl);
  const pct = Number(row.commission_pct);
  if (row.commission_brl != null) {
    const comissaoFixa = Number(row.commission_brl);
    if (Number.isFinite(comissaoFixa) && comissaoFixa > 0) return comissaoFixa;
  }
  if (!Number.isFinite(preco) || preco <= 0 || !Number.isFinite(pct) || pct <= 0) {
    return null;
  }
  return (preco * pct) / 100;
}

export function formatMoneyBRL(value: number | null): string {
  return value == null ? "—" : `R$ ${value.toFixed(2)}`;
}