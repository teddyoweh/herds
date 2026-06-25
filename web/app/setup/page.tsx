"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Logo } from "@/components/Logo";
import { getSession } from "@/lib/platform";

/* ------------------------------------------------------------------ *
 * herds.run/setup — the public, end-to-end setup guide. From nothing
 * to a fleet of Macs you drive from Python or the browser. Warm
 * editorial light theme, matched to the landing page.
 * ------------------------------------------------------------------ */

function Header() {
  const [account, setAccount] = useState<string | null>(null);
  useEffect(() => { const s = getSession(); if (s) setAccount(s.account); }, []);
  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] max-w-[960px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <Logo size={32} />
          <span className="text-[16px] font-semibold tracking-tight text-stone-900">Herds</span>
        </Link>
        <div className="flex items-center gap-2">
          <Link href="/docs" className="hidden rounded-lg px-3 py-1.5 text-[13px] text-stone-500 transition-colors hover:text-stone-900 sm:inline-flex">Docs</Link>
          {account ? (
            <Link href="/dashboard" className="inline-flex items-center gap-1.5 rounded-full bg-signal-600 px-4 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-signal-500">Dashboard <span aria-hidden className="text-white/60">→</span></Link>
          ) : (
            <>
              <Link href="/login" className="hidden rounded-lg px-3 py-1.5 text-[13px] text-stone-500 transition-colors hover:text-stone-900 sm:inline-flex">Log in</Link>
              <Link href="/signup" className="inline-flex items-center rounded-full bg-signal-600 px-4 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-signal-500">Start free</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1400); }}
      aria-label="Copy command"
      className={`shrink-0 rounded-md px-2 py-1 text-[11px] font-medium transition ${copied ? "text-signal-400" : "text-stone-500 hover:bg-white/[0.06] hover:text-stone-300"}`}
    >
      {copied ? "copied" : "copy"}
    </button>
  );
}

/* A dark terminal block: a copyable command line + optional faux output. */
function Term({ chrome, command, children }: { chrome: string; command?: string; children?: React.ReactNode }) {
  return (
    <div className="mt-4 overflow-hidden rounded-2xl bg-[#0d1117] shadow-[0_18px_50px_-26px_rgba(13,17,23,0.6)]">
      <div className="flex items-center gap-1.5 border-b border-white/[0.06] bg-white/[0.04] px-3.5 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="mx-auto font-mono text-[10.5px] text-stone-500">{chrome}</span>
        {command ? <CopyButton text={command} /> : <span className="w-9" />}
      </div>
      <pre className="overflow-x-auto px-5 py-4 font-mono text-[12.5px] leading-[1.9] text-stone-200">{children}</pre>
    </div>
  );
}

function Line({ c }: { c: string }) {
  return <div className="flex gap-2"><span className="select-none text-signal-400">$</span><span className="text-stone-100">{c}</span></div>;
}
function OK({ children }: { children: React.ReactNode }) {
  return <div className="pl-[18px] text-[11.5px] leading-[1.7] text-stone-500"><span className="text-signal-400">✓</span> {children}</div>;
}
function Note({ c }: { c: string }) {
  return <div className="text-[11.5px] text-stone-600">{c}</div>;
}

function Step({ n, title, children, body }: { n: number; title: string; body: React.ReactNode; children?: React.ReactNode }) {
  return (
    <section className="relative pl-12 sm:pl-14">
      <span className="absolute left-0 top-0 grid h-9 w-9 place-items-center rounded-full bg-stone-900 font-mono text-[14px] font-semibold text-white">{n}</span>
      <h2 className="text-[19px] font-semibold tracking-tight text-stone-900">{title}</h2>
      <div className="mt-2 max-w-[56ch] text-[14.5px] leading-relaxed text-stone-500">{body}</div>
      {children}
    </section>
  );
}

/* Installing the CLI: the curl one-liner (also grabs uv if missing) vs a
   plain pip install for Macs that already have Python. Same package either
   way — the toggle just meets you where you are. */
