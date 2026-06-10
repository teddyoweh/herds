"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { LiveDot, StatePill, EmptyState } from "@/components/ui";
import { JobsTable } from "@/components/JobsTable";
import { FileBrowser } from "@/components/FileBrowser";
import { LiveTail } from "@/components/LiveTail";
import { useToast } from "@/components/Toast";
import { Copy } from "@/components/ui";
import { BarChart } from "@/components/charts";
import {
  useSandbox, usePorts, fetchFiles, fetchFile, stopSandbox, runInSandbox, terminateSandbox,
  exposePort, unexposePort, API,
} from "@/lib/api";
import { ago, dur, uptime } from "@/lib/format";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <SandboxDetailInner />
    </Suspense>
  );
}

function SandboxDetailInner() {
  const id = useSearchParams().get("id") ?? "";
  const { data, error, mutate } = useSandbox(id);
  const toast = useToast();
  const router = useRouter();
  const sp = useSearchParams();
  const [confirmKill, setConfirmKill] = useState(false);
  const initial = sp.get("tab") === "files" ? "files" : "logs";
  const [tab, setTab] = useState<"logs" | "files">(initial);
  const [stopping, setStopping] = useState(false);
  const [cmd, setCmd] = useState("");
  const [keepAlive, setKeepAlive] = useState(false);
  const [runningCmd, setRunningCmd] = useState(false);
  const { data: portsData, mutate: mutatePorts } = usePorts(id);
  const [newPort, setNewPort] = useState("");
  const ports = portsData?.ports ?? [];

  const expose = async () => {
    const p = parseInt(newPort, 10);
    if (!p) return;
    try {
      await exposePort(id, p, "");
      setNewPort("");
      mutatePorts();
      toast(`Port ${p} exposed`, "success");
    } catch (e: any) {
      toast(e.message || "Failed to expose", "error");
    }
  };

  if (error) {
    return (
      <div>
        <Back />
        <EmptyState title="Sandbox not found" hint={`No sandbox ${id} on this control plane.`} />
      </div>
    );
  }

  const sb = data?.sandbox;
  const jobs = data?.jobs ?? [];
  const succeeded = jobs.filter((j) => j.state === "succeeded").length;
  const totalMs = jobs.reduce((a, j) => a + (j.duration_ms ?? 0), 0);
  const live = !!sb?.live;
  const running = jobs.find((j) => ["running", "dispatched", "queued"].includes(j.state));

  // Activity histogram — execs bucketed over the last 30 minutes.
  const activityHist = (() => {
    const win = 30 * 60_000, n = 44, bsize = win / n, start = Date.now() - win;
    const c = Array.from({ length: n }, (_, i) => ({ t: start + i * bsize, count: 0 }));
    jobs.forEach((j) => {
      if (j.created_ms >= start) c[Math.min(n - 1, Math.floor((j.created_ms - start) / bsize))].count++;
    });
    return c;
  })();
  const recentExecs = activityHist.reduce((a, b) => a + b.count, 0);

  const stop = async () => {
    setStopping(true);
    try {
      await stopSandbox(id);
      toast("Sandbox stopped");
      mutate();
    } catch {
      toast("Failed to stop", "error");
    } finally {
      setStopping(false);
    }
  };

  const terminate = async () => {
    if (!confirmKill) {
      setConfirmKill(true);
      setTimeout(() => setConfirmKill(false), 3000);
      return;
    }
    try {
      await terminateSandbox(id);
      toast("Sandbox terminated");
      router.push("/sandboxes");
    } catch {
      toast("Failed to terminate", "error");
    }
  };

  const run = async () => {
    if (!cmd.trim() || !sb) return;
    setRunningCmd(true);
    try {
      await runInSandbox(sb.machine_id, {
        command: cmd.trim(),
        sandbox_id: id,
        keep_alive: keepAlive,
      });
      toast(keepAlive ? "Agent spawned" : "Command running", "success");
      setCmd("");
      setTimeout(mutate, 400);
    } catch (e: any) {
      toast(e.message || "Failed to run", "error");
    } finally {
      setRunningCmd(false);
    }
  };

  return (
    <div>
      <Back />

      <div className="mb-8 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <LiveDot on={live} size={8} />
            <h1 className="font-mono text-[20px] font-semibold tracking-tight text-white">{id}</h1>
            <Copy text={id} />
          </div>
          <p className="mt-2 text-[13px] text-zinc-600">
            {sb?.image || "host environment"} · on{" "}
            <span className="font-mono text-zinc-500">{sb?.machine_id}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          {live ? (
            <>
              <span className="inline-flex items-center gap-1.5 rounded-md bg-signal-500/10 px-2.5 py-1 text-[12px] font-medium text-signal-400">
                <LiveDot size={6} /> live
              </span>
              {running && <span className="text-[12px] text-zinc-600">up {uptime(running.created_ms)}</span>}
              <button
                onClick={stop}
                disabled={stopping}
                className="rounded-lg bg-rose-500/10 px-3.5 py-1.5 text-[12px] font-medium text-rose-300 transition-colors hover:bg-rose-500/20 disabled:opacity-50"
              >
                {stopping ? "Stopping…" : "Stop"}
              </button>
            </>
          ) : (
            sb && <StatePill state="idle" />
          )}
          <button
            onClick={terminate}
            className={`rounded-lg px-3.5 py-1.5 text-[12px] font-medium transition-colors ${
              confirmKill
                ? "bg-rose-500 text-white"
                : "bg-white/[0.04] text-zinc-500 hover:bg-rose-500/15 hover:text-rose-300"
            }`}
          >
            {confirmKill ? "Confirm terminate" : "Terminate"}
          </button>
        </div>
      </div>

      {live && running && (
        <div className="mb-8">
          <LiveTail requestId={running.request_id} startedMs={running.created_ms} />
        </div>
      )}

      {/* Stat strip */}
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="execs" value={sb?.exec_count ?? jobs.length} />
        <Tile label="succeeded" value={succeeded} rate={(sb?.exec_count ?? jobs.length) ? succeeded / (sb?.exec_count ?? jobs.length) : 0} />
        <Tile label="total time" value={dur(totalMs)} />
        <Tile label="last used" value={ago(sb?.last_used_ms)} />
      </div>

      {/* Activity histogram — execs over time */}
      <div className="surface mb-6 p-5">
        <div className="mb-4 flex items-baseline justify-between">
          <span className="flex items-center gap-2 text-[13px] text-zinc-400">
            <LiveDot on={live} size={6} />
            Activity
          </span>
          <span className="tnum text-[12px] text-zinc-600">
            {recentExecs} <span className="text-zinc-700">execs · last 30m</span>
          </span>
        </div>
        {recentExecs === 0 ? (
          <div className="grid h-[116px] place-items-center text-[12px] text-zinc-700">No activity in the last 30m</div>
        ) : (
          <BarChart data={activityHist} />
        )}
      </div>

      {/* Command bar — run or spawn directly in this sandbox */}
      <div className="surface mb-8 flex items-center gap-2 px-3 py-2">
        <span className="pl-2 font-mono text-[13px] text-zinc-600">$</span>
        <input
          value={cmd}
          onChange={(e) => setCmd(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="run a command in this sandbox…"
          className="min-w-0 flex-1 bg-transparent font-mono text-[13px] text-zinc-100 outline-none placeholder:text-zinc-700"
        />
        <button
          onClick={() => setKeepAlive((v) => !v)}
          title="Supervise: restart if it exits"
          className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
            keepAlive ? "bg-signal-500/15 text-signal-300" : "bg-white/[0.04] text-zinc-500 hover:text-zinc-300"
          }`}
        >
          keep-alive
        </button>
        <button
          onClick={run}
          disabled={runningCmd || !cmd.trim()}
          className="rounded-md bg-zinc-100 px-3 py-1.5 text-[12px] font-medium text-ink-950 transition-colors hover:bg-white disabled:opacity-40"
        >
          {runningCmd ? "…" : keepAlive ? "Spawn" : "Run"}
        </button>
      </div>

      {/* Ports & links — expose servers running in this sandbox */}
      <div className="surface mb-8 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3">
          <span className="text-[13px] font-medium text-zinc-300">Ports &amp; links</span>
          <div className="flex items-center gap-2">
            <input
              value={newPort}
              onChange={(e) => setNewPort(e.target.value.replace(/\D/g, ""))}
              onKeyDown={(e) => e.key === "Enter" && expose()}
              placeholder="port"
              className="w-20 rounded-md bg-black/30 px-2.5 py-1.5 text-center font-mono text-[12px] text-zinc-100 outline-none ring-1 ring-white/[0.06] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
            />
            <button onClick={expose} className="rounded-md bg-zinc-100 px-3 py-1.5 text-[12px] font-medium text-ink-950 transition-colors hover:bg-white">
              Expose
            </button>
          </div>
        </div>
        {ports.length === 0 ? (
          <div className="px-5 pb-4 text-[12px] text-zinc-600">
            Run a server in this sandbox (e.g. <span className="font-mono text-zinc-500">sbx.spawn("python -m http.server 8000")</span>), then expose its port to get a live URL.
          </div>
        ) : (
          <div className="divide-y divide-white/[0.05]">
            {ports.map((p) => (
              <div key={p.port} className="flex items-center gap-3 px-5 py-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-signal-500/12 font-mono text-[11px] text-signal-300">{p.port}</span>
                <a
                  href={`${API}${p.path}`}
                  target="_blank"
                  rel="noreferrer"
                  className="min-w-0 flex-1 truncate font-mono text-[12px] text-signal-400 hover:text-signal-300 hover:underline"
                >
                  {(p.url || `${API}${p.path}`).replace(/^https?:\/\//, "")}
                </a>
                <Copy text={p.url || `${typeof window !== "undefined" ? window.location.origin : ""}${p.path}`} label="copy" />
                <button onClick={() => { unexposePort(id, p.port).then(() => mutatePorts()); }} className="text-[11px] text-zinc-600 transition-colors hover:text-rose-400">
                  remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sub-tabs */}
      <div className="mb-5 flex items-center gap-1">
        <SubTab label="Execution history" active={tab === "logs"} onClick={() => setTab("logs")} />
        <SubTab label="Files" active={tab === "files"} onClick={() => setTab("files")} />
      </div>

      {tab === "logs" ? (
        jobs.length === 0 ? (
          <EmptyState title="No execs yet" hint="sbx.exec(...) runs appear here — click any row to stream its logs." />
        ) : (
          <JobsTable jobs={jobs} showMachine={false} />
        )
      ) : (
        <div className="flex h-[calc(100vh-25rem)] min-h-[400px] overflow-hidden rounded-xl bg-white/[0.012] shadow-[0_4px_24px_-12px_rgba(0,0,0,0.6)]">
          <FileBrowser
            flat
            list={(p) => fetchFiles(id, p)}
            read={(p) => fetchFile(id, p)}
            initialPath={sp.get("path") ?? ""}
            initialFile={sp.get("file")}
          />
        </div>
      )}
    </div>
  );
}

function SubTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`h-8 rounded-lg px-3 text-[13px] transition-colors ${
        active ? "bg-white/[0.07] font-medium text-white" : "text-zinc-500 hover:bg-white/[0.03] hover:text-zinc-300"
      }`}
    >
      {label}
    </button>
  );
}

function Back() {
  return (
    <Link href="/sandboxes" className="mb-6 inline-block text-[12px] text-zinc-600 transition-colors hover:text-zinc-300">
      ← Sandboxes
    </Link>
  );
}

function Tile({ label, value, rate }: { label: string; value: any; rate?: number }) {
  return (
    <div className="surface px-4 py-3">
      <div className="label">{label}</div>
      <div className="mt-1.5 tnum text-[20px] font-semibold leading-none tracking-tightest text-white">{value}</div>
      {rate !== undefined && (
        <div className="mt-2.5 flex items-center gap-2">
          <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/[0.07]">
            <div className="h-full rounded-full bg-signal-500" style={{ width: `${Math.round(rate * 100)}%` }} />
          </div>
          <span className="tnum text-[10px] text-zinc-600">{Math.round(rate * 100)}%</span>
        </div>
      )}
    </div>
  );
}
