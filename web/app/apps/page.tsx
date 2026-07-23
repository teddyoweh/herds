"use client";

import Link from "next/link";
import { EmptyState, LiveDot } from "@/components/ui";
import { RowSkeleton } from "@/components/Skeleton";
import { useApps } from "@/lib/api";
import { ago } from "@/lib/format";

export default function AppsPage() {
  const { data } = useApps();
  const apps = data?.apps ?? [];
  const totalRuns = apps.reduce((a, b) => a + b.job_count, 0);
  const deployed = apps.filter((a) => a.deployed_ms).length;

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-[22px] font-semibold tracking-tightest text-white">Apps</h1>
      </div>

      <div className="mb-8 grid grid-cols-3 gap-3">
        <StatTile label="Apps" value={apps.length} />
        <StatTile label="Total runs" value={totalRuns} />
        <StatTile label="Deployed" value={deployed} accent={deployed > 0} />
      </div>

      {!data ? (
        <RowSkeleton rows={4} />
      ) : apps.length === 0 ? (
        <EmptyState
          title="No apps yet"
          hint='herds.App("my-builds") groups every run, sandbox, and function you launch. Just name an app and run something — it shows up here.'
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {apps.map((a) => (
            <Link
              key={a.name}
              href={`/app?name=${encodeURIComponent(a.name)}`}
              className="surface surface-hover group block p-5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <LiveDot on={!!a.deployed_ms} size={7} />
                  <code className="font-mono text-[13px] text-zinc-100">{a.name}</code>
                </div>
                {a.deployed_ms ? (
                  <span className="inline-flex items-center rounded-md bg-signal-500/10 px-2 py-0.5 text-[11px] font-medium text-signal-400">
                    deployed
                  </span>
                ) : null}
              </div>
              <div className="mt-4 truncate text-[12px] text-zinc-500">
                {a.description || "no description"}
              </div>
              <div className="mt-5 flex items-center justify-between text-[12px]">
                <Stat label="runs" value={a.job_count} />
                <Stat label="functions" value={a.function_count} />
                <Stat label="sandboxes" value={a.sandbox_count} />
                <Stat label="active" value={ago(a.last_active_ms)} />
              </div>
            </Link>
          ))}
        </div>
      )}
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

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="tnum text-[13px] text-zinc-300">{value}</div>
      <div className="label mt-1">{label}</div>
    </div>
  );
}
