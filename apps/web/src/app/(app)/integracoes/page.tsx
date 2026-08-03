import { createClient } from "@/lib/supabase/server";
import { connectMercadoLivre, disconnectMercadoLivre } from "@/lib/actions";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

type WorkerMetadata = {
  aliexpress_api_configured?: boolean;
  aliexpress_tracking_configured?: boolean;
  aliexpress_terms_shuffled?: boolean;
  search_terms_count?: number;
  shopee_api_configured?: boolean;
  shopee_discovery_enabled?: boolean;
  shopee_search_terms?: string[];
  shopee_terms_per_cycle?: number;
  shopee_cycle_minutes?: number;
  shopee_target_percent?: number;
  magalu_storefront_configured?: boolean;
  magalu_store_slug?: string;
  magalu_coupons_url?: string;
  magalu_target_percent?: number;
};

export default async function IntegracoesPage() {
  const supabase = await createClient();

  const [
    { data: mlCred },
    { data: ultimaPublicacao },
    { data: heartbeatRows },
    { count: aliProductCount },
    { data: ultimoProdutoAli },
    { count: shopeeProductCount },
    { data: ultimoProdutoShopee },
    { count: magaluProductCount },
    { data: ultimoProdutoMagalu },
  ] = await Promise.all([
    supabase.from("ml_credentials").select("*").maybeSingle(),
    supabase
      .from("publications")
      .select("created_at, external_message_id, channel, campaign_id")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("audit_log")
      .select("created_at, metadata")
      .eq("action", "worker_heartbeat")
      .order("created_at", { ascending: false })
      .limit(1),
    supabase
      .from("products")
      .select("id", { count: "exact", head: true })
      .eq("source_name", "aliexpress"),
    supabase
      .from("products")
      .select("collected_at, created_at")
      .eq("source_name", "aliexpress")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("products")
      .select("id", { count: "exact", head: true })
      .eq("source_name", "shopee"),
    supabase
      .from("products")
      .select("collected_at, created_at")
      .eq("source_name", "shopee")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("products")
      .select("id", { count: "exact", head: true })
      .eq("source_name", "magalu"),
    supabase
      .from("products")
      .select("collected_at, created_at")
      .eq("source_name", "magalu")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
  ]);

  const mlConectado = Boolean(mlCred);
  const mlExpirado =
    mlCred && mlCred.expires_at && new Date(mlCred.expires_at) <= new Date();

  const heartbeat = heartbeatRows?.[0] ?? null;
  const workerMetadata = (heartbeat?.metadata ?? {}) as WorkerMetadata;
  // eslint-disable-next-line react-hooks/purity -- Server Component: calculado uma vez por requisição.
  const agora = Date.now();
  const workerOnline = Boolean(
    heartbeat && agora - new Date(heartbeat.created_at).getTime() <= 12 * 60_000,
  );
  const aliApiConfigurada = workerMetadata.aliexpress_api_configured === true;
  const aliTrackingConfigurado =
    workerMetadata.aliexpress_tracking_configured === true;
  const aliAtivo = workerOnline && aliApiConfigurada && aliTrackingConfigurado;
  const ultimaCapturaAli =
    ultimoProdutoAli?.collected_at ?? ultimoProdutoAli?.created_at ?? null;
  const shopeeConfigurada = workerMetadata.shopee_api_configured === true;
  const shopeeAtiva = workerOnline && shopeeConfigurada;
  const ultimaCapturaShopee =
    ultimoProdutoShopee?.collected_at ?? ultimoProdutoShopee?.created_at ?? null;
  const magaluConfigurada = workerMetadata.magalu_storefront_configured === true;
  const magaluAtiva = workerOnline && magaluConfigurada;
  const magaluSlug = workerMetadata.magalu_store_slug || "canaltopfy";
  const magaluStoreKey = magaluSlug.startsWith("magazine")
    ? magaluSlug
    : `magazine${magaluSlug}`;
  const magaluStorefrontUrl = `https://www.magazinevoce.com.br/${magaluStoreKey}/`;
  const magaluCouponsUrl =
    workerMetadata.magalu_coupons_url ||
    `https://especiais.magazineluiza.com.br/magazinevoce/cupons/?showcase=${magaluStoreKey}`;
  const ultimaCapturaMagalu =
    ultimoProdutoMagalu?.collected_at ?? ultimoProdutoMagalu?.created_at ?? null;

  const telegramUsername = process.env.TELEGRAM_BOT_USERNAME;
  const telegramChatId = process.env.TELEGRAM_CHAT_ID;

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <p className="eyebrow">Conexões</p>
        <h1 className="text-2xl font-semibold tracking-tight">Integrações</h1>
        <p className="text-sm text-muted-foreground">
          Conexões usadas pelo pipeline de importação e publicação.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mercado Livre</CardTitle>
          <CardDescription>
            Importação manual de produtos com seu código de afiliado.
            Automação de importação é proibida pela plataforma — o conector
            registra o código no link e busca dados públicos do anúncio.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            {mlConectado ? (
              <Badge variant={mlExpirado ? "destructive" : "secondary"}>
                {mlExpirado ? "Conectado (token expirado)" : "Conectado"}
              </Badge>
            ) : (
              <Badge variant="outline">Não conectado</Badge>
            )}
            {mlCred?.expires_at && (
              <span className="text-sm text-muted-foreground">
                Token expira em{" "}
                {new Date(mlCred.expires_at).toLocaleString("pt-BR")}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <form action={connectMercadoLivre}>
              <button
                type="submit"
                className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                {mlConectado ? "Reconectar" : "Conectar"}
              </button>
            </form>
            {mlConectado && (
              <form action={disconnectMercadoLivre}>
                <button
                  type="submit"
                  className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-4 text-sm font-medium text-destructive transition-colors hover:bg-muted"
                >
                  Desconectar
                </button>
              </form>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AliExpress</CardTitle>
          <CardDescription>
            Captura automática pela Affiliate API oficial, com geração de link
            rastreado, termos embaralhados, score e deduplicação antes de entrar
            na fila de publicação.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            {aliAtivo ? (
              <Badge variant="secondary">Conectado e ativo</Badge>
            ) : aliApiConfigurada || aliTrackingConfigurado ? (
              <Badge variant="outline">Configuração incompleta</Badge>
            ) : (
              <Badge variant="destructive">Não configurado no worker</Badge>
            )}
            <span className="text-sm text-muted-foreground">
              {workerOnline ? "Worker online" : "Worker sem telemetria recente"}
            </span>
          </div>

          <div className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">API oficial</p>
              <p className="font-medium">
                {aliApiConfigurada ? "Configurada" : "Pendente"}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Tracking</p>
              <p className="font-medium">
                {aliTrackingConfigurado ? "Configurado" : "Pendente"}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">
                Termos ativos
              </p>
              <p className="font-medium">
                {Number(workerMetadata.search_terms_count ?? 0)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">
                Produtos capturados
              </p>
              <p className="font-medium">{aliProductCount ?? 0}</p>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">
            {ultimaCapturaAli
              ? `Última captura: ${new Date(ultimaCapturaAli).toLocaleString("pt-BR")}`
              : "Nenhuma captura registrada."}
            {workerMetadata.aliexpress_terms_shuffled
              ? " · Termos embaralhados a cada reposição."
              : ""}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Shopee</CardTitle>
          <CardDescription>
            Integrada ao mesmo fluxo de score, deduplicação, diversidade,
            copy, fila e Telegram. Catálogo e shortlinks vêm da Affiliate
            Open API oficial, sem scraping.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            {shopeeAtiva ? (
              <Badge variant="secondary">Conectada ao worker</Badge>
            ) : shopeeConfigurada ? (
              <Badge variant="outline">Configurada; worker offline</Badge>
            ) : (
              <Badge variant="destructive">Não configurada no worker</Badge>
            )}
            <span className="text-sm text-muted-foreground">
              Meta no mix: {Number(workerMetadata.shopee_target_percent ?? 50)}%
            </span>
          </div>
          <div className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">API oficial</p>
              <p className="font-medium">{shopeeConfigurada ? "Configurada" : "Pendente"}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Ciclo</p>
              <p className="font-medium">{Number(workerMetadata.shopee_cycle_minutes ?? 5)} min</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Termos por ciclo</p>
              <p className="font-medium">{Number(workerMetadata.shopee_terms_per_cycle ?? 3)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Produtos capturados</p>
              <p className="font-medium">{shopeeProductCount ?? 0}</p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            {ultimaCapturaShopee
              ? `Última captura: ${new Date(ultimaCapturaShopee).toLocaleString("pt-BR")}`
              : "Nenhuma captura registrada."}
            {workerMetadata.shopee_discovery_enabled
              ? " · Descoberta dedicada ativa."
              : " · Integrada ao reabastecedor atual."}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Magalu</CardTitle>
          <CardDescription>
            Integração pelo Influenciador Magalu / Magazine Você. A atribuição
            de afiliado é feita pela vitrine oficial; as APIs OAuth do Magalu
            Devs são voltadas a sellers e não geram comissão de influenciador.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            {magaluAtiva ? (
              <Badge variant="secondary">Conectada pela vitrine</Badge>
            ) : magaluConfigurada ? (
              <Badge variant="outline">Vitrine configurada; worker offline</Badge>
            ) : (
              <Badge variant="destructive">Vitrine não configurada</Badge>
            )}
            <span className="text-sm text-muted-foreground">
              Meta no mix: {Number(workerMetadata.magalu_target_percent ?? 20)}%
            </span>
          </div>

          <div className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Vitrine</p>
              <p className="font-medium">{magaluStoreKey}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Atribuição</p>
              <p className="font-medium">Link Magazine Você</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Cupons</p>
              <p className="font-medium">Página oficial vinculada</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Produtos capturados</p>
              <p className="font-medium">{magaluProductCount ?? 0}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <a
              href={magaluStorefrontUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Abrir minha vitrine
            </a>
            <a
              href={magaluCouponsUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-4 text-sm font-medium transition-colors hover:bg-muted"
            >
              Ver cupons Magalu
            </a>
          </div>

          <p className="text-sm text-muted-foreground">
            {ultimaCapturaMagalu
              ? `Última captura: ${new Date(ultimaCapturaMagalu).toLocaleString("pt-BR")}`
              : "Nenhum produto Magalu importado ainda."}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Telegram</CardTitle>
          <CardDescription>
            Publicação das ofertas no canal/grupo via bot. O worker busca
            campanhas agendadas e envia a foto + texto do anúncio.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 text-sm sm:grid-cols-2">
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">Bot</p>
              <p className="font-medium">{telegramUsername || "—"}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase text-muted-foreground">
                Chat (grupo/canal)
              </p>
              <p className="font-medium">{telegramChatId || "—"}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {telegramUsername && telegramChatId ? (
              <Badge variant="secondary">Configurado</Badge>
            ) : (
              <Badge variant="destructive">Faltando env vars</Badge>
            )}
            {ultimaPublicacao && (
              <span className="text-sm text-muted-foreground">
                Última publicação:{" "}
                {new Date(ultimaPublicacao.created_at).toLocaleString("pt-BR")}
                {ultimaPublicacao.external_message_id
                  ? ` (mensagem ${ultimaPublicacao.external_message_id})`
                  : ""}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
