import Link from "next/link";
import { NewCampaignForm } from "@/components/app/new-campaign-form";
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
    <div className="mx-auto max-w-lg space-y-6">
      <div className="space-y-1">
        <Link
          href="/campanhas"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Campanhas
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">
          Nova campanha
        </h1>
        <p className="eyebrow">Importação manual</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Importar produto</CardTitle>
          <CardDescription>
            Cole a URL do produto. O pipeline executa: extração → link de
            afiliado → Topfy Score → cópias → revisão.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <NewCampaignForm initialUrl={url ?? ""} />
        </CardContent>
      </Card>
    </div>
  );
}
