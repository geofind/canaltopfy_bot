"use client";

import { useActionState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  approveCampaignContent,
  schedulePublication,
  type CampaignActionState,
} from "@/lib/actions";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";

const initialState: CampaignActionState = {};

export function ApproveContentButton({
  campaignId,
  contentId,
  disabled,
}: {
  campaignId: string;
  contentId: string;
  disabled: boolean;
}) {
  const [state, formAction, pending] = useActionState(
    () => approveCampaignContent(campaignId, contentId),
    initialState,
  );
  return (
    <form action={formAction}>
      {state.error && (
        <Alert variant="destructive">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      <Button type="submit" disabled={pending || disabled} size="sm">
        {pending ? "Aprovando…" : "Aprovar esta cópia"}
      </Button>
    </form>
  );
}

export function SchedulePublicationForm({
  campaignId,
  contentId,
  canPublish,
}: {
  campaignId: string;
  contentId: string;
  canPublish: boolean;
}) {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(
    (prev: CampaignActionState, fd: FormData) =>
      schedulePublication(campaignId, contentId, fd),
    initialState,
  );

  useEffect(() => {
    if (state.ok) {
      router.refresh();
    }
  }, [state.ok, router]);

  return (
    <form action={formAction} className="space-y-3">
      {state.error && (
        <Alert variant="destructive">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-2">
        <label htmlFor="chat_id" className="text-sm font-medium leading-none">
          chat_id do Telegram (canal/grupo)
        </label>
        <input
          id="chat_id"
          name="chat_id"
          placeholder="@seuduacanal ou -1001234567890"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <p className="text-xs text-muted-foreground">
          Publicação real no Telegram exige TELEGRAM_BOT_TOKEN configurado no
          worker. O CTA sempre aponta para o redirect first-party /r/&lt;id&gt;.
        </p>
      </div>
      <Button type="submit" disabled={pending || !canPublish}>
        {pending ? "Agendando…" : "Agendar publicação no Telegram"}
      </Button>
    </form>
  );
}
