"use client";

import { useState } from "react";
import { SectionTitle, Copy } from "@/components/ui";
import { useToast } from "@/components/Toast";
import { API, useKeys, useHost, createKey, revokeKey } from "@/lib/api";

export default function SettingsPage() {
  const { data, mutate } = useKeys();
  const { data: host } = useHost();
  const toast = useToast();
  const [label, setLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [fresh, setFresh] = useState<string | null>(null);

  const keys = data?.keys ?? [];

  const create = async () => {
    setCreating(true);
    try {
      const r = await createKey(label.trim() || "default");
      setFresh(r.key);
      setLabel("");
      mutate();
      toast("API key created", "success");
    } catch {
      toast("Failed to create key", "error");
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (masked: string) => {
    const prefix = masked.split("…")[0];
    await revokeKey(prefix);
    mutate();
    toast("Key revoked");
  };

  const connectSnippet = `# install\nbrew install herds\n\n# connect this Mac\nherds connect`;

  return (
    <div className="max-w-3xl">
      <SectionTitle title="Settings" sub="Connect Macs and manage API access." />

      {/* Host & access — the public link + token for this host */}
      {host?.hosted && (
        <section className="mb-10">
          <h2 className="mb-3 text-[13px] font-medium text-zinc-300">Host &amp; access</h2>
          <div className="surface divide-y divide-white/[0.05] overflow-hidden">
            <Field label="Dashboard link" value={host.public_url} mono />
            <Field label="Host token" value={host.token} mono secret />
            <Field label="Add a Mac" value={host.connect} mono />
          </div>
          <p className="mt-2.5 text-[12px] text-zinc-600">
            Share the link + token to access this host from anywhere, or to add another Mac as a
            compute node.
          </p>
        </section>
      )}

      {/* Connect a Mac */}
      <section className="mb-10">
        <h2 className="mb-3 text-[13px] font-medium text-zinc-300">Connect a Mac</h2>
        <div className="surface overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3">
            <span className="text-[12px] text-zinc-500">Install the daemon, then sign in.</span>
            <Copy text={connectSnippet} label="copy" />
          </div>
          <pre className="overflow-x-auto bg-black/25 px-5 py-4 font-mono text-[12.5px] leading-[1.7] text-zinc-400">
{connectSnippet}
          </pre>
        </div>
        <p className="mt-3 text-[12px] text-zinc-600">
          Control plane: <span className="font-mono text-zinc-400">{API}</span>{" "}
          <span className="text-zinc-700">— set</span>{" "}
          <span className="font-mono text-zinc-500">HERDS_CONTROL_PLANE</span>{" "}
          <span className="text-zinc-700">to point a Mac at your own.</span>
        </p>
      </section>

      {/* API keys */}
      <section>
        <h2 className="mb-3 text-[13px] font-medium text-zinc-300">API keys</h2>

        {fresh && (
          <div className="surface mb-3 p-4">
            <div className="mb-2 text-[12px] text-signal-400">New key — copy it now, it won't be shown again.</div>
            <div className="flex items-center gap-3">
              <code className="min-w-0 flex-1 truncate rounded-md bg-black/30 px-3 py-2 font-mono text-[12px] text-zinc-200">
                {fresh}
              </code>
              <Copy text={fresh} />
              <button onClick={() => setFresh(null)} className="text-[11px] text-zinc-600 hover:text-zinc-300">dismiss</button>
            </div>
          </div>
        )}

        <div className="mb-4 flex gap-2">
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
            placeholder="Key label (e.g. ci, laptop)"
            className="flex-1 rounded-lg bg-black/30 px-3 py-2 text-[13px] text-zinc-100 outline-none ring-1 ring-white/[0.06] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
          />
          <button
            onClick={create}
            disabled={creating}
            className="rounded-lg bg-zinc-100 px-3.5 py-2 text-[12px] font-medium text-ink-950 transition-colors hover:bg-white disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create key"}
          </button>
        </div>

        {keys.length === 0 ? (
          <div className="surface px-5 py-6 text-[13px] text-zinc-600">No API keys yet.</div>
        ) : (
          <div className="hairline">
            {keys.map((k) => (
              <div key={k.masked} className="row -mx-3 flex items-center gap-4 rounded-md px-3 py-3">
                <span className="text-[13px] text-zinc-200">{k.label}</span>
                <code className="font-mono text-[12px] text-zinc-600">{k.masked}</code>
                <button onClick={() => revoke(k.masked)} className="ml-auto text-[12px] text-zinc-600 transition-colors hover:text-rose-400">
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Field({ label, value, mono, secret }: { label: string; value: string; mono?: boolean; secret?: boolean }) {
  const [show, setShow] = useState(false);
  const display = secret && !show ? "•".repeat(Math.min(value.length, 28)) : value;
  return (
    <div className="flex items-center gap-3 px-5 py-3">
      <span className="w-28 shrink-0 text-[12px] text-zinc-500">{label}</span>
      <code className={`min-w-0 flex-1 truncate text-[12px] text-zinc-300 ${mono ? "font-mono" : ""}`}>{display}</code>
      {secret && (
        <button onClick={() => setShow((s) => !s)} className="shrink-0 text-[11px] text-zinc-600 transition-colors hover:text-zinc-300">
          {show ? "hide" : "reveal"}
        </button>
      )}
      <Copy text={value} />
    </div>
  );
}
