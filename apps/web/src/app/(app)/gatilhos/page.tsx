import { createClient } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/app/page-header";
import { CtaPhraseForm } from "@/components/app/divulgacao-forms";
import { deleteCtaPhrase } from "@/lib/actions";

export const dynamic = "force-dynamic";

export default async function GatilhosPage() {
  const supabase = await createClient();

  const { data: frases } = await supabase
    .from("cta_phrases")
    .select("*")
    .order("created_at");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Divulgação"
        title="Gatilhos"
        description="Frases de chamada para ação (CTA) sorteadas pelo worker em cada publicação. Sem nenhuma cadastrada, o sistema usa as 3 variações padrão."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <h2 className="text-lg font-bold">Frases cadastradas</h2>
          {!frases || frases.length === 0 ? (
            <Card className="shadow-soft-sm">
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                Nenhuma frase ainda — as publicações usam as variações padrão
                (&quot;Ver oferta&quot;, &quot;Conferir na loja&quot;, &quot;Ver
                oferta na loja&quot;).
              </CardContent>
            </Card>
          ) : (
            <div className="overflow-hidden rounded-xl border bg-white shadow-soft-sm">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Frase</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {frases.map((frase) => (
                    <tr key={frase.id} className="hover:bg-muted/50">
                      <td className="px-4 py-3">{frase.phrase}</td>
                      <td className="px-4 py-3">
                        {frase.is_active ? (
                          <Badge>Ativa</Badge>
                        ) : (
                          <Badge variant="secondary">Inativa</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <form action={deleteCtaPhrase.bind(null, frase.id)}>
                          <button
                            type="submit"
                            className="rounded-md border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                          >
                            Remover
                          </button>
                        </form>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Card className="shadow-soft-sm">
            <CardHeader>
              <CardTitle className="text-sm">Nova frase</CardTitle>
            </CardHeader>
            <CardContent>
              <CtaPhraseForm />
            </CardContent>
          </Card>
          <Card className="shadow-soft-sm">
            <CardHeader>
              <CardTitle className="text-sm">Boas práticas</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                Use chamadas diretas e honestas: &quot;Desconto confirmado na
                loja&quot;, &quot;Confira o preço oficial&quot;, &quot;Aproveite
                enquanto está neste valor&quot;.
              </p>
              <p>
                Frases com urgência falsa ou estoque falso são bloqueadas pela
                validação do worker.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
