"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { StatePill, EmptyState, LiveDot } from "@/components/ui";
import { BarChart } from "@/components/charts";
import { RowSkeleton } from "@/components/Skeleton";
import { NewSandboxModal } from "@/components/NewSandboxModal";
import { useToast } from "@/components/Toast";
import { useSandboxes, useTimeseries, useMetrics, stopSandbox, terminateSandbox } from "@/lib/api";
import { ago, uptime } from "@/lib/format";

export default function SandboxesPage() {
  return (
    <Suspense fallback={null}>
      <SandboxesInner />
    </Suspense>
  );
}

const RANGES = [{ key: "15m", m: 15, b: 60 }, { key: "1h", m: 60, b: 60 }, { key: "24h", m: 1440, b: 96 }] as const;

function SandboxesInner() {
  const { data, mutate } = useSandboxes();
  const { data: m } = useMetrics();
  const [rangeKey, setRangeKey] = useState<(typeof RANGES)[number]["key"]>("15m");
  const range = RANGES.find((r) => r.key === rangeKey)!;
  const { data: ts } = useTimeseries(range.m, range.b);
  const toast = useToast();
  const sandboxes = data?.sandboxes ?? [];
  const live = m?.sandboxes_live ?? sandboxes.filter((s) => s.live).length;
  const createdInRange = (ts?.sandboxes ?? []).reduce((a, b) => a + b.count, 0);
  const [open, setOpen] = useState(useSearchParams().get("new") === "1");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmKill, setConfirmKill] = useState(false);
  const [busy, setBusy] = useState(false);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const bulk = async (action: "stop" | "terminate") => {
    if (action === "terminate" && !confirmKill) {
      setConfirmKill(true);
      setTimeout(() => setConfirmKill(false), 3000);
      return;
    }
    setBusy(true);
    const fn = action === "stop" ? stopSandbox : terminateSandbox;
    await Promise.allSettled([...selected].map((id) => fn(id)));
    toast(`${action === "stop" ? "Stopped" : "Terminated"} ${selected.size} sandbox${selected.size > 1 ? "es" : ""}`);
    setSelected(new Set());
    setConfirmKill(false);
    setBusy(false);
    mutate();
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-[22px] font-semibold tracking-tightest text-white">Sandboxes</h1>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 rounded-lg bg-white/[0.04] p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.key}
                onClick={() => setRangeKey(r.key)}
                className={`rounded-md px-2.5 py-1 text-[12px] transition-colors ${
                  rangeKey === r.key ? "bg-white/[0.08] text-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {r.key}
              </button>
            ))}
          </div>
          <button
            onClick={() => setOpen(true)}
            className="rounded-lg bg-zinc-100 px-3.5 py-2 text-[12px] font-medium text-ink-950 transition-colors hover:bg-white"
          >
            New sandbox
          </button>
        </div>
      </div>

      {/* Stat band */}
      <div className="mb-3 grid grid-cols-3 gap-3">
        <StatTile label="Live sandboxes" value={live} accent={live > 0} />
        <StatTile label="Total created" value={sandboxes.length} />
        <StatTile label={`Created · ${rangeKey}`} value={createdInRange} />
      </div>

      {/* Sandboxes created histogram */}
      <div className="surface mb-8 p-5">
        <div className="mb-4 flex items-baseline justify-between">
          <span className="flex items-center gap-2 text-[13px] text-zinc-400">
            <LiveDot on={live > 0} size={6} />
            Sandboxes created
          </span>
          <span className="tnum text-[12px] text-zinc-600">
            {createdInRange} <span className="text-zinc-700">· last {rangeKey}</span>
          </span>
        </div>
        {createdInRange === 0 ? (
          <div className="grid h-[116px] place-items-center text-[12px] text-zinc-700">No sandboxes created in the last {rangeKey}</div>
        ) : (
          <BarChart data={ts?.sandboxes ?? []} />
        )}
      </div>

      {!data ? (
        <RowSkeleton rows={4} />
      ) : sandboxes.length === 0 ? (
        <EmptyState
          title="No sandboxes yet"
          hint="dc.Sandbox.create(image='xcode:26') spins up an isolated workspace. sbx.spawn(...) runs a long-lived agent that keeps it live."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sandboxes.map((s) => (
            <Link
              key={s.sandbox_id}
              href={`/sandbox?id=${s.sandbox_id}`}
              className={`surface surface-hover group block p-5 ${
                selected.has(s.sandbox_id) ? "ring-1 ring-signal-500/50" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      toggle(s.sandbox_id);
                    }}
                    className={`grid h-4 w-4 shrink-0 place-items-center rounded border text-[10px] transition-all ${
                      selected.has(s.sandbox_id)
                        ? "border-signal-500 bg-signal-500 text-ink-950"
                        : "border-white/15 text-transparent opacity-0 group-hover:opacity-100"
                    }`}
                    aria-label="select"
                  >
                    ✓
                  </button>
                  <LiveDot on={!!s.live} size={7} />
                  <code className="font-mono text-[13px] text-zinc-100">{s.sandbox_id}</code>
                </div>
                {s.live ? (
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-signal-500/10 px-2 py-0.5 text-[11px] font-medium text-signal-400">
                    live · up {uptime(s.last_used_ms)}
                  </span>
                ) : (
                  <StatePill state="idle" />
                )}
              </div>
              <div className="mt-4 text-[12px] text-zinc-500">{s.image || "host environment"}</div>
              <div className="mt-5 flex items-center justify-between text-[12px]">
                <Stat label="execs" value={s.exec_count} />
                <Stat label="machine" value={s.machine_id.replace("mac_", "")} mono />
                <Stat label="used" value={ago(s.last_used_ms)} />
              </div>
            </Link>
          ))}
        </div>
      )}

      <AnimatePresence>{open && <NewSandboxModal onClose={() => setOpen(false)} />}</AnimatePresence>

      {/* Bulk action bar */}
      <AnimatePresence>
        {selected.size > 0 && (
          <motion.div
            initial={{ y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 24, opacity: 0 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            className="fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-2xl bg-ink-850 px-4 py-2.5 shadow-e2"
          >
            <span className="text-[13px] text-zinc-300">
              <span className="tnum font-medium text-white">{selected.size}</span> selected
            </span>
            <span className="h-4 w-px bg-white/10" />
            <button
              onClick={() => bulk("stop")}
              disabled={busy}
              className="rounded-lg px-3 py-1.5 text-[12px] text-zinc-300 transition-colors hover:bg-white/[0.06] disabled:opacity-50"
            >
              Stop
            </button>
            <button
              onClick={() => bulk("terminate")}
              disabled={busy}
              className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-50 ${
                confirmKill ? "bg-rose-500 text-white" : "text-rose-300 hover:bg-rose-500/15"
              }`}
            >
              {confirmKill ? "Confirm terminate" : "Terminate"}
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="rounded-lg px-3 py-1.5 text-[12px] text-zinc-500 transition-colors hover:text-zinc-200"
            >
              Clear
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StatTile({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="surface px-5 py-4">
      <div className="flex items-center gap-1.5">
        {accent && <LiveDot size={6} />}
        <span className="label">{label}</span>
      </div>
      <div className="mt-2.5 tnum text-[26px] font-semibold leading-none tracking-tightest text-white">
        {value.toLocaleString()}
      </div>
    </div>
  );
}

function Stat({ label, value, mono }: { label: string; value: any; mono?: boolean }) {
  return (
    <div>
      <div className={`text-zinc-300 ${mono ? "font-mono text-[12px]" : "tnum text-[13px]"}`}>{value}</div>
      <div className="label mt-1">{label}</div>
    </div>
  );
}
