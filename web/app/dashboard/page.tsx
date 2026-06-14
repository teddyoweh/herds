"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Logo } from "@/components/Logo";
import { useToast } from "@/components/Toast";
import {
  getSession, clearSession, getStatus, listTokens, createToken, revokeToken,
  type Session, type AccountStatus, type ApiToken,
} from "@/lib/platform";

export default function DashboardPage() {
  const router = useRouter();
  const toast = useToast();
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AccountStatus | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const s = getSession();
    if (!s) {
      router.replace("/login");
      return;
    }
    setSession(s);
    setReady(true);
  }, [router]);

  // Poll live status (is the Mac connected?).
  useEffect(() => {
    if (!session) return;
    let alive = true;
    const tick = async () => {
      const st = await getStatus(session.token);
      if (alive && st) setStatus(st);
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => { alive = false; clearInterval(id); };
  }, [session]);

  if (!ready || !session) return <div className="fixed inset-0 bg-ink-950" />;

  const online = status?.online ?? false;
  const authCmd = `herds auth --token ${session.token}`;

  function signOut() {
    clearSession();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen bg-ink-950">
      {/* top bar */}
      <header className="sticky top-0 z-40 bg-ink-950/70 backdrop-blur-xl">
        <div className="mx-auto flex h-[60px] max-w-[920px] items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <Logo size={26} />
            <span className="text-[15px] font-semibold tracking-tightest text-white">Herds</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-[13px] text-zinc-500 sm:inline">{status?.email || session.account}</span>
            <button onClick={signOut} className="rounded-lg px-3 py-1.5 text-[13px] text-zinc-400 transition hover:text-zinc-100">
              Sign out
            </button>
          </div>
        </div>
        <div className="h-px w-full bg-white/[0.05]" />
      </header>

      <motion.main
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="mx-auto max-w-[920px] px-6 py-12"
      >
        {/* status hero */}
        <div className="flex items-center gap-2.5">
          <span className={`h-2 w-2 rounded-full ${online ? "bg-signal-400 shadow-[0_0_8px_1px_rgba(52,211,158,0.6)] animate-breathe" : "bg-zinc-600"}`} />
          <span className="label !text-zinc-500">{online ? "Connected" : "Waiting for your Mac"}</span>
        </div>
        <h1 className="mt-3 text-[30px] font-semibold tracking-tightest text-white sm:text-[36px]">
          {online ? "Your Mac is live." : "Connect your Mac."}
        </h1>
        <p className="mt-2 text-[15px] leading-relaxed text-zinc-400">
          {online ? (
            <>It&apos;s serving at <a href={session.url} target="_blank" className="text-signal-400 underline-offset-2 hover:underline">{session.url.replace("https://", "")}</a>.</>
          ) : (
            <>Run two commands on any Mac and it goes live at <span className="text-zinc-200">{session.url.replace("https://", "")}</span>.</>
          )}
        </p>

        {/* primary CTA */}
        <div className="mt-7 flex flex-wrap gap-3">
          <a
            href={online ? `${session.url}/?token=${encodeURIComponent(session.token)}` : "#"}
            onClick={(e) => { if (!online) { e.preventDefault(); toast("Connect a Mac first — run the commands below.", "default"); } }}
            target={online ? "_blank" : undefined}
            className={`inline-flex items-center gap-1.5 rounded-full px-5 py-2.5 text-[14px] font-medium transition ${online ? "bg-signal-400 text-ink-950 hover:bg-signal-300" : "cursor-default bg-white/[0.06] text-zinc-500"}`}
          >
            Open my Mac dashboard <span aria-hidden>→</span>
          </a>
        </div>

        {/* connect steps */}
        <div className="surface mt-10 px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="label">Connect a Mac</div>
            <div className="text-[12px] text-zinc-600">2 steps</div>
          </div>

          <Step n={1} title="Authenticate this machine" cmd={authCmd} onCopy={() => toast("Copied", "default")} />
          <Step n={2} title="Start serving" cmd="herds host" onCopy={() => toast("Copied", "default")} />

          <div className="mt-5 flex items-center gap-2 rounded-lg bg-white/[0.02] px-3 py-2.5 text-[12.5px] text-zinc-500">
            <span className={`h-1.5 w-1.5 rounded-full ${online ? "bg-signal-400 animate-breathe" : "bg-zinc-600"}`} />
            {online ? "Mac connected — you're live." : "Waiting for your Mac to connect…"}
          </div>
        </div>

        {/* run from an agent */}
        <AgentCard url={session.url} token={session.token} onCopy={() => toast("Copied", "default")} />

        {/* scoped agent tokens */}
        {online && <TokensCard url={session.url} token={session.token} toast={toast} />}

        {/* account details */}
        <div className="surface mt-6 px-6 py-6">
          <div className="label mb-4">Account</div>
          <Row label="Account">{session.account}</Row>
          {status?.email && <Row label="Email">{status.email}</Row>}
          <Row label="Dashboard URL">
            <a href={session.url} target="_blank" className="text-signal-400 hover:underline">{session.url}</a>
          </Row>
          <Row label="Token" mono copyable value={session.token} onCopy={() => toast("Token copied", "default")} />
        </div>
      </motion.main>
    </div>
  );
}