function InstallCLI() {
  const [tab, setTab] = useState<"curl" | "pip">("curl");
  return (
    <>
      <div className="mt-4 inline-flex rounded-full bg-[#f3f2ee] p-1 text-[12.5px]">
        <button onClick={() => setTab("curl")} className={`rounded-full px-3.5 py-1.5 font-medium transition ${tab === "curl" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}>One-liner</button>
        <button onClick={() => setTab("pip")} className={`rounded-full px-3.5 py-1.5 font-medium transition ${tab === "pip" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}>Already have Python</button>
      </div>
      {tab === "curl" ? (
        <Term chrome="your Mac — zsh" command="curl -fsSL herds.run/install | sh">
          <Note c="# pulls a self-contained runtime — nothing to install first" />
          <Line c="curl -fsSL herds.run/install | sh" />
          <OK>installed herds 0.1</OK>
        </Term>
      ) : (
        <Term chrome="your Mac — zsh" command="pip install herds">
          <Note c="# same package from PyPI — Python 3.11+ already on this Mac" />
          <Line c="pip install herds" />
          <OK>installed herds 0.1</OK>
        </Term>
      )}
    </>
  );
}

/* Adding a Mac: a fresh machine (one-liner installs + joins) vs one that
   already has herds (just connect). A small toggle keeps both honest. */
function AddMac() {
  const [tab, setTab] = useState<"fresh" | "has">("fresh");
  const fresh = "curl -fsSL herds.run/install | sh -s -- you.herds.run hx_…";
  return (
    <>
      <div className="mt-4 inline-flex rounded-full bg-[#f3f2ee] p-1 text-[12.5px]">
        <button onClick={() => setTab("fresh")} className={`rounded-full px-3.5 py-1.5 font-medium transition ${tab === "fresh" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}>A brand-new Mac</button>
        <button onClick={() => setTab("has")} className={`rounded-full px-3.5 py-1.5 font-medium transition ${tab === "has" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}>Already has Herds</button>
      </div>
      {tab === "fresh" ? (
        <Term chrome="on the new Mac — zsh" command={fresh}>
          <Note c="# one line: installs Herds, then joins your fleet" />
          <Line c="curl …/install | sh -s -- you.herds.run hx_…" />
          <OK>Mac mini · M2 Pro joined the fleet</OK>
        </Term>
      ) : (
        <Term chrome="on the other Mac — zsh" command="herds connect you.herds.run hx_…">
          <Note c="# herds already installed — just point it at your host" />
          <Line c="herds connect you.herds.run hx_…" />
          <OK>Mac Studio joined the fleet</OK>
        </Term>
      )}
    </>
  );
}

export default function SetupPage() {
  return (
    <div className="min-h-screen bg-white font-sans text-stone-900 antialiased">
      <Header />
      <main className="mx-auto max-w-[760px] px-6 pb-28 pt-14 sm:pt-20">
        {/* hero */}
        <div className="text-[12px] font-medium uppercase tracking-[0.18em] text-signal-600">Setup</div>
        <h1 className="ed mt-3 text-[26px] leading-[1.1] text-stone-900 sm:text-[34px]">From nothing to a fleet of Macs</h1>
        <p className="mt-4 max-w-[52ch] text-[15px] leading-relaxed text-stone-500">
          Install once, sign in through your browser, and host. Every Mac you own joins with a single line — then drive
          the whole fleet from Python or watch it live in the dashboard. A few minutes, start to finish.
        </p>

        {/* steps */}
        <div className="mt-14 space-y-14">
          <Step n={1} title="Install the CLI" body={<>One command on any Mac — it pulls a self-contained runtime, so there&rsquo;s nothing to install first. Already have Python? A plain <code className="rounded bg-[#f3f2ee] px-1.5 py-0.5 font-mono text-[13px] text-stone-700">pip install</code> grabs the same package.</>}>
            <InstallCLI />
          </Step>

          <Step n={2} title="Sign in from your browser" body={<>Run <code className="rounded bg-[#f3f2ee] px-1.5 py-0.5 font-mono text-[13px] text-stone-700">herds auth</code>. It opens your browser with a short code — confirm it matches, sign in, and the token syncs straight back to this Mac. No copy-pasting secrets.</>}>
            <Term chrome="your Mac — zsh" command="herds auth">
              <Line c="herds auth" />
              <Note c="# opens herds.run/activate — approve the code shown" />
              <OK>approved in browser</OK>
              <OK>signed in as <span className="text-stone-300">you@team.com</span></OK>
            </Term>
            <p className="mt-3 text-[13px] leading-relaxed text-stone-400">On a headless box? <code className="font-mono text-stone-500">herds auth --no-browser</code> prints the link + code, or <code className="font-mono text-stone-500">herds auth --token hx_…</code> signs in directly.</p>
          </Step>

          <Step n={3} title="Go live" body={<>Host turns this Mac into your control plane and opens a public, branded link through the relay — no inbound ports, no port-forwarding. Your browser opens already signed in.</>}>
            <Term chrome="your main Mac — zsh" command="herds host">
              <Line c="herds host" />
              <OK>control plane up · dashboard built</OK>
              <OK>live at <span className="text-signal-400">you.herds.run</span></OK>
              <Note c="# opening you.herds.run/?token=… — you're signed in" />
            </Term>
          </Step>

          <Step n={4} title="Add more Macs" body={<>Any other Mac you own joins the same fleet. Brand-new machine or one that already has Herds — pick your path. Repeat for as many as you like.</>}>
            <AddMac />
          </Step>

          <Step n={5} title="Drive it — Python or the web" body={<>Target the idlest matching Mac by tag, run anything, and expose a port as a public URL. Or just watch it all live in the dashboard the relay serves.</>}>
            <Term chrome="agent.py" command={`import herds\n\nmac = herds.mac(tag="xcode")\nmac.run("xcodebuild -scheme App")\nurl = mac.expose(3000)  # → public URL`}>
              <div><span className="text-[#c792ea]">import</span> <span className="text-stone-100">herds</span></div>
              <div className="h-3" />
              <div><span className="text-stone-100">mac</span> = herds.<span className="text-[#82aaff]">mac</span>(tag=<span className="text-[#e5c07b]">&quot;xcode&quot;</span>) <span className="text-stone-600"># idlest match</span></div>
              <div><span className="text-stone-100">mac</span>.<span className="text-[#82aaff]">run</span>(<span className="text-[#e5c07b]">&quot;xcodebuild -scheme App&quot;</span>)</div>
              <div><span className="text-stone-100">url</span> = <span className="text-stone-100">mac</span>.<span className="text-[#82aaff]">expose</span>(<span className="text-[#6cb6ff]">3000</span>) <span className="text-stone-600"># → public URL</span></div>
            </Term>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-full bg-stone-900 px-5 py-2.5 text-[13px] font-medium text-white transition hover:bg-stone-800">Open the dashboard <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 11 11 5M6 5h5v5" strokeLinecap="round" strokeLinejoin="round" /></svg></Link>
              <Link href="/docs" className="text-[13px] font-medium text-stone-500 underline-offset-4 transition hover:text-stone-900 hover:underline">Read the SDK docs</Link>
            </div>
          </Step>

          <Step n={6} title="Keep it running (optional)" body={<>Make a Mac a permanent node: a login agent restarts <code className="rounded bg-[#f3f2ee] px-1.5 py-0.5 font-mono text-[13px] text-stone-700">herds host</code> on boot and after a crash, so the fleet stays up on its own.</>}>
            <Term chrome="zsh" command="herds install">
              <Line c="herds install" />
              <OK>installed login agent · ai.spawnlabs.herds</OK>
              <OK>host will restart on login &amp; after crashes</OK>
            </Term>
          </Step>
        </div>

        {/* one Mac → many sandboxes aside */}
        <div className="mt-16 rounded-3xl bg-[#f3f2ee] p-7 sm:p-9">
          <div className="text-[12px] font-medium uppercase tracking-[0.16em] text-signal-600">Good to know</div>
          <h2 className="ed mt-3 text-[24px] leading-snug text-stone-900 sm:text-[28px]">One Mac is a whole fleet on its own</h2>
          <p className="mt-3 max-w-[58ch] text-[14.5px] leading-relaxed text-stone-500">
            Each machine isn&rsquo;t just one runtime — you can carve a single Mac mini into dozens of isolated, localized
            sandboxes, each with its own HOME, filesystem, and ports, all running in parallel and torn down clean.
            Drive the machine directly, or fan work out across the grid.
          </p>
          <Term chrome="agent.py" command={`with herds.mac("mac-mini").sandbox(image="xcode:26") as sbx:\n    sbx.exec("xcodebuild -scheme App archive")\n    url = sbx.expose(3000)`}>
            <div><span className="text-[#c792ea]">with</span> herds.<span className="text-[#82aaff]">mac</span>(<span className="text-[#e5c07b]">&quot;mac-mini&quot;</span>).<span className="text-[#82aaff]">sandbox</span>(image=<span className="text-[#e5c07b]">&quot;xcode:26&quot;</span>) <span className="text-[#c792ea]">as</span> sbx:</div>
            <div className="pl-6"><span className="text-stone-100">sbx</span>.<span className="text-[#82aaff]">exec</span>(<span className="text-[#e5c07b]">&quot;xcodebuild -scheme App archive&quot;</span>)</div>
            <div className="pl-6"><span className="text-stone-100">url</span> = sbx.<span className="text-[#82aaff]">expose</span>(<span className="text-[#6cb6ff]">3000</span>) <span className="text-stone-600"># its own public URL</span></div>
          </Term>
        </div>

        {/* footer CTA */}
        <div className="mt-16 flex flex-col items-center gap-4 rounded-3xl bg-[#0d1117] px-6 py-12 text-center">
          <h2 className="ed text-[26px] leading-tight text-white sm:text-[32px]">Connect your first Mac</h2>
          <p className="max-w-[40ch] text-[14px] leading-relaxed text-stone-400">Every Mac becomes an API. Your machines, your infra — live with one command.</p>
          <div className="mt-2 flex items-center gap-3">
            <Link href="/signup" className="inline-flex items-center rounded-full bg-signal-600 px-6 py-3 text-[14px] font-medium text-white transition hover:bg-signal-500">Start free</Link>
            <Link href="/docs" className="inline-flex items-center rounded-full bg-white/[0.08] px-6 py-3 text-[14px] font-medium text-stone-200 transition hover:bg-white/[0.14]">Docs</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
