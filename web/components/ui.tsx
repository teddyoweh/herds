"use client";

import { motion, useSpring, useTransform } from "framer-motion";
import { useEffect, useState } from "react";

/** Inline copy-to-clipboard affordance. */
export function Copy({ text, label = "copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        navigator.clipboard?.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1200);
      }}
      className="text-[11px] text-zinc-600 transition-colors hover:text-zinc-300"
    >
      {done ? "copied" : label}
    </button>
  );
}

/** A small status dot. Live = soft breathing glow; idle = flat. No rings. */
export function LiveDot({ on = true, size = 7 }: { on?: boolean; size?: number }) {
  return (
    <span
      className={
        on
          ? "inline-block animate-breathe rounded-full bg-signal-400 shadow-[0_0_8px_1px_rgba(52,211,158,0.45)]"
          : "inline-block rounded-full bg-zinc-700"
      }
      style={{ width: size, height: size }}
    />
  );
}

// Color is scarce and meaningful: emerald = ok, sky = in-flight, rose = failed,
// zinc = idle/done. Only genuinely in-flight states pulse.
const STATE: Record<string, { text: string; dot: string }> = {
  succeeded: { text: "text-zinc-400", dot: "bg-signal-500" },
  active: { text: "text-zinc-500", dot: "bg-zinc-600" },
  idle: { text: "text-zinc-500", dot: "bg-zinc-600" },
  running: { text: "text-sky-300", dot: "bg-sky-400" },
  dispatched: { text: "text-sky-300", dot: "bg-sky-400" },
  queued: { text: "text-amber-300", dot: "bg-amber-400" },
  failed: { text: "text-rose-300", dot: "bg-rose-400" },
  terminated: { text: "text-zinc-500", dot: "bg-zinc-600" },
};
const PULSING = new Set(["running", "dispatched", "queued"]);

export function StatePill({ state }: { state: string }) {
  const s = STATE[state] ?? { text: "text-zinc-400", dot: "bg-zinc-500" };
  return (
    <span className={`inline-flex items-center gap-1.5 text-[12px] ${s.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot} ${PULSING.has(state) ? "animate-breathe" : ""}`} />
      <span className="tracking-tight">{state}</span>
    </span>
  );
}

/** Number that settles into place. Subtle — the only motion that earns its keep. */
export function AnimatedNumber({ value }: { value: number }) {
  const spring = useSpring(0, { mass: 0.7, stiffness: 110, damping: 20 });
  const display = useTransform(spring, (v) => Math.round(v).toLocaleString());
  useEffect(() => {
    spring.set(value || 0);
  }, [value, spring]);
  return <motion.span className="tnum">{display}</motion.span>;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="surface flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="text-[14px] font-medium text-zinc-300">{title}</div>
      {hint && <div className="max-w-md text-[12.5px] leading-relaxed text-zinc-600">{hint}</div>}
    </div>
  );
}

export function SectionTitle({
  title,
  sub,
  right,
}: {
  title: string;
  sub?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex items-start justify-between">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tightest text-white">{title}</h1>
        {sub && <p className="mt-1.5 text-[13px] text-zinc-600">{sub}</p>}
      </div>
      {right}
    </div>
  );
}
