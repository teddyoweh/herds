"use client";

import { useEffect, useState } from "react";
import { useMetrics, getToken, setToken, isUnauthorized } from "@/lib/api";

/** When the control plane requires auth and we have no valid token, prompt for it. */
export function TokenGate({ children }: { children: React.ReactNode }) {
  const { error } = useMetrics();
  const [locked, setLocked] = useState(false);
  const [val, setVal] = useState("");

  useEffect(() => {
    if (error && isUnauthorized(error)) setLocked(true);
    else if (!error) setLocked(false);
  }, [error]);

  return (
    <>
      {children}
      {locked && (
        <div className="fixed inset-0 z-[90] grid place-items-center bg-ink-950/90 px-4 backdrop-blur-xl">
          <div className="w-full max-w-sm rounded-2xl bg-ink-850 p-7 shadow-e2">
            <div className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-signal-400 to-signal-600 text-base">🍎</span>
              <span className="text-[15px] font-semibold tracking-tightest text-white">Herds</span>
            </div>
            <h2 className="mt-5 text-[15px] font-semibold text-white">This host is protected</h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">
              Enter the host token to access this dashboard. You get it from{" "}
              <span className="font-mono text-zinc-400">herds host</span> on the host machine.
            </p>
            <input
              autoFocus
              type="password"
              value={val}
              onChange={(e) => setVal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && val.trim()) {
                  setToken(val.trim());
                  location.reload();
                }
              }}
              placeholder="herds_sk_…"
              className="mt-5 w-full rounded-lg bg-black/30 px-3 py-2.5 font-mono text-[13px] text-zinc-100 outline-none ring-1 ring-white/[0.06] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
            />
            <button
              onClick={() => {
                if (val.trim()) {
                  setToken(val.trim());
                  location.reload();
                }
              }}
              className="mt-3 w-full rounded-lg bg-signal-500 py-2.5 text-[13px] font-medium text-ink-950 transition hover:bg-signal-400"
            >
              Continue
            </button>
          </div>
        </div>
      )}
    </>
  );
}
