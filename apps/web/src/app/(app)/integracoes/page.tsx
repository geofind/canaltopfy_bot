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

export default async function IntegracoesPage() {
  const supabase = await createClient();

  const { data: mlCred } = await supabase
    .from("ml_credentials")
    .select("*")
    .maybeSingle();
  const mlConectado = Boolean(mlCred);
  const mlExpirado =
    mlCred && mlCred.expires_at && new Date(mlCred.expires_at) <= new Date();

  const { data: ultimaPublicacao } = await supabase
    .from("publications")
    .select("created_at, external_message_id, channel, campaign_id")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

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
