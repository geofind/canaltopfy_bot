"use client";

import { useActionState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  createCampaignFromUrl,
  type CampaignActionState,
} from "@/lib/actions";
import { Alert, AlertDescription } from "@/components/ui/alert";

const initialState: CampaignActionState = {};

export function NewCampaignForm() {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(
    createCampaignFromUrl,
    initialState,
  );

  useEffect(() => {
    if (state.ok) {
      router.push("/campanhas");
    }
  }, [state.ok, router]);

  return (
    <form action={formAction} className="space-y-4">
      {state.error && (
        <Alert variant="destructive">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <label
          htmlFor="url"
          className="text-sm font-medium leading-none"
        >
          URL do produto
        </label>
        <input
          id="url"
          name="url"
          type="url"
          required
          placeholder="https://pt.aliexpress.com/item/10050012345.html"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        />
        <p className="text-xs text-muted-foreground">
          No MVP aceitamos produtos da AliExpress. O worker extrai os dados
          via API oficial e calcula o Topfy Score.
        </p>
      </div>

      <button
        type="submit"
        disabled={pending}
        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
      >
        {pending ? "Importando…" : "Importar produto e criar campanha"}
      </button>
    </form>
  );
}
