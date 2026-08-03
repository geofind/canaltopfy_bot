"use client";

import { useActionState, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  approveCampaignContent,
  publishNow,
  addToQueue,
  regenerateContents,
  updateCardConfig,
  completeMercadoLivreAutomation,
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

export type ChannelGroupOption = {
  id: string;
  name: string;
  telegram_chat_id: string;
};

export type QueueOption = { id: string; name: string };

const inputClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function MercadoLivreAutomationForm({
  campaignId,
  filas,
}: {
  campaignId: string;
  filas: QueueOption[];
}) {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(
    (prev: CampaignActionState, fd: FormData) =>
      completeMercadoLivreAutomation(campaignId, prev, fd),
    initialState,
  );

  useEffect(() => {
    if (state.ok) {
      router.refresh();
    }
  }, [state.ok, router]);

  return (
    <form action={formAction} className="space-y-4">
      {state.error && (
        <Alert variant="destructive">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      {state.ok && (
        <Alert>
          <AlertDescription>
            Link entregue. O worker vai gerar a copy, aprovar e enviar para a fila.
          </AlertDescription>
        </Alert>
      )}
      <div className="space-y-2">
        <label htmlFor="affiliate_url" className="text-sm font-medium leading-none">
          Link criado pelo Hermes no Gerador oficial
        </label>
        <input
          id="affiliate_url"
          name="affiliate_url"
          type="url"
          required
          placeholder="https://meli.la/..."
          className={inputClass}
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="ml_queue_id" className="text-sm font-medium leading-none">
          Fila automática do Telegram
        </label>
        <select
          id="ml_queue_id"
          name="queue_id"
          required
          defaultValue=""
          className={inputClass}
        >
          <option value="" disabled>Selecione a fila…</option>
          {filas.map((fila) => (
            <option key={fila.id} value={fila.id}>{fila.name}</option>
          ))}
        </select>
      </div>
      <div className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs text-muted-foreground">
        Modo automático: sem aprovação humana. O agente valida o link, gera a
        copy, aprova a primeira versão válida e agenda a publicação. Links
        duplicados ou campanhas já publicadas são bloqueados.
      </div>
      <Button type="submit" disabled={pending || filas.length === 0}>
        {pending ? "Entregando ao agente…" : "Continuar e publicar automaticamente"}
      </Button>
    </form>
  );
}

export function SchedulePublicationForm({
  campaignId,
  contentId,
  canPublish,
  defaultChatId,
  grupos,
  filas,
}: {
  campaignId: string;
  contentId: string;
  canPublish: boolean;
  defaultChatId?: string;
  grupos: ChannelGroupOption[];
  filas: QueueOption[];
}) {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(
    (prev: CampaignActionState, fd: FormData) =>
      publishNow(campaignId, contentId, fd),
    initialState,
  );
  const [queueState, queueAction, queuePending] = useActionState(
    (prev: CampaignActionState, fd: FormData) =>
      addToQueue(campaignId, contentId, fd),
    initialState,
  );

  useEffect(() => {
    if (state.ok || queueState.ok) {
      router.refresh();
    }
  }, [state.ok, queueState.ok, router]);

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium leading-none">Publicar agora ou agendar</p>
        <form action={formAction} className="mt-3 space-y-3">
          {state.error && (
            <Alert variant="destructive">
              <AlertDescription>{state.error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <label htmlFor="group_id" className="text-sm font-medium leading-none">
              Grupo de destino
            </label>
            <select
              id="group_id"
              name="group_id"
              required
              className={inputClass}
              defaultValue=""
            >
              <option value="" disabled>
                Selecione um grupo cadastrado…
              </option>
              {grupos.map((grupo) => (
                <option key={grupo.id} value={grupo.id}>
                  {grupo.name} ({grupo.telegram_chat_id})
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Sem grupos cadastrados? Cadastre em{" "}
              <a href="/grupos" className="text-primary underline">
                Grupos
              </a>{" "}
              ou informe o chat_id do grupo padrão (
              {defaultChatId || "TELEGRAM_CHAT_ID"}).
            </p>
          </div>
          <div className="space-y-2">
            <label htmlFor="when" className="text-sm font-medium leading-none">
              Quando (deixe vazio para disparar agora)
            </label>
            <input
              id="when"
              name="when"
              type="datetime-local"
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">
              O horário é do seu fuso local; o worker dispara no momento
              marcado.
            </p>
          </div>
          <Button type="submit" disabled={pending || !canPublish}>
            {pending ? "Agendando…" : "Disparar no Telegram"}
          </Button>
        </form>
      </div>

      {filas.length > 0 && (
        <div className="border-t border-border pt-4">
          <p className="text-sm font-medium leading-none">Adicionar à fila</p>
          <form action={queueAction} className="mt-3 space-y-3">
            {queueState.error && (
              <Alert variant="destructive">
                <AlertDescription>{queueState.error}</AlertDescription>
              </Alert>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="queue_id" className="text-sm font-medium leading-none">
                  Fila
                </label>
                <select
                  id="queue_id"
                  name="queue_id"
                  required
                  className={inputClass}
                  defaultValue=""
                >
                  <option value="" disabled>
                    Selecione a fila…
                  </option>
                  {filas.map((fila) => (
                    <option key={fila.id} value={fila.id}>
                      {fila.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label htmlFor="queue_when" className="text-sm font-medium leading-none">
                  Posição a partir de
                </label>
                <input
                  id="queue_when"
                  name="when"
                  type="datetime-local"
                  className={inputClass}
                />
              </div>
            </div>
            <Button
              type="submit"
              variant="secondary"
              disabled={queuePending || !canPublish}
            >
              {queuePending ? "Adicionando…" : "Adicionar à fila"}
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}

export function RegenerateButton({
  campaignId,
  disabled,
}: {
  campaignId: string;
  disabled?: boolean;
}) {
  const [state, formAction, pending] = useActionState(
    () => regenerateContents(campaignId),
    initialState,
  );
  return (
    <form action={formAction}>
      {state.error && (
        <Alert variant="destructive">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      <Button type="submit" variant="secondary" size="sm" disabled={pending || disabled}>
        {pending ? "Gerando…" : "Gerar novos textos"}
      </Button>
    </form>
  );
}

const CARD_THEMES: Record<string, { label: string; preview: string }> = {
  navy: { label: "Navy (padrão)", preview: "linear-gradient(160deg,#0B1220,#101A2C)" },
  verde: { label: "Verde", preview: "linear-gradient(160deg,#042F1F,#064E3B)" },
  amarelo: { label: "Amarelo", preview: "linear-gradient(160deg,#241C02,#3B2F04)" },
  vermelho: { label: "Vermelho", preview: "linear-gradient(160deg,#2B0A10,#4C131C)" },
};

export function CardConfigForm({
  productId,
  initial,
}: {
  productId: string;
  initial?: { theme?: string; border?: boolean } | null;
}) {
  const [theme, setTheme] = useState(initial?.theme ?? "navy");
  const [border, setBorder] = useState(initial?.border ?? false);
  const [state, formAction, pending] = useActionState(
    (prev: CampaignActionState, fd: FormData) =>
      updateCardConfig(productId, fd),
    initialState,
  );

  const preview = CARD_THEMES[theme] ?? CARD_THEMES.navy;

  return (
    <form action={formAction} className="space-y-3">
      {state.error && (
        <Alert variant="destructive">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-2">
        <label htmlFor="theme" className="text-sm font-medium leading-none">
          Cor do card do Telegram
        </label>
        <select
          id="theme"
          name="theme"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          className={inputClass}
        >
          {Object.entries(CARD_THEMES).map(([key, item]) => (
            <option key={key} value={key}>
              {item.label}
            </option>
          ))}
        </select>
        <div className="mt-2 flex items-center gap-3 rounded-md border border-border bg-card p-3">
          <span
            className="h-10 w-14 rounded-md"
            style={{ background: preview.preview }}
            aria-hidden="true"
          />
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              name="border"
              checked={border}
              onChange={(e) => setBorder(e.target.checked)}
              className="size-4 accent-[#D71931]"
            />
            Moldura colorida ao redor do card
          </label>
        </div>
      </div>
      <Button type="submit" size="sm" variant="secondary" disabled={pending}>
        {pending ? "Salvando…" : "Salvar card"}
      </Button>
    </form>
  );
}

export function CopyTextButton({
  copyText,
  link,
}: {
  copyText: string;
  link?: string | null;
}) {
  const [copiado, setCopiado] = useState(false);
  const handleCopy = async () => {
    const texto = link ? `${copyText}\n\n${link}` : copyText;
    await navigator.clipboard.writeText(texto);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  };
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={handleCopy}
      className={copiado ? "border-emerald-500 text-emerald-600" : ""}
    >
      {copiado ? "Copiado!" : "Copiar texto"}
    </Button>
  );
}
