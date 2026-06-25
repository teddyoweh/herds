"use client";

import { useId } from "react";

/* A single gull-bird, centred at the origin, pointing up. The whole mark is a
   flock of these in formation — a herd, moving as one. */
const BIRD = "M0 -2 C4 -6 8 -5 12 -2 C8 -2.5 4 -1 0 1 C-4 -1 -8 -2.5 -12 -2 C-8 -5 -4 -6 0 -2 Z";

/**
 * Herds mark — a flock of birds rising in formation, on the signal-green
 * gradient. Freestanding (no container): the lead bird carries a soft sheen and
 * the trailing birds recede for depth. Below ~30px it collapses to a clean trio
 * so it stays legible in dense nav and favicons.
 */
export function Logo({ size = 28, className = "" }: { size?: number; className?: string }) {
  const uid = useId();
  const g = `${uid}g`;
  const s = `${uid}s`;
  const full = size >= 30;
  const fill = `url(#${g})`;
  // Composition fills and centres the 64×64 box so the mark reads large at any size.
  const lead = full ? "translate(32 27) scale(1.6)" : "translate(32 28) scale(1.72)";
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={`shrink-0 ${className}`} role="img" aria-label="Herds">
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="0.32" y2="1">
          <stop offset="0" stopColor="#46e3ad" />
          <stop offset="0.5" stopColor="#1bbd86" />
          <stop offset="1" stopColor="#0b9266" />
        </linearGradient>
        <linearGradient id={s} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.32" />
          <stop offset="0.62" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
      </defs>
      {full && (
        <>
          <path d={BIRD} transform="translate(8 45) scale(0.66)" fill={fill} opacity="0.4" />
          <path d={BIRD} transform="translate(56 45) scale(0.66)" fill={fill} opacity="0.4" />
        </>
      )}
      <path d={BIRD} transform={full ? "translate(16 37) scale(1.05)" : "translate(15 40) scale(1.06)"} fill={fill} opacity={full ? 0.7 : 0.66} />
      <path d={BIRD} transform={full ? "translate(48 37) scale(1.05)" : "translate(49 40) scale(1.06)"} fill={fill} opacity={full ? 0.7 : 0.66} />
      <path d={BIRD} transform={lead} fill={fill} />
      <path d={BIRD} transform={lead} fill={`url(#${s})`} />
    </svg>
  );
}
