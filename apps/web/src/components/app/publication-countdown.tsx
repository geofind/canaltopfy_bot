"use client";

import { useEffect, useState } from "react";

type PublicationCountdownProps = {
  targetEpochMs: number | null;
  initialRemainingSeconds: number;
  scheduledTimeLabel: string;
  productTitle: string | null;
};

function formatCountdown(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;

  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

export function PublicationCountdown({
  targetEpochMs,
  initialRemainingSeconds,
  scheduledTimeLabel,
  productTitle,
}: PublicationCountdownProps) {
  const [remainingSeconds, setRemainingSeconds] = useState(initialRemainingSeconds);

  useEffect(() => {
    if (targetEpochMs === null) {
      setRemainingSeconds(0);
      return;
    }

    const updateCountdown = () => {
      setRemainingSeconds(
        Math.max(0, Math.ceil((targetEpochMs - Date.now()) / 1_000)),
      );
    };

    updateCountdown();
    const timer = window.setInterval(updateCountdown, 1_000);
    return () => window.clearInterval(timer);
  }, [targetEpochMs]);

  const hasScheduledPost = targetEpochMs !== null;
  const isDue = hasScheduledPost && remainingSeconds === 0;

  return (
    <div className="relative border-t border-white/10 pt-6 sm:border-l sm:border-t-0 sm:pl-7 sm:pt-0">
      <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#F65A6C]">
        Próxima postagem
      </p>
      <p
        className="mt-4 whitespace-nowrap font-display text-5xl font-bold leading-none tracking-[-0.055em] tabular-nums sm:text-6xl"
        role="timer"
        aria-label={
          hasScheduledPost
            ? `${remainingSeconds} segundos para a próxima postagem`
            : "Nenhuma postagem agendada"
        }
      >
        {hasScheduledPost ? formatCountdown(remainingSeconds) : "--:--:--"}
      </p>
      <div className="mt-3 max-w-72 text-xs leading-5 text-white/55">
        <p className={isDue ? "font-bold text-emerald-300" : undefined}>
          {isDue
            ? "Publicando agora"
            : hasScheduledPost
              ? `programada para ${scheduledTimeLabel}`
              : "fila sem próxima campanha"}
        </p>
        {productTitle ? <p className="truncate text-white/35">{productTitle}</p> : null}
      </div>
    </div>
  );
}
