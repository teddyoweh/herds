"use client";

import { API } from "@/lib/api";
import { Copy, LiveDot } from "./ui";

const STEPS = [
  { n: 1, title: "Install Darwin", cmd: "brew install darwin-cloud" },
  { n: 2, title: "Connect this Mac", cmd: "darwin connect" },
];

export function Onboarding() {
  return (
    <div className="mx-auto max-w-xl py-10">
      <div className="text-center">
        <div className="mx-auto mb-5 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-signal-400 to-signal-600 text-xl shadow-e2">
          🍎
        </div>
        <h2 className="text-[20px] font-semibold tracking-tight text-white">Connect your first Mac</h2>
        <p className="mx-auto mt-2 max-w-sm text-[13px] leading-relaxed text-zinc-500">
          Install Darwin and sign in. The Mac dials home over a secure connection — no inbound
          ports — and becomes a programmable runtime you can drive from anywhere.
        </p>
      </div>

      <div className="mt-8 space-y-3">
        {STEPS.map((s) => (
          <div key={s.n} className="surface overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-3">
              <span className="grid h-5 w-5 place-items-center rounded-full bg-white/[0.06] text-[11px] font-medium text-zinc-400">
                {s.n}
              </span>
              <span className="flex-1 text-[13px] text-zinc-300">{s.title}</span>
              <Copy text={s.cmd} />
            </div>
            <pre className="overflow-x-auto bg-black/25 px-5 py-3 font-mono text-[12.5px] text-zinc-300">{s.cmd}</pre>
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-center gap-2 text-[12px] text-zinc-600">
        <LiveDot size={6} />
        Waiting for a Mac to connect…
      </div>
      <p className="mt-3 text-center text-[11px] text-zinc-700">
        Self-hosting? Point a Mac at this control plane with{" "}
        <span className="font-mono text-zinc-600">DARWIN_CONTROL_PLANE={API}</span>
      </p>
    </div>
  );
}
