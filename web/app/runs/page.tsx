"use client";

import { useState } from "react";
import { SectionTitle, EmptyState } from "@/components/ui";
import { JobsTable } from "@/components/JobsTable";
import { BarChart } from "@/components/charts";
import { GaugeNeedle } from "@/components/widgets";
import { useJobs, useTimeseries } from "@/lib/api";

const RANGES = [
  { key: "15m", minutes: 15, buckets: 60 },
  { key: "1h", minutes: 60, buckets: 60 },
  { key: "24h", minutes: 1440, buckets: 96 },
] as const;

const STATES = [
  { key: "all", label: "All", match: () => true },
  { key: "running", label: "Running", match: (s: string) => ["running", "dispatched", "queued"].includes(s) },
  { key: "succeeded", label: "Succeeded", match: (s: string) => s === "succeeded" },
  { key: "failed", label: "Failed", match: (s: string) => s === "failed" },
] as const;

export default function RunsPage() {
  const [rangeKey, setRangeKey] = useState<(typeof RANGES)[number]["key"]>("15m");
  const [stateKey, setStateKey] = useState<string>("all");
  const [q, setQ] = useState("");

  const range = RANGES.find((r) => r.key === rangeKey)!;
  const { data } = useJobs();
  const { data: ts } = useTimeseries(range.minutes, range.buckets);

  const windowMs = range.minutes * 60_000;
  const cutoff = Date.now() - windowMs;
  const stateMatch = STATES.find((s) => s.key === stateKey)!.match;
  const ql = q.trim().toLowerCase();

  const windowJobs = (data?.jobs ?? []).filter((j) => j.created_ms >= cutoff);
  const done = windowJobs.filter((j) => ["succeeded", "failed"].includes(j.state));
  const successRate = done.length ? (done.filter((j) => j.state === "succeeded").length / done.length) * 100 : 100;

  const jobs = windowJobs
    .filter((j) => stateMatch(j.state))
    .filter((j) => !ql || (j.command || "").toLowerCase().includes(ql) || j.machine_id.includes(ql));

  return (
    <div>
      <SectionTitle
        title="Runs"
        sub="Every command dispatched to your Macs."
        right={
          <div className="flex gap-1 rounded-lg bg-white/[0.03] p-0.5">
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
        }
      />

      {/* Success gauge + histogram */}
      <div className="mb-5 grid grid-cols-12 gap-3">
        <div className="col-span-12 lg:col-span-3">
          <GaugeNeedle value={successRate} title="Success rate" sub={`${done.length} done`} color="#34d39e" />
        </div>
        <div className="surface col-span-12 p-5 lg:col-span-9">
          <div className="mb-4 flex items-baseline justify-between">
            <span className="text-[13px] text-zinc-400">Runs created</span>
            <span className="tnum text-[13px] text-zinc-500">
              {ts?.runs_total ?? 0} <span className="text-zinc-700">· last {rangeKey}</span>
            </span>
          </div>
          {ts && ts.runs_total === 0 ? (
            <div className="grid h-[116px] place-items-center text-[12px] text-zinc-700">
              No runs in the last {rangeKey}
            </div>
          ) : (
            <BarChart data={ts?.runs ?? []} />
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div className="mb-4 flex items-center gap-3">
        <div className="flex gap-1">
          {STATES.map((s) => (
            <button
              key={s.key}
              onClick={() => setStateKey(s.key)}
              className={`rounded-lg px-2.5 py-1.5 text-[12px] transition-colors ${
                stateKey === s.key ? "bg-white/[0.07] text-white" : "text-zinc-500 hover:bg-white/[0.03] hover:text-zinc-300"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search commands…"
          className="ml-auto w-64 rounded-lg bg-black/30 px-3 py-1.5 font-mono text-[12px] text-zinc-100 outline-none ring-1 ring-white/[0.06] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
        />
      </div>

      {jobs.length === 0 ? (
        <EmptyState
          title={ql || stateKey !== "all" ? "No matching runs" : "No runs yet"}
          hint={ql || stateKey !== "all" ? "Try a different filter or time range." : "mac.run('uname -a') and it appears here, streamed live."}
        />
      ) : (
        <JobsTable jobs={jobs} />
      )}
    </div>
  );
}
