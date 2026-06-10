"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { SectionTitle, EmptyState } from "@/components/ui";
import { RowSkeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import { useSecrets, createSecret, deleteSecret } from "@/lib/api";
import { ago } from "@/lib/format";

export default function SecretsPage() {
  return (
    <Suspense fallback={null}>
      <SecretsInner />
    </Suspense>
  );
}

function SecretsInner() {
  const { data, mutate } = useSecrets();
  const toast = useToast();
  const [open, setOpen] = useState(useSearchParams().get("new") === "1");
  const [q, setQ] = useState("");
  const all = data?.secrets ?? [];
  const secrets = q ? all.filter((s) => s.name.toLowerCase().includes(q.toLowerCase())) : all;
  const keyCount = all.reduce((a, s) => a + s.keys.length, 0);

  return (
    <div>
      <SectionTitle
        title="Secrets"
        sub={`${all.length} secret${all.length === 1 ? "" : "s"} · ${keyCount} keys · injected as env at dispatch, never stored on the Mac`}
        right={
          <div className="flex items-center gap-2">
            {all.length > 0 && (
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search…"
                className="w-40 rounded-lg bg-white/[0.04] px-3 py-2 text-[13px] text-zinc-100 outline-none transition focus:bg-white/[0.06] placeholder:text-zinc-700"
              />
            )}
            <button
              onClick={() => setOpen(true)}
              className="rounded-lg bg-zinc-100 px-3.5 py-2 text-[12px] font-medium text-ink-950 transition-colors hover:bg-white"
            >
              New secret
            </button>
          </div>
        }
      />

      {!data ? (
        <RowSkeleton rows={3} />
      ) : all.length === 0 ? (
        <EmptyState
          title="No secrets yet"
          hint="Create a secret, then attach it: mac.run('python agent.py', secrets=['openai'])."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {secrets.map((s) => (
            <div key={s.name} className="surface surface-hover group p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[13px] font-medium text-zinc-100">{s.name}</div>
                  <div className="mt-0.5 text-[11px] text-zinc-700">created {ago(s.created_ms)}</div>
                </div>
                <button
                  onClick={async () => {
                    await deleteSecret(s.name);
                    mutate();
                    toast(`Secret "${s.name}" removed`);
                  }}
                  className="text-[12px] text-zinc-700 opacity-0 transition group-hover:opacity-100 hover:text-rose-400"
                >
                  Remove
                </button>
              </div>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {s.keys.map((k) => (
                  <span key={k} className="rounded-md bg-white/[0.04] px-2 py-0.5 font-mono text-[11px] text-zinc-500">
                    {k}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <AnimatePresence>
        {open && (
          <NewSecretModal
            onClose={() => setOpen(false)}
            onCreated={(name) => {
              setOpen(false);
              mutate();
              toast(`Secret "${name}" created`, "success");
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function NewSecretModal({ onClose, onCreated }: { onClose: () => void; onCreated: (name: string) => void }) {
  const [name, setName] = useState("");
  const [rows, setRows] = useState([{ k: "", v: "" }]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setErr("");
    const values: Record<string, string> = {};
    rows.forEach((r) => r.k && (values[r.k] = r.v));
    if (!name || Object.keys(values).length === 0) {
      setErr("Name and at least one key are required.");
      return;
    }
    setBusy(true);
    try {
      await createSecret(name, values);
      onCreated(name);
    } catch (e: any) {
      setErr(e.message || "Failed to create secret");
    } finally {
      setBusy(false);
    }
  };

  const input =
    "w-full rounded-lg bg-black/30 px-3 py-2 text-[13px] text-zinc-100 outline-none ring-1 ring-white/[0.06] transition focus:ring-signal-500/50 placeholder:text-zinc-700";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-sm"
    >
      <motion.div
        initial={{ scale: 0.97, y: 6 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.97, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl bg-ink-850 p-6 shadow-e2"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-semibold text-white">New secret</h3>
          <button onClick={onClose} className="text-[12px] text-zinc-600 hover:text-zinc-300">
            Esc
          </button>
        </div>

        <div className="label mt-6 mb-1.5">Name</div>
        <input autoFocus value={name} onChange={(e) => setName(e.target.value.replace(/\s/g, "-"))} placeholder="openai" className={input} />

        <div className="label mt-5 mb-1.5">Key / value</div>
        <div className="space-y-2">
          {rows.map((r, i) => (
            <div key={i} className="flex gap-2">
              <input
                value={r.k}
                onChange={(e) => { const n = [...rows]; n[i].k = e.target.value; setRows(n); }}
                placeholder="OPENAI_API_KEY"
                className={`${input} font-mono text-[12px]`}
              />
              <input
                value={r.v}
                type="password"
                onChange={(e) => { const n = [...rows]; n[i].v = e.target.value; setRows(n); }}
                placeholder="sk-…"
                className={`${input} font-mono text-[12px]`}
              />
            </div>
          ))}
        </div>
        <button onClick={() => setRows([...rows, { k: "", v: "" }])} className="mt-2 text-[12px] text-zinc-500 hover:text-zinc-200">
          Add pair
        </button>

        {err && <div className="mt-3 text-[12px] text-rose-400">{err}</div>}

        <div className="mt-7 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-3.5 py-2 text-[12px] text-zinc-500 hover:text-zinc-200">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={busy}
            className="rounded-lg bg-zinc-100 px-3.5 py-2 text-[12px] font-medium text-ink-950 transition hover:bg-white disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create secret"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
