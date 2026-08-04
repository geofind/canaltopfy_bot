import { createClient } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/app/page-header";
import { ChannelGroupForm, GroupMessageForm } from "@/components/app/divulgacao-forms";
import { deleteChannelGroup } from "@/lib/actions";

export const dynamic = "force-dynamic";

export default async function GruposPage() {
  const supabase = await createClient();

  const { data: grupos } = await supabase
    .from("channel_groups")
    .select("*")
    .order("name");

  const { data: publicacoes } = await supabase
    .from("publications")
    .select("chat_id, status, created_at")
    .eq("channel", "telegram")
    .order("created_at", { ascending: false })
    .limit(10);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Divulgação"
        title="Grupos"
        description="Canais e grupos do Telegram onde as ofertas são publicadas. Cadastre uma vez e reutilize em filas, agendamentos e disparos manuais."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <h2 className="text-lg font-bold">Grupos cadastrados</h2>
          {!grupos || grupos.length === 0 ? (
            <Card className="shadow-soft-sm">
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                Nenhum grupo cadastrado ainda. Use o formulário ao lado para
                adicionar o primeiro (ex.: o grupo principal{" "}
                <code className="rounded bg-muted px-1">-1004362453366</code>).
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {grupos.map((grupo) => (
                <Card key={grupo.id} className="shadow-soft-sm">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0">
                    <div>
                      <CardTitle className="text-sm">{grupo.name}</CardTitle>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {grupo.telegram_chat_id}
                        {grupo.telegram_chat_title
                          ? ` · ${grupo.telegram_chat_title}`
                          : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {grupo.is_active ? (
                        <Badge>Ativo</Badge>
                      ) : (
                        <Badge variant="secondary">Inativo</Badge>
                      )}
                      <form action={deleteChannelGroup.bind(null, grupo.id)}>
                        <button
                          type="submit"
                          className="rounded-md border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        >
                          Remover
                        </button>
                      </form>
                    </div>
                  </CardHeader>
                  <CardContent className="border-t pt-4">
                    <p className="mb-2 text-xs font-medium text-muted-foreground">
                      Testar conexão — envia uma mensagem real para este grupo
                    </p>
                    <GroupMessageForm
                      grupo={{
                        id: grupo.id,
                        name: grupo.name,
                        telegram_chat_id: grupo.telegram_chat_id,
                      }}
                    />
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Card className="shadow-soft-sm">
            <CardHeader>
              <CardTitle className="text-sm">Cadastrar grupo</CardTitle>
            </CardHeader>
            <CardContent>
              <ChannelGroupForm />
            </CardContent>
          </Card>

          <Card className="shadow-soft-sm">
            <CardHeader>
              <CardTitle className="text-sm">Últimos envios</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {!publicacoes || publicacoes.length === 0 ? (
                <p className="text-muted-foreground">
                  Nenhuma publicação registrada ainda.
                </p>
              ) : (
                publicacoes.map((pub, i) => (
                  <div key={i} className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs">
                      {pub.chat_id ?? "—"}
                    </span>
                    <Badge variant={pub.status === "PUBLISHED" ? "default" : "secondary"}>
                      {pub.status}
                    </Badge>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
