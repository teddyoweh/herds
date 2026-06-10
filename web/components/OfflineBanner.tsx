"use client";

import { useHealth } from "@/lib/api";

/** A quiet banner when the control plane can't be reached — graceful, not broken. */
export function OfflineBanner() {
  const { error } = useHealth();
  if (!error) return null;
  return (
    <div className="sticky top-0 z-40 flex items-center justify-center gap-2 bg-amber-500/10 py-1.5 text-[12px] text-amber-300 backdrop-blur-xl">
      <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-amber-400" />
      Reconnecting to control plane…
    </div>
  );
}
