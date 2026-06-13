"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/ui";
import { Skeleton } from "@/components/Skeleton";
import { FileBrowser } from "@/components/FileBrowser";
import { useVolumes, fetchVolumeFiles, fetchVolumeFile } from "@/lib/api";
import { bytes, ago } from "@/lib/format";

type Sel = { name: string; machine: string };

export default function VolumesPage() {
  const { data } = useVolumes();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Sel | null>(null);

  const all = data?.volumes ?? [];
  const volumes = useMemo(
    () => (q ? all.filter((v) => v.name.toLowerCase().includes(q.toLowerCase())) : all),
    [all, q]
  );
  const totalBytes = all.reduce((a, v) => a + v.size_bytes, 0);

  // Auto-select the first volume.
  useEffect(() => {
    if (!sel && all.length) setSel({ name: all[0].name, machine: all[0].machine_id });
  }, [all, sel]);

  const active = all.find((v) => v.name === sel?.name && v.machine_id === sel?.machine);

  return (
    <div className="flex h-[calc(100vh-13.5rem)] min-h-[440px] flex-col">
      {/* Header */}
      <div className="mb-5 flex items-end justify-between gap-6">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tightest text-white">Volumes</h1>
          <p className="mt-1.5 text-[13px] text-zinc-600">
            {all.length} volumes · {bytes(totalBytes)} · persistent directories on your Macs.
          </p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter volumes…"
          className="w-48 rounded-lg bg-white/[0.04] px-3 py-1.5 text-[13px] text-zinc-100 outline-none transition focus:bg-white/[0.06] placeholder:text-zinc-700"
        />
      </div>

      {!data ? (
        <Skeleton className="flex-1" />
      ) : all.length === 0 ? (
        <EmptyState
          title="No volumes yet"
          hint="herds.Volume.from_name('ios-builds') creates a persistent directory. Mount it with volumes={'builds': vol} and reach it via $HERDS_VOLUME_<NAME>."
        />
      ) : (
        <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl bg-white/[0.012] shadow-[0_4px_24px_-12px_rgba(0,0,0,0.6)]">
          {/* Volume rail (lightest tone) */}
          <div className="flex w-[244px] shrink-0 flex-col overflow-hidden bg-white/[0.03]">
            <div className="px-4 py-3 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-600">
              Volumes · {all.length}
            </div>
            <div className="flex-1 overflow-y-auto pb-2">
              {volumes.map((v) => {
                const on = active?.name === v.name && active?.machine_id === v.machine_id;
                const max = Math.max(1, ...all.map((x) => x.size_bytes));
                return (
                  <button
                    key={`${v.machine_id}/${v.name}`}
                    onClick={() => setSel({ name: v.name, machine: v.machine_id })}
                    className={`relative flex w-full flex-col gap-1.5 px-4 py-2.5 text-left transition-colors ${on ? "bg-white/[0.06]" : "hover:bg-white/[0.03]"}`}
                  >
                    {on && <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-signal-400" />}
                    <div className="flex items-center justify-between gap-2">
                      <span className={`truncate text-[13px] ${on ? "font-medium text-white" : "text-zinc-300"}`}>{v.name}</span>
                      <span className="tnum shrink-0 text-[11px] text-zinc-500">{bytes(v.size_bytes)}</span>
                    </div>
                    <div className="h-[3px] w-full overflow-hidden rounded-full bg-white/[0.06]">
                      <div className="h-full rounded-full bg-signal-500/80" style={{ width: `${Math.max(3, (v.size_bytes / max) * 100)}%` }} />
                    </div>
                    <div className="text-[10px] text-zinc-700">{v.file_count} files · {ago(v.updated_ms)}</div>
                  </button>
                );
              })}
              {volumes.length === 0 && <div className="px-4 py-5 text-[12px] text-zinc-600">No matches.</div>}
            </div>
          </div>

          {/* File browser (file list on base tone, preview darker) */}
          {active ? (
            <FileBrowser
              key={`${active.machine_id}/${active.name}`}
              flat
              list={(p) => fetchVolumeFiles(active.name, active.machine_id, p)}
              read={(p) => fetchVolumeFile(active.name, active.machine_id, p)}
            />
          ) : (
            <div className="grid flex-1 place-items-center text-[13px] text-zinc-600">Select a volume</div>
          )}
        </div>
      )}
    </div>
  );
}
