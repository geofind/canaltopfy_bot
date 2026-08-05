const MARKETPLACE: Record<string, { src: string; label: string }> = {
  aliexpress: { src: "/brand/marketplaces/aliexpress.svg", label: "AliExpress" },
  shopee: { src: "/brand/marketplaces/shopee.svg", label: "Shopee" },
  mercadolivre: { src: "/brand/marketplaces/mercadolivre.svg", label: "Mercado Livre" },
  mercadolibre: { src: "/brand/marketplaces/mercadolivre.svg", label: "Mercado Livre" },
  magalu: { src: "/brand/marketplaces/magalu.svg", label: "Magalu" },
  amazon: { src: "/brand/marketplaces/amazon.svg", label: "Amazon" },
};

/** Nome de exibição do marketplace — única fonte de verdade (antes havia
 * LOJA_LABEL/sourceLabel duplicados e divergentes por página, alguns sem
 * "magalu" cadastrado). */
export function marketplaceLabel(source: string | null | undefined): string {
  if (!source) return "Loja parceira";
  return MARKETPLACE[source]?.label ?? source;
}

type MarketplaceLogoProps = {
  source: string | null | undefined;
  size?: number;
  className?: string;
};

/** Mini logotipo do marketplace de origem do produto. Sem marketplace
 * reconhecido, devolve um espaço reservado neutro em vez de quebrar o
 * layout — nunca inventa uma marca. */
export function MarketplaceLogo({
  source,
  size = 20,
  className = "rounded-md",
}: MarketplaceLogoProps) {
  const info = source ? MARKETPLACE[source] : undefined;
  if (!info) {
    return (
      <span
        className={`inline-block shrink-0 bg-muted ${className}`}
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={info.src}
      alt={info.label}
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
    />
  );
}