function TokensCard({ url, token, toast }: { url: string; token: string; toast: (m: string, t?: "default" | "error") => void }) {
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [label, setLabel] = useState("");
  const [scope, setScope] = useState("run");
  const [minting, setMinting] = useState(false);
  const [fresh, setFresh] = useState<string | null>(null);

  const load = async () => { try { setTokens(await listTokens(url, token)); } catch { /* offline */ } };
  useEffect(() => { load(); }, [url, token]); // eslint-disable-line react-hooks/exhaustive-deps

  async function mint() {
    if (minting) return;
    setMinting(true);
    try {
      const r = await createToken(url, token, label.trim() || "agent", scope);
      setFresh(r.key);
      setLabel("");
      await load();
    } catch (e) { toast(e instanceof Error ? e.message : "Failed", "error"); }
    setMinting(false);
  }
  async function revoke(masked: string) {
    try { await revokeToken(url, token, masked); await load(); toast("Token revoked", "default"); }
    catch (e) { toast(e instanceof Error ? e.message : "Failed", "error"); }
  }

  return (
    <div className="surface mt-6 px-6 py-6">
      <div className="label">Agent tokens</div>
      <p className="mt-2 text-[12.5px] leading-relaxed text-zinc-500">
        Scoped, revocable keys — hand an agent a <span className="text-zinc-300">run</span> token, never your account.
      </p>

      {fresh && (
        <div className="mt-3 rounded-lg bg-signal-500/[0.08] px-3.5 py-3">
          <div className="text-[10.5px] uppercase tracking-[0.12em] text-signal-400">New token — shown once</div>
          <button
            onClick={() => { navigator.clipboard?.writeText(fresh); toast("Token copied", "default"); }}
            className="mt-1.5 flex w-full items-center justify-between gap-3 font-mono text-[12px] text-zinc-200"
          >
            <span className="truncate">{fresh}</span>
            <span className="shrink-0 text-[11px] text-zinc-500">Copy</span>
          </button>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          value={label} onChange={(e) => setLabel(e.target.value)} placeholder="label (e.g. my-agent)"
          className="min-w-0 flex-1 rounded-lg bg-black/30 px-3 py-2 text-[13px] text-zinc-100 outline-none ring-1 ring-white/[0.08] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
        />
        <select
          value={scope} onChange={(e) => setScope(e.target.value)}
          className="rounded-lg bg-black/30 px-2.5 py-2 text-[13px] text-zinc-200 outline-none ring-1 ring-white/[0.08]"
        >
          <option value="read">read</option>
          <option value="run">run</option>
          <option value="admin">admin</option>
        </select>
        <button
          onClick={mint} disabled={minting}
          className="rounded-lg bg-zinc-100 px-4 py-2 text-[13px] font-medium text-ink-950 transition hover:bg-white disabled:opacity-40"
        >
          {minting ? "…" : "Mint"}
        </button>
      </div>

      <div className="mt-4 divide-y divide-white/[0.05]">
        {tokens.map((t) => (
          <div key={t.masked} className="flex items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <span className="font-mono text-[12px] text-zinc-300">{t.masked}</span>
              <span className="ml-2 rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">{t.scope}</span>
              {t.label && <span className="ml-2 text-[12px] text-zinc-600">{t.label}</span>}
            </div>
            <button onClick={() => revoke(t.masked)} className="shrink-0 text-[11px] text-zinc-600 transition hover:text-rose-400">
              Revoke
            </button>
          </div>
        ))}
        {tokens.length === 0 && <div className="py-3 text-[12.5px] text-zinc-600">No agent tokens yet.</div>}
      </div>
    </div>
  );
}

function AgentCard({ url, token, onCopy }: { url: string; token: string; onCopy: () => void }) {
  const [reveal, setReveal] = useState(false);
  const shown = reveal ? token : token.slice(0, 7) + "…" + token.slice(-4);
  const snippet = `import herds
herds.configure(url="${url}", token="${token}")

mac = herds.mac()
mac.run("uname -msr")                  # run anything, from anywhere

# ship a whole codebase, then run it:
herds.Volume.from_name("repo").put("./my-app")
mac.run("python3 app/main.py", volumes={"app": herds.Volume.from_name("repo")})`;
  const display = snippet.replace(token, shown);
  return (
    <div className="surface mt-6 overflow-hidden px-6 py-6">
      <div className="flex items-center justify-between">
        <div className="label">Run it from an agent</div>
        <button onClick={() => setReveal((r) => !r)} className="text-[11px] text-zinc-600 transition hover:text-zinc-300">
          {reveal ? "hide token" : "reveal token"}
        </button>
      </div>
      <p className="mt-2 text-[12.5px] leading-relaxed text-zinc-500">
        Hand an agent these two strings and it runs on your Mac — no SSH, no setup.
      </p>
      <div className="mt-3 flex items-center gap-2 font-mono text-[12px] text-zinc-500">
        <span className="text-signal-400">$</span> pip install herds
      </div>
      <div className="relative mt-2">
        <pre className="overflow-x-auto rounded-lg bg-black/40 px-4 py-3.5 font-mono text-[12px] leading-[1.7] text-zinc-300">{display}</pre>
        <button
          onClick={() => { navigator.clipboard?.writeText(snippet); onCopy(); }}
          className="absolute right-2.5 top-2.5 rounded-md bg-white/[0.06] px-2 py-1 text-[11px] text-zinc-400 transition hover:bg-white/[0.1] hover:text-zinc-200"
        >
          Copy
        </button>
      </div>
    </div>
  );
}

function Step({ n, title, cmd, onCopy }: { n: number; title: string; cmd: string; onCopy: () => void }) {
  return (
    <div className="mt-5">
      <div className="flex items-center gap-2.5">
        <span className="grid h-5 w-5 place-items-center rounded-full bg-white/[0.06] text-[11px] text-zinc-400">{n}</span>
        <span className="text-[13.5px] text-zinc-300">{title}</span>
      </div>
      <button
        onClick={() => { navigator.clipboard?.writeText(cmd); onCopy(); }}
        className="surface-hover group mt-2 flex w-full items-center justify-between gap-3 rounded-lg bg-black/30 px-3.5 py-2.5 text-left font-mono text-[12.5px] text-zinc-200"
      >
        <span className="truncate"><span className="text-signal-400">$</span> {cmd}</span>
        <span className="shrink-0 text-[11px] text-zinc-600 group-hover:text-zinc-400">Copy</span>
      </button>
    </div>
  );
}

function Row({ label, children, mono, copyable, value, onCopy }: { label: string; children?: React.ReactNode; mono?: boolean; copyable?: boolean; value?: string; onCopy?: () => void }) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-white/[0.05] py-3 first:border-t-0">
      <span className="text-[13px] text-zinc-500">{label}</span>
      {copyable && value ? (
        <button
          onClick={() => { navigator.clipboard?.writeText(value); onCopy?.(); }}
          className="group flex items-center gap-2 font-mono text-[12.5px] text-zinc-300"
        >
          <span className="max-w-[260px] truncate">{value}</span>
          <span className="text-[11px] text-zinc-600 group-hover:text-zinc-400">Copy</span>
        </button>
      ) : (
        <span className={`text-[13px] text-zinc-200 ${mono ? "font-mono" : ""}`}>{children}</span>
      )}
    </div>
  );
}
