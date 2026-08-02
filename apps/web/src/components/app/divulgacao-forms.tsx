"use client";

import { useActionState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  saveChannelGroup,
  sendGroupMessage,
  createQueue,
  saveCtaPhrase,
  type CampaignActionState,
} from "@/lib/actions";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { ChannelGroupOption } from "./campaign-actions";

const initialState: CampaignActionState = {};

const inputClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function ChannelGroupForm() {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(saveChannelGroup, initialState);

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
        <label htmlFor="name" className="text-sm font-medium leading-none">
          Nome do grupo
        </label>
        <input
          id="name"
          name="name"
          required
          placeholder="Grupo Tech Promo"
          className={inputClass}
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="telegram_chat_id" className="text-sm font-medium leading-none">
          chat_id do Telegram
        </label>
        <input
          id="telegram_chat_id"
          name="telegram_chat_id"
          required
          placeholder="-1001234567890"
          className={inputClass}
        />
        <p className="text-xs text-muted-foreground">
          Para descobrir o chat_id do grupo: adicione o bot ao grupo, envie uma
          mensagem nele e rode{" "}
          <code className="rounded bg-muted px-1">python -m publishers.telegram</code>{" "}
          na pasta do worker.
        </p>
      </div>
      <Button type="submit" disabled={pending}>
        {pending ? "Salvando…" : "Cadastrar grupo"}
      </Button>
    </form>
  );
}

export function GroupMessageForm({ grupo }: { grupo: ChannelGroupOption }) {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(
    (prev: CampaignActionState, fd: FormData) =>
      sendGroupMessage(grupo.id, prev, fd),
    initialState,
  );

  useEffect(() => {
    if (state.ok) {
      router.refresh();
    }
  }, [state.ok, router]);

  return (
    <form action={formAction} className="space-y-2">
      {state.error && (
        <Alert variant="destructive">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      <textarea
        name="text"
        rows={3}
        placeholder="Mensagem de teste (aceita HTML do Telegram, ex.: <b>negrito</b>)"
        className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <Button type="submit" size="sm" variant="secondary" disabled={pending}>
        {pending ? "Enviando…" : "Enviar mensagem de teste"}
      </Button>
    </form>
  );
}

export function QueueForm({ grupos }: { grupos: ChannelGroupOption[] }) {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(createQueue, initialState);

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
        <label htmlFor="queue_name" className="text-sm font-medium leading-none">
          Nome da fila
        </label>
        <input
          id="queue_name"
          name="name"
          required
          placeholder="Fila da manhã"
          className={inputClass}
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="interval_minutes" className="text-sm font-medium leading-none">
          Intervalo entre envios (minutos)
        </label>
        <input
          id="interval_minutes"
          name="interval_minutes"
          type="number"
          min={1}
          max={240}
          defaultValue={5}
          className={inputClass}
        />
        <p className="text-xs text-muted-foreground">
          Intervalo mínimo entre uma oferta e outra nesta fila. O worker
          respeita esse espaço para não floodar os grupos.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2">
          <label htmlFor="window_start" className="text-sm font-medium leading-none">
            Janela — início (opcional)
          </label>
          <input id="window_start" name="window_start" type="time" className={inputClass} />
        </div>
        <div className="space-y-2">
          <label htmlFor="window_end" className="text-sm font-medium leading-none">
            Janela — fim (opcional)
          </label>
          <input id="window_end" name="window_end" type="time" className={inputClass} />
        </div>
      </div>
      <div className="space-y-2">
        <p className="text-sm font-medium leading-none">Grupos de destino</p>
        {grupos.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Cadastre um grupo em Grupos antes de criar a fila.
          </p>
        ) : (
          <div className="space-y-1.5">
            {grupos.map((grupo) => (
              <label
                key={grupo.id}
                className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground"
              >
                <input
                  type="checkbox"
                  name="group_ids"
                  value={grupo.id}
                  className="size-4 accent-[#D71931]"
                />
                {grupo.name}
                <span className="ml-auto text-xs text-muted-foreground">
                  {grupo.telegram_chat_id}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>
      <Button type="submit" disabled={pending || grupos.length === 0}>
        {pending ? "Criando…" : "Criar fila"}
      </Button>
    </form>
  );
}

export function CtaPhraseForm() {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(saveCtaPhrase, initialState);

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
        <label htmlFor="phrase" className="text-sm font-medium leading-none">
          Frase de gatilho (CTA)
        </label>
        <input
          id="phrase"
          name="phrase"
          required
          placeholder="Ex.: Desconto confirmado na loja"
          className={inputClass}
        />
        <p className="text-xs text-muted-foreground">
          A cada publicação o worker sorteia uma das frases ativas. Frases
          enganosas (urgência falsa, estoque falso) são bloqueadas pela
          validação.
        </p>
      </div>
      <Button type="submit" disabled={pending}>
        {pending ? "Salvando…" : "Adicionar frase"}
      </Button>
    </form>
  );
}
