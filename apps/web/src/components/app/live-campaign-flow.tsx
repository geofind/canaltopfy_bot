"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  BadgeCheck,
  Check,
  Clock3,
  FileText,
  ListOrdered,
  Radar,
  Send,
  Zap,
} from "lucide-react";

type NextCampaign = {
  id: string;
  title: string;
  source: string;
  scheduledTime: string;
  isDue: boolean;
  priceLabel: string;
  score: number;
  discount: number;
};

type LiveCampaignFlowProps = {
  nextCampaign: NextCampaign | null;
  workerOnline: boolean;
  refreshedAtLabel: string;
};

const stepIcons = [Radar, BadgeCheck, FileText, ListOrdered, Send];

function ElectricWire() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 72 28"
      className="electric-wire h-7 w-14 shrink-0 sm:w-16"
      preserveAspectRatio="none"
    >
      <path
        d="M0 14 H13 L20 5 L29 23 L38 8 L46 14 H72"
        className="electric-wire-base"
      />
      <path
        d="M0 14 H13 L20 5 L29 23 L38 8 L46 14 H72"
        className="electric-wire-current"
      />
    </svg>
  );
}

export function LiveCampaignFlow({
  nextCampaign,
  workerOnline,
  refreshedAtLabel,
}: LiveCampaignFlowProps) {
  const router = useRouter();

  useEffect(() => {
    const timer = window.setInterval(() => router.refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [router]);

  const scheduledTime = nextCampaign?.scheduledTime ?? "—";
  const isDue = nextCampaign?.isDue ?? false;
  const activeStep = !nextCampaign ? 0 : isDue && workerOnline ? 4 : 3;

  const steps = [
    {
      label: "Descoberta",
      detail: nextCampaign
        ? `${nextCampaign.source} selecionado`
        : "Motor procurando ofertas",
    },
    {
      label: "Score",
      detail: nextCampaign
        ? `${nextCampaign.score} pontos · ${nextCampaign.discount.toFixed(0)}% off`
        : "Aguardando candidato",
    },
    {
      label: "Copy + link",
      detail: nextCampaign ? "Texto e link verificados" : "Aguardando produto",
    },
    {
      label: "Fila",
      detail: nextCampaign ? `Reservado para ${scheduledTime}` : "Fila vazia",
    },
    {
      label: "Telegram",
      detail: nextCampaign
        ? isDue
          ? "Liberado para publicar"
          : `Publicação às ${scheduledTime}`
        : "Aguardando campanha",
    },
  ];

  return (
    <section
      aria-labelledby="live-flow-title"
      className="overflow-hidden rounded-2xl border border-[#CBD0D8] bg-[#171E2A] text-white shadow-soft"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 px-5 py-4 sm:px-7">
        <div>
          <div className="flex items-center gap-2">
            <Zap className="size-4 text-[#F65A6C]" aria-hidden="true" />
            <p className="text-[9px] font-black uppercase tracking-[.22em] text-[#F65A6C]">
              Circuito da próxima publicação
            </p>
          </div>
          <h2 id="live-flow-title" className="mt-1 font-display text-2xl font-bold">
            Fluxo ao vivo
          </h2>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-white/45">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-50 motion-reduce:animate-none" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-400" />
          </span>
          Atualiza a cada 30s · {refreshedAtLabel}
        </div>
      </div>

      <div className="overflow-x-auto px-5 py-6 sm:px-7">
        <div className="flex min-w-max items-center">
          {steps.map((step, index) => {
            const Icon = stepIcons[index];
            const isActive = index === activeStep;
            const isComplete = index < activeStep;
            const isNextProductCard = index === 3 && nextCampaign;

            const card = (
              <div
                className={`relative flex h-[190px] flex-col rounded-xl border p-4 transition-colors ${
                  isNextProductCard ? "w-[310px]" : "w-[190px]"
                } ${
                  isActive
                    ? "border-[#FF334F] bg-[#252D3A] shadow-[0_0_0_3px_rgba(215,25,49,.28),0_0_28px_rgba(215,25,49,.20)]"
                    : isComplete
                      ? "border-emerald-400/25 bg-[#202936]"
                      : "border-white/10 bg-white/[.035]"
                }`}
              >
                {isActive ? (
                  <span className="absolute -top-2.5 left-4 rounded-full bg-[#D71931] px-2.5 py-1 text-[8px] font-black uppercase tracking-[.16em] text-white">
                    Etapa atual
                  </span>
                ) : null}
                <div className="flex items-center justify-between">
                  <span
                    className={`grid size-9 place-items-center rounded-lg ${
                      isActive
                        ? "bg-[#D71931] text-white"
                        : isComplete
                          ? "bg-emerald-400/10 text-emerald-300"
                          : "bg-white/5 text-white/35"
                    }`}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <span className="font-mono text-[9px] font-bold text-white/25">
                    0{index + 1}
                  </span>
                </div>
                <h3 className="mt-4 text-sm font-black">{step.label}</h3>

                {isNextProductCard ? (
                  <div className="mt-2 min-w-0">
                    <p className="line-clamp-2 text-xs font-bold leading-5 text-white/90">
                      {nextCampaign.title}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1.5 text-[9px] font-bold">
                      <span className="rounded bg-white/8 px-2 py-1">
                        {nextCampaign.priceLabel}
                      </span>
                      <span className="rounded bg-[#D71931]/20 px-2 py-1 text-[#FF8192]">
                        Score {nextCampaign.score}
                      </span>
                      <span className="rounded bg-white/8 px-2 py-1">
                        {scheduledTime}
                      </span>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-[10px] leading-4 text-white/45">{step.detail}</p>
                )}

                <div className="mt-auto flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-[.12em]">
                  {isComplete ? (
                    <>
                      <Check className="size-3 text-emerald-300" aria-hidden="true" />
                      <span className="text-emerald-300">Concluído</span>
                    </>
                  ) : isActive ? (
                    <>
                      <Clock3 className="size-3 text-[#FF8192]" aria-hidden="true" />
                      <span className="text-[#FF8192]">Em andamento</span>
                    </>
                  ) : (
                    <span className="text-white/25">Próxima etapa</span>
                  )}
                </div>
              </div>
            );

            return (
              <div key={step.label} className="flex items-center">
                {isNextProductCard && nextCampaign ? (
                  <Link
                    href={`/campanhas/${nextCampaign.id}`}
                    className="rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF334F] focus-visible:ring-offset-4 focus-visible:ring-offset-[#171E2A]"
                    aria-label={`Abrir próxima campanha: ${nextCampaign.title}`}
                  >
                    {card}
                  </Link>
                ) : (
                  card
                )}
                {index < steps.length - 1 ? <ElectricWire /> : null}
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-5 py-3 text-[10px] text-white/40 sm:px-7">
        <span>
          {nextCampaign
            ? `Próxima: ${nextCampaign.title} · ${nextCampaign.priceLabel} · score ${nextCampaign.score}`
            : "Sem campanha pendente; o motor está reabastecendo a fila."}
        </span>
        <Link href="/filas" className="font-bold text-white hover:text-[#F65A6C]">
          Abrir fila →
        </Link>
      </div>
    </section>
  );
}
