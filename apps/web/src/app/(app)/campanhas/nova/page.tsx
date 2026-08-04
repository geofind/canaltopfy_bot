import { NewCampaignForm } from "@/components/app/new-campaign-form";
import { PageHeader } from "@/components/app/page-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default async function NewCampaignPage({
  searchParams,
}: {
  searchParams: Promise<{ url?: string }>;
}) {
  const { url } = await searchParams;
  return (
    <div className="mx-auto max-w-lg space-y-8">
      <PageHeader
        eyebrow="Importação manual"
        title="Nova campanha"
        description="Cole a URL do produto. O pipeline executa: extração → link de afiliado → Topfy Score → cópias → revisão."
        backHref="/campanhas"
        backLabel="Campanhas"
      />

      <Card>
        <CardHeader>
          <CardTitle>Importar produto</CardTitle>
          <CardDescription>
            O link de afiliado é adicionado automaticamente quando a fonte
            suporta rastreamento.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <NewCampaignForm initialUrl={url ?? ""} />
        </CardContent>
      </Card>
    </div>
  );
}
