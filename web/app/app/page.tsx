"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { LiveDot, StatePill, EmptyState } from "@/components/ui";
import { JobsTable } from "@/components/JobsTable";
import { useToast } from "@/components/Toast";
import { useApp, deleteApp } from "@/lib/api";
import { ago } from "@/lib/format";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AppDetailInner />
    </Suspense>
  );
}

function Back() {
  return (
    <Link href="/apps" className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-zinc-500 transition-colors hover:text-zinc-300">
      ← Apps
    </Link>
  );
}

function AppDetailInner() {
  const name = useSearchParams().get("name") ?? "";
  const { data, error } = useApp(name);
  const toast = useToast();
  const router = useRouter();
  const [confirmDel, setConfirmDel] = useState(false);

  if (error) {
    return (
      <div>
        <Back />
        <EmptyState title="App not found" hint={`No app named "${name}".`} />
      </div>
    );
  }
  if (!data) {
    return (
      <div>
        <Back />
        <div className="h-40 animate-pulse rounded-xl bg-white/[0.03]" />
      </div>
    );
  }

  const { app, functions, jobs, sandboxes } = data;

  const del = async () => {
    if (!confirmDel) {
      setConfirmDel(true);
      setTimeout(() => setConfirmDel(false), 3000);
      return;
    }
    try {
      await deleteApp(app.name);
      toast(`Deleted app ${app.name}`, "success");
      router.push("/apps");
    } catch (e: any) {
      toast(e.message || "Failed to delete", "error");
    }
  };

  return (
    <div>
      <Back />

      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <LiveDot on={!!app.deployed_ms} size={8} />
            <h1 className="text-[22px] font-semibold tracking-tightest text-white">{app.name}</h1>
            {app.deployed_ms ? (
              <span className="inline-flex items-center rounded-md bg-signal-500/10 px-2 py-0.5 text-[11px] font-medium text-signal-400">
                deployed
              </span>
            ) : null}
          </div>
          <div className="mt-1.5 text-[13px] text-zinc-500">{app.description || "no description"}</div>
        </div>
        <button
          onClick={del}
          className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors ${
            confirmDel ? "bg-rose-500 text-white" : "text-rose-300 hover:bg-rose-500/15"
          }`}
        >
          {confirmDel ? "Confirm delete" : "Delete"}
        </button>
      </div>

      {/* Stat band */}
      <div className="mb-8 grid grid-cols-4 gap-3">
        <StatTile label="Runs" value={jobs.length} />
        <StatTile label="Functions" value={functions.length} />
        <StatTile label="Sandboxes" value={sandboxes.length} />
        <StatTile label="Last active" text={ago(app.last_active_ms)} />
      </div>

      {/* Functions */}
      {functions.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-[13px] font-medium text-zinc-400">Functions</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {functions.map((f) => (
              <div key={f.name} className="surface p-4">
                <div className="flex items-center justify-between">
                  <code className="font-mono text-[13px] text-zinc-100">{f.name}</code>
                  <StatePill state={f.kind} />
                </div>
                <div className="mt-3 flex items-center justify-between text-[12px] text-zinc-500">
                  <span>{f.image || "python"}</span>
                  {f.schedule ? <code className="font-mono text-signal-400">{f.schedule}</code> : null}
                </div>
                {f.url ? (
                  <a
                    href={f.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 block truncate font-mono text-[12px] text-signal-400 hover:underline"
                  >
                    {f.url} ↗
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Runs */}
      <section className="mb-8">
        <h2 className="mb-3 text-[13px] font-medium text-zinc-400">Runs</h2>
        {jobs.length === 0 ? (
          <EmptyState title="No runs yet" hint="Runs stamped with this app show up here." />
        ) : (
          <JobsTable jobs={jobs} />
        )}
      </section>

      {/* Sandboxes */}
      {sandboxes.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-[13px] font-medium text-zinc-400">Sandboxes</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {sandboxes.map((s) => (
              <Link key={s.sandbox_id} href={`/sandbox?id=${s.sandbox_id}`} className="surface surface-hover block p-4">
                <div className="flex items-center gap-2.5">
                  <LiveDot on={!!s.live} size={7} />
                  <code className="font-mono text-[13px] text-zinc-100">{s.sandbox_id}</code>
                </div>
                <div className="mt-3 text-[12px] text-zinc-500">{s.image || "host environment"} · {s.exec_count} execs</div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatTile({ label, value, text, accent }: { label: string; value?: number; text?: string; accent?: boolean }) {
  return (
    <div className="surface px-5 py-4">
      <div className="flex items-center gap-1.5">
        {accent && <LiveDot size={6} />}
        <span className="label">{label}</span>
      </div>
      <div className="mt-2.5 tnum text-[22px] font-semibold leading-none tracking-tightest text-white">
        {text ?? (value ?? 0).toLocaleString()}
      </div>
    </div>
  );
}
