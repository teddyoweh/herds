"use client";

import Link from "next/link";
import { SectionTitle, LiveDot } from "@/components/ui";
import { MiniGauge } from "@/components/widgets";
import { Skeleton } from "@/components/Skeleton";
import { Onboarding } from "@/components/Onboarding";
import { useMachines } from "@/lib/api";
import { ago } from "@/lib/format";

export default function MachinesPage() {
  const { data } = useMachines();
  const machines = data?.machines ?? [];

  return (
    <div>
      <SectionTitle title="Machines" sub="The Macs you've connected. The Mac is the cloud." />
      {!data ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      ) : machines.length === 0 ? (
        <Onboarding />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {machines.map((mac) => (
            <Link key={mac.machine_id} href={`/machine?id=${mac.machine_id}`} className="surface surface-hover block p-6">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[15px] font-semibold tracking-tight text-white">
                    {mac.name}
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-zinc-700">{mac.machine_id}</div>
                </div>
                <div className="flex items-center gap-2 text-[12px]">
                  <LiveDot on={mac.status === "online"} size={6} />
                  <span className={mac.status === "online" ? "text-signal-400" : "text-zinc-600"}>
                    {mac.status}
                  </span>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-4">
                <Spec label="Chip" value={mac.info?.chip ?? "—"} />
                <Spec label="Memory" value={mac.info?.memory_gb ? `${mac.info.memory_gb} GB` : "—"} />
                <Spec label="Cores" value={mac.info?.cpu_count ?? "—"} />
                <Spec label="macOS" value={mac.info?.macos_version ?? "—"} />
              </div>

              <div className="mt-6 flex items-center justify-between border-t border-white/[0.05] pt-4">
                {mac.status === "online" && mac.live_cpu != null ? (
                  <MiniGauge value={mac.live_cpu} />
                ) : (
                  <span className="text-[11px] text-zinc-700">offline</span>
                )}
                <span className="text-[11px] text-zinc-700">
                  {ago(mac.last_seen_ms)} · {mac.info?.arch ?? "arm64"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Spec({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="mt-1.5 text-[13px] text-zinc-200">{value}</div>
    </div>
  );
}
