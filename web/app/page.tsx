"use client";

import Link from "next/link";
import { useState } from "react";
import { LiveDot, StatePill } from "@/components/ui";
import { BarChart, Sparkline } from "@/components/charts";
import { GaugeNeedle, LiquidFill, GradientSlider, SpotLine } from "@/components/widgets";
import { StatSkeleton, RowSkeleton } from "@/components/Skeleton";
import { Onboarding } from "@/components/Onboarding";
import { useJobs, useMachines, useMetrics, useTimeseries, useSandboxes } from "@/lib/api";
import { ago, bytes, dur } from "@/lib/format";

export default function Overview() {
  const { data: m } = useMetrics();
  const { data: machinesData } = useMachines();
  const { data: jobsData } = useJobs();
  const RANGES = [{ key: "15m", m: 15, b: 90 }, { key: "1h", m: 60, b: 60 }, { key: "24h", m: 1440, b: 96 }] as const;
  const [rangeKey, setRangeKey] = useState<(typeof RANGES)[number]["key"]>("15m");
  const range = RANGES.find((r) => r.key === rangeKey)!;
  const { data: ts } = useTimeseries(range.m, range.b);
  const { data: sbxData } = useSandboxes();
  const machines = machinesData?.machines ?? [];
  const jobs = (jobsData?.jobs ?? []).slice(0, 8);
  const liveSandboxes = (sbxData?.sandboxes ?? []).filter((s) => s.live);
  const cpuPoints = (ts?.cpu_mem ?? []).map((s) => ({ t: s.t, v: s.cpu }));
  const memPoints = (ts?.cpu_mem ?? []).map((s) => ({ t: s.t, v: s.mem }));
  const totalCores = machines.reduce((a, mc) => a + (mc.info?.cpu_count ?? 0), 0);
  const totalRam = machines.reduce((a, mc) => a + (mc.info?.memory_gb ?? 0), 0);
  const cpu = ts?.live_cpu ?? 0;
  const mem = ts?.live_mem ?? 0;
  const memLabel = mem < 50 ? "Comfortable" : mem < 80 ? "Moderate" : "High";
  const loadIdx = Math.max(cpu, mem) / 10;
  const loadLabel = loadIdx < 3 ? "Light" : loadIdx < 7 ? "Moderate" : "Heavy";

  // First-run: no Mac connected yet → focused onboarding.
  if (machinesData && machines.length === 0) {
    return (
      <div className="space-y-10">
        <header>
          <h1 className="text-[26px] font-semibold tracking-tightest text-white">Welcome to Herds</h1>
          <p className="mt-2 text-[13px] text-zinc-500">Turn any Mac into a programmable cloud runtime.</p>
        </header>
        <Onboarding />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[12px] text-zinc-600">
            <LiveDot size={6} /> Live workspace
          </div>
          <h1 className="mt-3 text-[26px] font-semibold tracking-tightest text-white">Your Macs, programmable.</h1>
        </div>
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
      </header>

      {!m ? (
        <StatSkeleton />
      ) : (
        <div className="grid grid-cols-12 gap-3">
          {/* Fleet hero */}
          <Widget className="col-span-12 lg:col-span-6">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-[13px] text-zinc-400">
                <LiveDot on={(m?.machines_online ?? 0) > 0} size={7} /> Fleet
              </span>
              <Link href="/machines" className="text-[12px] text-zinc-600 hover:text-zinc-300">View all</Link>
            </div>
            <div className="mt-4 flex items-end gap-3">
              <span className="tnum text-[44px] font-semibold leading-none tracking-tightest text-white">
                {m?.machines_online ?? 0}
              </span>
              <span className="pb-1 text-[13px] text-zinc-500">
                {(m?.machines_online ?? 0) === 1 ? "Mac online" : "Macs online"}
                <span className="text-zinc-700"> · {m?.machines_total ?? 0} connected</span>
              </span>
            </div>
            <div className="mt-5 grid grid-cols-3 gap-3 border-t border-white/[0.05] pt-4">
              <HeroStat value={totalCores || "—"} label="vCPUs" />
              <HeroStat value={totalRam ? `${totalRam}` : "—"} label="GB RAM" />
              <HeroStat value={ts?.runs_total ?? 0} label={`runs · ${rangeKey}`} />
            </div>
            <div className="mt-4 h-8">
              <Sparkline data={(ts?.runs ?? []).map((r) => r.count)} height={32} />
            </div>
          </Widget>

          {/* CPU gauge + Memory liquid-fill */}
          <div className="col-span-6 lg:col-span-3"><GaugeNeedle value={cpu} sub="live" /></div>
          <div className="col-span-6 lg:col-span-3"><LiquidFill value={mem} label={memLabel} /></div>

          {/* Load slider + CPU trend line */}
          <div className="col-span-6 lg:col-span-3"><GradientSlider value={loadIdx} label={loadLabel} /></div>
          <div className="col-span-6 lg:col-span-3"><SpotLine points={cpuPoints} title="CPU" tint="#fb923c" /></div>

          {/* Runs histogram */}
          <Widget className="col-span-12 lg:col-span-6">
            <div className="mb-4 flex items-baseline justify-between">
              <span className="text-[13px] text-zinc-400">Runs created</span>
              <span className="tnum text-[15px] font-semibold text-white">{ts?.runs_total ?? 0}</span>
            </div>
            <BarChart data={ts?.runs ?? []} />
          </Widget>

          {/* Small stat widgets */}
          <MiniWidget className="col-span-12 lg:col-span-2" value={m?.sandboxes_live ?? 0} label="Live sandboxes" sub={`${m?.sandboxes_total ?? 0} total`} accent={(m?.sandboxes_live ?? 0) > 0} href="/sandboxes" />
          <MiniWidget className="col-span-6 lg:col-span-2" value={m?.volumes ?? 0} label="Volumes" sub={bytes(m?.volumes_bytes ?? 0)} href="/volumes" />
          <MiniWidget className="col-span-6 lg:col-span-2" value={m?.secrets ?? 0} label="Secrets" sub="at dispatch" href="/secrets" />

          {/* Machines */}
          <Widget className="col-span-12 lg:col-span-6 !p-0">
            <div className="flex items-baseline justify-between px-5 pt-5">
              <h2 className="text-[13px] font-medium text-zinc-300">Machines</h2>
              <Link href="/machines" className="text-[12px] text-zinc-600 hover:text-zinc-300">View all</Link>
            </div>
            <div className="mt-3 divide-y divide-white/[0.05]">
              {machines.map((mac) => (
                <Link key={mac.machine_id} href={`/machine?id=${mac.machine_id}`} className="row flex items-center justify-between px-5 py-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2.5">
                      <LiveDot on={mac.status === "online"} size={7} />
                      <span className="truncate text-[13px] font-medium text-zinc-100">{mac.name}</span>
                    </div>
                    <div className="mt-1 pl-[18px] text-[12px] text-zinc-600">
                      {mac.info?.chip ?? "—"}{mac.info?.memory_gb && ` · ${mac.info.memory_gb}GB`}{mac.info?.cpu_count && ` · ${mac.info.cpu_count} cores`}
                    </div>
                  </div>
                  <span className="font-mono text-[10px] text-zinc-700">{mac.machine_id}</span>
                </Link>
              ))}
            </div>
          </Widget>

          {/* Live activity */}
          <Widget className="col-span-12 lg:col-span-6 !p-0">
            <div className="flex items-baseline justify-between px-5 pt-5">
              <h2 className="flex items-center gap-2 text-[13px] font-medium text-zinc-300">
                {liveSandboxes.length > 0 && <LiveDot size={6} />} Live activity
              </h2>
              <Link href="/runs" className="text-[12px] text-zinc-600 hover:text-zinc-300">All runs</Link>
            </div>
            <div className="mt-3 divide-y divide-white/[0.05]">
              {jobsData && jobs.length === 0 && (
                <div className="px-5 py-10 text-center text-[13px] text-zinc-600">
                  No runs yet — your first <span className="font-mono text-zinc-400">mac.run()</span> appears here.
                </div>
              )}
              {jobs.map((j) => (
                <div key={j.request_id} className="row flex items-center gap-4 px-5 py-2.5">
                  <span className="w-[84px] shrink-0"><StatePill state={j.state} /></span>
                  <code className="min-w-0 flex-1 truncate font-mono text-[12px] text-zinc-400">{j.command || "—"}</code>
                  <span className="tnum hidden w-10 text-right font-mono text-[11px] text-zinc-700 sm:inline">{dur(j.duration_ms)}</span>
                  <span className="w-14 text-right text-[12px] text-zinc-600">{ago(j.created_ms)}</span>
                </div>
              ))}
            </div>
          </Widget>
        </div>
      )}

      {/* Quickstart */}
      <section>
        <Heading title="Run something on a Mac" href="https://github.com/teddyoweh/herds" cta="Docs →" />
        <pre className="surface mt-3 overflow-x-auto px-5 py-4 font-mono text-[12.5px] leading-[1.7] text-zinc-400">
{`import herds

mac = herds.mac()
sbx = herds.Sandbox.create(
    image="xcode:26",
    volumes={"builds": herds.Volume.from_name("ios")},
    secrets=[herds.Secret.from_name("appstore")],
)
sbx.exec("xcodebuild -scheme App archive", check=True)`}
        </pre>
      </section>
    </div>
  );
}

function Widget({ className = "", center, children }: { className?: string; center?: boolean; children: React.ReactNode }) {
  return (
    <div className={`surface p-5 ${center ? "flex flex-col" : ""} ${className}`}>{children}</div>
  );
}

function HeroStat({ value, label }: { value: any; label: string }) {
  return (
    <div>
      <div className="tnum text-[20px] font-semibold leading-none tracking-tightest text-white">{value}</div>
      <div className="mt-1.5 text-[11px] text-zinc-600">{label}</div>
    </div>
  );
}

function MiniWidget({ className = "", value, label, sub, accent, href }: { className?: string; value: number; label: string; sub: string; accent?: boolean; href: string }) {
  return (
    <Link href={href} className={`surface surface-hover flex flex-col justify-between p-5 ${className}`}>
      <div className="flex items-center gap-1.5">
        {accent && <LiveDot size={6} />}
        <span className="label">{label}</span>
      </div>
      <div className="mt-3">
        <div className="tnum text-[28px] font-semibold leading-none tracking-tightest text-white">{value.toLocaleString()}</div>
        <div className="mt-1.5 text-[11px] text-zinc-700">{sub}</div>
      </div>
    </Link>
  );
}

function Heading({ title, href, cta }: { title: string; href: string; cta: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <h2 className="text-[13px] font-medium text-zinc-300">{title}</h2>
      <Link href={href} className="text-[12px] text-zinc-600 transition-colors hover:text-zinc-300">
        {cta}
      </Link>
    </div>
  );
}
