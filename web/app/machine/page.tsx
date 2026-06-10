"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { LiveDot, Copy, EmptyState } from "@/components/ui";
import { GaugeNeedle, LiquidFill, GradientSlider, SpotLine } from "@/components/widgets";
import { useMachines, useSandboxes, useVolumes, useTimeseries } from "@/lib/api";
import { ago, bytes, uptime } from "@/lib/format";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <MachineDetailInner />
    </Suspense>
  );
}

function MachineDetailInner() {
  const id = useSearchParams().get("id") ?? "";
  const { data: md } = useMachines();
  const { data: sd } = useSandboxes();
  const { data: vd } = useVolumes();
  const { data: ts } = useTimeseries(15, 90, id);

  const mac = (md?.machines ?? []).find((m) => m.machine_id === id);
  const sandboxes = (sd?.sandboxes ?? []).filter((s) => s.machine_id === id);
  const volumes = (vd?.volumes ?? []).filter((v) => v.machine_id === id);
  const cpu = (ts?.cpu_mem ?? []).map((s) => ({ t: s.t, v: s.cpu }));
  const online = mac?.status === "online";

  if (md && !mac) {
    return (
      <div>
        <Back />
        <EmptyState title="Machine not found" hint={`No machine ${id} on this control plane.`} />
      </div>
    );
  }

  return (
    <div>
      <Back />

      <div className="mb-8 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <LiveDot on={online} size={8} />
            <h1 className="text-[20px] font-semibold tracking-tight text-white">{mac?.name ?? id}</h1>
            <Copy text={id} />
          </div>
          <p className="mt-2 font-mono text-[12px] text-zinc-600">{id}</p>
        </div>
        <span className={`text-[12px] ${online ? "text-signal-400" : "text-zinc-600"}`}>{mac?.status ?? "—"}</span>
      </div>

      <div className="surface mb-6 grid grid-cols-2 gap-x-8 gap-y-4 px-5 py-4 sm:grid-cols-4">
        <Spec label="Chip" value={mac?.info?.chip ?? "—"} />
        <Spec label="Memory" value={mac?.info?.memory_gb ? `${mac.info.memory_gb} GB` : "—"} />
        <Spec label="Cores" value={mac?.info?.cpu_count ?? "—"} />
        <Spec label="macOS" value={mac?.info?.macos_version ?? "—"} />
      </div>

      <div className="mb-10 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <GaugeNeedle value={ts?.live_cpu ?? 0} sub="live" />
        <LiquidFill value={ts?.live_mem ?? 0} label={(ts?.live_mem ?? 0) < 50 ? "Comfortable" : (ts?.live_mem ?? 0) < 80 ? "Moderate" : "High"} />
        <GradientSlider value={Math.max(ts?.live_cpu ?? 0, ts?.live_mem ?? 0) / 10} label={Math.max(ts?.live_cpu ?? 0, ts?.live_mem ?? 0) / 10 < 3 ? "Light" : Math.max(ts?.live_cpu ?? 0, ts?.live_mem ?? 0) / 10 < 7 ? "Moderate" : "Heavy"} />
        <SpotLine points={cpu} title="CPU" tint="#fb923c" />
      </div>

      <Section title="Sandboxes" count={sandboxes.length}>
        {sandboxes.length === 0 ? (
          <div className="px-5 py-3 text-[13px] text-zinc-600">No sandboxes on this Mac.</div>
        ) : (
          sandboxes.map((s) => (
            <Link key={s.sandbox_id} href={`/sandbox?id=${s.sandbox_id}`} className="row flex items-center gap-3 px-5 py-2.5">
              <LiveDot on={!!s.live} size={6} />
              <code className="min-w-0 flex-1 truncate font-mono text-[12px] text-zinc-300">{s.sandbox_id}</code>
              <span className="text-[11px] text-zinc-600">{s.image || "host"}</span>
              <span className="w-16 text-right text-[11px] text-zinc-700">{s.live ? `up ${uptime(s.last_used_ms)}` : ago(s.last_used_ms)}</span>
            </Link>
          ))
        )}
      </Section>

      <div className="h-8" />

      <Section title="Volumes" count={volumes.length}>
        {volumes.length === 0 ? (
          <div className="px-5 py-3 text-[13px] text-zinc-600">No volumes on this Mac.</div>
        ) : (
          volumes.map((v) => (
            <Link key={v.name} href={`/volume?name=${encodeURIComponent(v.name)}&machine=${id}`} className="row flex items-center gap-3 px-5 py-2.5">
              <code className="min-w-0 flex-1 truncate font-mono text-[12px] text-zinc-300">{v.name}</code>
              <span className="tnum text-[11px] text-zinc-600">{bytes(v.size_bytes)}</span>
              <span className="w-20 text-right text-[11px] text-zinc-700">{v.file_count} files</span>
            </Link>
          ))
        )}
      </Section>
    </div>
  );
}

function Back() {
  return (
    <Link href="/machines" className="mb-6 inline-block text-[12px] text-zinc-600 transition-colors hover:text-zinc-300">
      ← Machines
    </Link>
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

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 text-[13px] font-medium text-zinc-300">
        {title}
        <span className="tnum text-zinc-600">{count}</span>
      </h2>
      <div className="surface divide-y divide-white/[0.05] overflow-hidden">{children}</div>
    </section>
  );
}
