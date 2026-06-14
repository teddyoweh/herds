"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { getSession } from "@/lib/platform";
import Link from "next/link";
import { motion, type Variants } from "framer-motion";

/* ------------------------------------------------------------------ *
 * Herds — public marketing landing page.
 * Warm editorial light theme (Orchid-grade): off-white paper, high-
 * contrast display serif (.ed), generous whitespace, restrained
 * signal-green accent. Borderless: elevation = white fill-lift + soft
 * shadow, never edge lines. Scrollytelling: each section is a centered
 * serif statement followed by a bespoke product card.
 * ------------------------------------------------------------------ */

const GITHUB = "https://github.com/teddyoweh/herds";

/* Flat surfaces on a pure-white page: cards are a subtle gray fill, inset tiles
   are white. No shadows, no borders — separation comes from fill alone. */
const CARD = "bg-[#f3f2ee]";
const INSET = "bg-white";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.65, ease: [0.22, 1, 0.36, 1] } },
};
const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
};

function Reveal({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-90px" }} transition={{ delay }} className={className}>
      {children}
    </motion.div>
  );
}

function Check({ size = 22 }: { size?: number }) {
  return (
    <span className="grid flex-none place-items-center rounded-full bg-signal-500 text-white" style={{ width: size, height: size }}>
      <svg width={Math.round(size * 0.5)} height={Math.round(size * 0.5)} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M3 8.5 6.5 12 13 4" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </span>
  );
}

/* ------------------------------------------------------------------ *
 * Top bar
 * ------------------------------------------------------------------ */

function TopBar() {
  const [account, setAccount] = useState<string | null>(null);
  useEffect(() => { const s = getSession(); if (s) setAccount(s.account); }, []);
  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] max-w-[1120px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <Logo size={22} />
          <span className="text-[16px] font-semibold tracking-tight text-stone-900">Herds</span>
        </Link>
        <div className="flex items-center gap-2">
          {account ? (
            <Link href="/dashboard" className="inline-flex items-center gap-1.5 rounded-full bg-signal-600 px-4 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-signal-500">
              Dashboard <span aria-hidden className="text-white/60">→</span>
            </Link>
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

/* ------------------------------------------------------------------ *
 * Shared editorial pieces
 * ------------------------------------------------------------------ */

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-[#f3f2ee] px-3 py-1 text-[12px] font-medium text-stone-600">
      <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" />
      {children}
    </span>
  );
}

/** Centered serif statement — the page's recurring editorial beat. */
function Statement({ eyebrow, title, sub }: { eyebrow?: string; title: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <Reveal className="mx-auto max-w-3xl text-center">
      {eyebrow && <div className="mb-4 text-[12px] font-medium uppercase tracking-[0.18em] text-signal-600">{eyebrow}</div>}
      <h2 className="ed mx-auto max-w-[20ch] text-[32px] leading-[1.07] text-stone-900 sm:text-[46px]">{title}</h2>
      {sub && <p className="ed-soft mx-auto mt-6 max-w-[36rem] text-[18px] leading-[1.5] text-stone-500 sm:text-[21px]">{sub}</p>}
    </Reveal>
  );
}

function Section({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`mx-auto max-w-[1080px] px-6 py-24 sm:py-28 ${className}`}>{children}</section>;
}

/** Window chrome bar shared by product mockups. */
function Chrome({ title }: { title?: string }) {
  return (
    <div className="flex items-center gap-2 bg-[#e9e8e3] px-4 py-3">
      <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
      <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
      <span className="h-3 w-3 rounded-full bg-[#28c840]" />
      {title && (
        <div className="mx-auto flex items-center gap-1.5 rounded-md bg-white px-3 py-1 text-[11px] text-stone-400">
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" className="text-stone-400"><rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" strokeWidth="2" /></svg>
          <span className="font-mono">{title}</span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Hero — command cluster + live dashboard card
 * ------------------------------------------------------------------ */

function CommandBar() {
  const EX = ["xcodebuild -scheme App build", "swift test --parallel", "npm run build && ./deploy.sh", "open -a Simulator"];
  const [i, setI] = useState(0);
  useEffect(() => { const t = setInterval(() => setI((v) => (v + 1) % EX.length), 2800); return () => clearInterval(t); }, []);
  return (
    <div className={`flex items-center gap-3 rounded-2xl px-4 py-3 ${CARD}`}>
      <span className="font-mono text-[13px] text-signal-600">$</span>
      <div className="min-w-0 flex-1 overflow-hidden whitespace-nowrap text-left font-mono text-[13px] text-stone-400">
        herds.mac().run(<span className="text-stone-500">&quot;</span>
        <motion.span key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.45 }} className="text-stone-800">{EX[i]}</motion.span>
        <span className="text-stone-500">&quot;</span>)
      </div>
      <Link href="/signup" className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-signal-600 text-white transition hover:bg-signal-500" aria-label="run">
        <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </Link>
    </div>
  );
}

function CurlPill() {
  const [copied, setCopied] = useState(false);
  const cmd = "curl -fsSL herds.run/install | sh";
  return (
    <button onClick={() => { navigator.clipboard?.writeText(cmd); setCopied(true); setTimeout(() => setCopied(false), 1400); }}
      className="group inline-flex items-center gap-2.5 rounded-full bg-[#f3f2ee] px-4 py-2.5 font-mono text-[12.5px] text-stone-500 transition hover:bg-[#ececea]">
      <span className="text-signal-600">$</span><span>{cmd}</span>
      <span className={`text-[11px] ${copied ? "text-signal-600" : "text-stone-400 group-hover:text-stone-600"}`}>{copied ? "copied" : "copy"}</span>
    </button>
  );
}

function FleetRow({ name, kind, load, delay }: { name: string; kind: string; load: number; delay: number }) {
  return (
    <div className={`flex items-center gap-3 rounded-xl ${INSET} px-3.5 py-3`}>
      <Logo size={26} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-[12.5px] font-semibold tracking-tight text-stone-900">{name}</span>
          <span className="tnum font-mono text-[11px] text-stone-400">{load}%</span>
        </div>
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-black/[0.08]">
          <motion.div initial={{ width: 0 }} whileInView={{ width: `${load}%` }} viewport={{ once: true }} transition={{ delay, duration: 1, ease: [0.22, 1, 0.36, 1] }} className="h-full rounded-full bg-signal-500" />
        </div>
        <div className="mt-1.5 text-[10px] text-stone-400">{kind}</div>
      </div>
    </div>
  );
}

const RUN_LINES: { node: React.ReactNode; cmd?: boolean }[] = [
  { cmd: true, node: <><span className="text-signal-600">$</span> <span className="text-stone-800">herds.mac(&quot;m3max&quot;).run(&quot;xcodebuild&quot;)</span></> },
  { node: <><span className="text-stone-400">→</span> building · M3 Max · Mac Studio</> },
  { node: <><span className="text-signal-600">✓</span> Build succeeded · <span className="text-stone-600">42.1s</span></> },
  { node: <><span className="text-signal-600">↗</span> exposed <span className="text-stone-500">:3000</span> → <span className="text-signal-600 underline decoration-signal-500/40 underline-offset-2">app.you.herds.run</span></> },
];

function DashboardCard() {
  return (
    <motion.div initial={{ opacity: 0, y: 28, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ delay: 0.4, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
      className={`relative mx-auto w-full max-w-[940px] overflow-hidden rounded-3xl ${CARD}`}>
      <Chrome title="you.herds.run" />
      <div className="grid sm:grid-cols-[1.05fr_1fr]">
        <div className="p-5 text-left">
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-semibold tracking-tight text-stone-700">Your fleet</span>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-stone-500"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> 3 online</span>
          </div>
          <div className="mt-4 space-y-2.5">
            <FleetRow name="M3 Max" kind="Mac Studio · 3 sandboxes" load={38} delay={0.7} />
            <FleetRow name="M2 Pro" kind="Mac mini · 5 sandboxes" load={71} delay={0.85} />
            <FleetRow name="M3" kind="MacBook Air · 1 sandbox" load={12} delay={1.0} />
          </div>
        </div>
        <div className="flex flex-col p-5 text-left">
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-semibold tracking-tight text-stone-700">Live run</span>
            <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-stone-400"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> m3max</span>
          </div>
          <motion.div className="mt-4 space-y-1.5 font-mono text-[11.5px] leading-[1.7] tnum" initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.45, delayChildren: 0.7 } } }}>
            {RUN_LINES.map((l, i) => (
              <motion.div key={i} variants={{ hidden: { opacity: 0, y: 3 }, show: { opacity: 1, y: 0 } }} transition={{ duration: 0.25 }} className={l.cmd ? "text-stone-800" : "text-stone-500"}>
                {l.node}
                {i === RUN_LINES.length - 1 && <span className="ml-1 inline-block h-[12px] w-[6px] translate-y-[2px] animate-breathe bg-signal-500/80 align-middle" />}
              </motion.div>
            ))}
          </motion.div>
          <div className="mt-auto pt-5">
            <div className="text-[10px] uppercase tracking-[0.14em] text-stone-400">Exposed</div>
            <div className="mt-2.5 space-y-1.5">
              {[{ port: ":3000", url: "app.you.herds.run" }, { port: ":8000", url: "api.you.herds.run" }].map((e) => (
                <div key={e.port} className={`flex items-center gap-2 rounded-lg ${INSET} px-2.5 py-1.5 font-mono text-[11px]`}>
                  <span className="text-stone-500">{e.port}</span><span className="text-stone-300">→</span><span className="truncate text-signal-600">{e.url}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="relative mx-auto max-w-[1080px] px-6 pb-16 pt-14 text-center">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-center"><Eyebrow>Modal, for Macs</Eyebrow></motion.div>
        <motion.h1 variants={stagger} initial="hidden" animate="show" className="ed mx-auto mt-6 max-w-[16ch] text-[12.5vw] leading-[0.98] text-stone-900 sm:text-[64px] lg:text-[80px]">
          <motion.span variants={fadeUp} className="block">Give your agents</motion.span>
          <motion.span variants={fadeUp} className="block">real Macs.</motion.span>
        </motion.h1>
        <motion.p initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }} className="ed-soft mx-auto mt-6 max-w-[37rem] text-[18px] leading-[1.5] text-stone-500 sm:text-[20px]">
          Connect any Mac you own and it becomes a programmable cloud runtime — driven by agents, SDKs, and CLIs from anywhere. One command to go live.
        </motion.p>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.34 }} className="mx-auto mt-8 max-w-[34rem]">
          <CommandBar />
          <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
            <Link href="/signup" className="inline-flex items-center rounded-full bg-signal-600 px-5 py-2.5 text-[14px] font-medium text-white transition-all hover:-translate-y-px hover:bg-signal-500">Start free</Link>
            <CurlPill />
          </div>
        </motion.div>
        <div className="mt-12"><DashboardCard /></div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * 02 — Wake up to a fleet (overnight runs, Orchid todo-card energy)
 * ------------------------------------------------------------------ */

const OVERNIGHT = [
  { done: true, title: "Build App.ipa", sub: "xcodebuild -scheme App · 42.1s" },
  { done: true, title: "swift test --parallel", sub: "128 passed · 0 failed" },
  { done: true, title: "Codesign & notarize", sub: "Developer ID · stapled" },
  { done: false, title: "Deploy preview", sub: "→ app.you.herds.run" },
  { done: false, title: "Snapshot build cache", sub: "volume: derived-data · 84 GB" },
];

function MorningCard() {
  return (
    <Reveal className={`mx-auto mt-14 w-full max-w-[480px] rounded-3xl p-3 ${CARD}`}>
      {OVERNIGHT.map((t, i) => (
        <div key={i} className="flex items-center gap-3.5 rounded-2xl px-4 py-3.5">
          {t.done ? <Check size={22} /> : <span className="h-[22px] w-[22px] flex-none rounded-full bg-[#ececec]" />}
          <div className="min-w-0">
            <div className={`text-[15px] font-semibold tracking-tight ${t.done ? "text-stone-400" : "text-stone-900"}`}>{t.title}</div>
            <div className="text-[12.5px] text-stone-400">{t.sub}</div>
          </div>
        </div>
      ))}
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 03 — Real macOS (mac window + tool chips)
 * ------------------------------------------------------------------ */

function MacWindowCard() {
  return (
    <Reveal className={`mx-auto mt-14 w-full max-w-[760px] overflow-hidden rounded-3xl ${CARD}`}>
      <Chrome title="App.xcodeproj — Xcode" />
      <div className="grid gap-5 p-6 sm:grid-cols-[1.3fr_1fr]">
        <div>
          <div className="flex items-center justify-between text-[12px]">
            <span className="font-semibold text-stone-700">Build · iOS Simulator</span>
            <span className="font-mono text-stone-400">arm64</span>
          </div>
          <div className="mt-4 space-y-2.5 font-mono text-[12px] text-stone-500">
            <div><span className="text-signal-600">✓</span> Resolved Swift packages</div>
            <div><span className="text-signal-600">✓</span> Compiled 214 Swift sources</div>
            <div><span className="text-stone-400">▸</span> Linking App.app…</div>
          </div>
          <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-black/[0.08]">
            <motion.div initial={{ width: 0 }} whileInView={{ width: "78%" }} viewport={{ once: true }} transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }} className="h-full rounded-full bg-signal-500" />
          </div>
          <div className="mt-2 text-[11px] text-stone-400">Building… 78%</div>
        </div>
        <div className={`grid grid-cols-2 gap-2 rounded-2xl ${INSET} p-3`}>
          {["Xcode", "Simulators", "Codesign", "AppleScript", "Homebrew", "Metal"].map((t) => (
            <span key={t} className="rounded-lg bg-[#f3f2ee] px-3 py-2 text-center font-mono text-[11px] text-stone-600">{t}</span>
          ))}
        </div>
      </div>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 04 — Capabilities (4-col break, Orchid columns)
 * ------------------------------------------------------------------ */

function MacIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><rect x="3" y="4" width="18" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><path d="M2 20h20M9 16l-.5 4M15 16l.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>; }
function PortIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.07 0l-3 3A5 5 0 0 0 11 21l1.71-1.71" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>; }
function VolumeIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><ellipse cx="12" cy="5" rx="8" ry="3" stroke="currentColor" strokeWidth="1.5" /><path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>; }
function BoltIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>; }

const CAPS = [
  { icon: <MacIcon />, title: "The real platform", body: "Xcode, iOS/macOS simulators, codesigning, AppleScript, Homebrew — not a stub or an emulator. The whole machine." },
  { icon: <PortIcon />, title: "Ports → URLs", body: "Run a server inside a sandbox and get a public link instantly. No inbound ports opened on your network." },
  { icon: <VolumeIcon />, title: "Persistent state", body: "Snapshot, suspend, resume. Mount durable volumes so caches and builds survive across runs and machines." },
  { icon: <BoltIcon />, title: "Driven by agents", body: "One API call hands an agent a full machine — files, GUI, network. Scoped, revocable, observable." },
];

function Capabilities() {
  return (
    <motion.div variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="mt-16 grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
      {CAPS.map((c) => (
        <motion.div key={c.title} variants={fadeUp}>
          {c.icon}
          <h3 className="ed mt-5 text-[21px] leading-snug text-stone-900">{c.title}</h3>
          <p className="mt-3 text-[13.5px] leading-relaxed text-stone-500">{c.body}</p>
        </motion.div>
      ))}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ *
 * 05 — Ship iOS apps end to end (pipeline card)
 * ------------------------------------------------------------------ */

const PIPELINE = [
  { label: "Clone repository", t: "1.2s", done: true },
  { label: "Resolve packages", t: "8.4s", done: true },
  { label: "Build · Release", t: "42.1s", done: true },
  { label: "Test · 128 cases", t: "19.7s", done: true },
  { label: "Codesign & notarize", t: "6.0s", done: true },
  { label: "Upload to TestFlight", t: "running", done: false },
];

function ShipCard() {
  return (
    <Reveal className={`mx-auto mt-14 w-full max-w-[560px] overflow-hidden rounded-3xl p-6 ${CARD}`}>
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-semibold tracking-tight text-stone-800">Pipeline · m3max</span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-signal-500/10 px-2.5 py-1 text-[11px] font-medium text-signal-600"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> shipping</span>
      </div>
      <div className="mt-5 space-y-1">
        {PIPELINE.map((s, i) => (
          <div key={i} className="flex items-center gap-3 py-2">
            {s.done ? <Check size={20} /> : <span className="h-5 w-5 flex-none animate-breathe rounded-full bg-signal-500/30" />}
            <span className={`flex-1 text-[14px] ${s.done ? "text-stone-500" : "font-medium text-stone-900"}`}>{s.label}</span>
            <span className="tnum font-mono text-[11.5px] text-stone-400">{s.t}</span>
          </div>
        ))}
      </div>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 06 — Expose a port → link (browser preview card)
 * ------------------------------------------------------------------ */

function ExposeCard() {
  return (
    <Reveal className={`mx-auto mt-14 w-full max-w-[720px] overflow-hidden rounded-3xl ${CARD}`}>
      <Chrome title="app.you.herds.run" />
      <div className="relative">
        {/* faux preview */}
        <div className="bg-[#f3f2ee] px-8 py-12 text-center">
          <div className="mx-auto h-2.5 w-24 rounded-full bg-signal-500/30" />
          <div className="mx-auto mt-4 h-5 w-2/3 rounded-md bg-black/[0.08]" />
          <div className="mx-auto mt-2.5 h-5 w-1/2 rounded-md bg-black/[0.06]" />
          <div className="mx-auto mt-6 h-9 w-32 rounded-full bg-signal-500/80" />
        </div>
        {/* mapping chip */}
        <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-white px-4 py-2 font-mono text-[12px]">
          <span className="text-stone-500">localhost:3000</span>
          <span className="text-stone-300">→</span>
          <span className="text-signal-600">app.you.herds.run</span>
          <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-signal-500/10 px-2 py-0.5 text-[10px] font-medium text-signal-600"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> live</span>
        </div>
      </div>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 07 — Observable (log stream + metrics)
 * ------------------------------------------------------------------ */

const LOGS = [
  "10:02:14  ▸ run started · sandbox sbx_9fa2",
  "10:02:15  ↳ xcodebuild -scheme App -sdk iphonesimulator",
  "10:02:57  ✓ ** BUILD SUCCEEDED ** (42.1s)",
  "10:02:58  ↗ expose :3000 → app.you.herds.run",
  "10:02:59  ● 200 GET /  · 38ms",
];

function Meter({ label, value, pct }: { label: string; value: string; pct: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-[11px]"><span className="text-stone-400">{label}</span><span className="tnum font-mono text-stone-600">{value}</span></div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-black/[0.08]"><motion.div initial={{ width: 0 }} whileInView={{ width: `${pct}%` }} viewport={{ once: true }} transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }} className="h-full rounded-full bg-signal-500" /></div>
    </div>
  );
}

function ObserveCard() {
  return (
    <Reveal className={`mx-auto mt-14 grid w-full max-w-[820px] overflow-hidden rounded-3xl ${CARD} sm:grid-cols-[1.4fr_1fr]`}>
      <div className="bg-[#0f141a] p-5">
        <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.16em] text-stone-500">live logs</div>
        <div className="space-y-1.5 font-mono text-[11.5px] leading-relaxed text-stone-300">
          {LOGS.map((l, i) => <div key={i} className={l.includes("✓") || l.includes("↗") ? "text-signal-400" : "text-stone-400"}>{l}</div>)}
          <div className="inline-block h-[12px] w-[6px] translate-y-[2px] animate-breathe bg-signal-400/80" />
        </div>
      </div>
      <div className="p-5">
        <div className="mb-4 text-[12px] font-semibold tracking-tight text-stone-700">m3max · metrics</div>
        <div className="space-y-4">
          <Meter label="CPU" value="38%" pct={38} />
          <Meter label="Memory" value="12.4 / 64 GB" pct={19} />
          <Meter label="Network" value="↑ 2.1 ↓ 8.7 MB/s" pct={54} />
          <Meter label="GPU" value="22%" pct={22} />
        </div>
      </div>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 08 — Snapshot / Suspend / Resume (lifecycle)
 * ------------------------------------------------------------------ */

function LifecycleCard() {
  const states = [
    { k: "Snapshot", d: "freeze disk + memory" },
    { k: "Suspend", d: "release the machine" },
    { k: "Resume", d: "back in < 2s" },
  ];
  return (
    <Reveal className={`mx-auto mt-14 w-full max-w-[720px] rounded-3xl p-7 ${CARD}`}>
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
        {states.map((s, i) => (
          <div key={s.k} className="flex flex-1 items-center gap-3">
            <div className={`flex-1 rounded-2xl ${INSET} px-4 py-4 text-center`}>
              <div className="ed text-[18px] text-stone-900">{s.k}</div>
              <div className="mt-1 text-[12px] text-stone-400">{s.d}</div>
            </div>
            {i < states.length - 1 && <span aria-hidden className="hidden text-stone-300 sm:block">→</span>}
          </div>
        ))}
      </div>
      <div className={`mt-3 flex items-center gap-3 rounded-2xl ${INSET} px-4 py-3 font-mono text-[12px]`}>
        <VolumeIcon />
        <span className="text-stone-600">volume: derived-data</span>
        <span className="text-stone-300">·</span>
        <span className="text-stone-500">84 GB</span>
        <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-signal-600"><span className="h-1.5 w-1.5 rounded-full bg-signal-500" /> mounted</span>
      </div>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 09 — One API call (code card)
 * ------------------------------------------------------------------ */

function CodeCard() {
  return (
    <Reveal className={`mx-auto mt-14 w-full max-w-[640px] overflow-hidden rounded-3xl font-mono text-[12.5px] sm:text-[13px] ${CARD}`}>
      <Chrome title="agent.py" />
      <pre className="overflow-x-auto px-6 py-6 leading-[1.9] text-stone-600">
        <code>
          <span className="text-stone-400">{"# hand an agent a real Mac\n"}</span>
          <span className="text-signal-600">{"mac"}</span>{" = herds."}<span className="text-stone-800">{"mac"}</span>{"()\n\n"}
          <span className="text-signal-600">{"build"}</span>{" = mac."}<span className="text-stone-800">{"run"}</span>{'("xcodebuild -scheme App")\n'}
          <span className="text-stone-800">{"url"}</span>{"   = mac."}<span className="text-stone-800">{"expose"}</span>{"(3000)  "}<span className="text-stone-400">{"# → public link"}</span>{"\n\n"}
          <span className="text-stone-800">{"agent"}</span>{".verify("}<span className="text-stone-800">{"url"}</span>{", screenshot="}<span className="text-signal-600">{"True"}</span>{")"}
        </code>
      </pre>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 10 — Scoped tokens
 * ------------------------------------------------------------------ */

const TOKENS = [
  { key: "hx_live_a91f…7c2", scope: "run", label: "agent-ci", age: "2d ago" },
  { key: "hx_live_4be0…9d1", scope: "read", label: "dashboard", age: "5d ago" },
  { key: "herds_sk_mqoa…EwA", scope: "admin", label: "host", age: "stable" },
];
const SCOPE_TONE: Record<string, string> = {
  run: "bg-signal-500/10 text-signal-600",
  read: "bg-stone-200/70 text-stone-600",
  admin: "bg-amber-500/10 text-amber-700",
};

function TokensCard() {
  return (
    <Reveal className={`mx-auto mt-14 w-full max-w-[640px] overflow-hidden rounded-3xl p-5 ${CARD}`}>
      <div className="mb-3 flex items-center justify-between px-1">
        <span className="text-[13px] font-semibold tracking-tight text-stone-800">API keys</span>
        <span className="text-[11px] text-stone-400">scoped · revocable</span>
      </div>
      <div className="space-y-2">
        {TOKENS.map((t) => (
          <div key={t.key} className={`flex items-center gap-3 rounded-2xl ${INSET} px-4 py-3`}>
            <span className={`rounded-md px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${SCOPE_TONE[t.scope]}`}>{t.scope}</span>
            <span className="font-mono text-[12.5px] text-stone-700">{t.key}</span>
            <span className="hidden text-[12px] text-stone-400 sm:inline">{t.label}</span>
            <span className="ml-auto text-[11px] text-stone-400">{t.age}</span>
            <button className="text-[11px] font-medium text-stone-400 transition-colors hover:text-red-500">Revoke</button>
          </div>
        ))}
      </div>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ *
 * 11 — Final CTA
 * ------------------------------------------------------------------ */

function FinalCTA() {
  return (
    <Section>
      <Reveal>
        <div className="relative overflow-hidden rounded-[28px] bg-stone-900 px-8 py-16 text-center sm:px-16 sm:py-20">
          <div className="relative">
            <h2 className="ed text-[32px] leading-[1.05] text-white sm:text-[46px]">Connect your Mac in 60 seconds.</h2>
            <p className="ed-soft mx-auto mt-4 max-w-md text-[18px] leading-relaxed text-stone-400">Every Mac becomes an API. Your own machine, your own infra — live with one command.</p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link href="/signup" className="inline-flex items-center rounded-full bg-signal-500 px-6 py-3 text-[14px] font-medium text-white transition-colors hover:bg-signal-400">Start free</Link>
              <Link href="/login" className="inline-flex items-center rounded-full bg-white/[0.08] px-6 py-3 text-[14px] font-medium text-stone-200 transition-colors hover:bg-white/[0.14]">Log in</Link>
            </div>
            <div className="mt-6 font-mono text-[12.5px] text-stone-500"><span className="text-signal-400">$</span> herds host</div>
          </div>
        </div>
      </Reveal>
    </Section>
  );
}

function Footer() {
  return (
    <footer className="mx-auto max-w-[1080px] px-6 pb-14 pt-6">
      <div className="h-px w-full bg-black/[0.07]" />
      <div className="flex flex-col items-start justify-between gap-6 pt-8 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2.5">
          <Logo size={20} />
          <span className="text-[14px] font-semibold tracking-tight text-stone-900">Herds</span>
          <span className="ml-2 text-[12.5px] text-stone-400">Your Mac is the cloud.</span>
        </div>
        <nav className="flex items-center gap-6 text-[13px] text-stone-500">
          <Link href={GITHUB} className="transition-colors hover:text-stone-900">Docs</Link>
          <Link href={GITHUB} className="transition-colors hover:text-stone-900">GitHub</Link>
          <Link href="https://spawnlabs.ai" className="transition-colors hover:text-stone-900">Spawn Labs</Link>
        </nav>
      </div>
      <div className="mt-8 text-[12px] text-stone-400">© 2026 Herds — a Spawn Labs project. All rights reserved.</div>
    </footer>
  );
}

/* ------------------------------------------------------------------ *
 * Page — editorial scrollytelling, 10+ sections
 * ------------------------------------------------------------------ */

export function Landing() {
  return (
    <div className="min-h-screen bg-white font-sans text-stone-900 antialiased">
      <TopBar />
      <main>
        <Hero />

        <Section>
          <Statement eyebrow="Always on" title={<>Wake up to a fleet,<br /> not a laptop.</>} sub="Your Macs stay online while you sleep — agents build, test, and ship through the night on the real hardware your users run." />
          <MorningCard />
        </Section>

        <Section>
          <Statement eyebrow="Real macOS" title={<>The whole platform.<br /> Not a Linux stub.</>} sub="Xcode, simulators, codesigning, AppleScript, Homebrew — the actual machine, exposed as programmable infrastructure." />
          <MacWindowCard />
          <Capabilities />
        </Section>

        <Section>
          <Statement eyebrow="End to end" title={<>Ship iOS apps, autonomously.</>} sub="From clone to TestFlight in one run — build, test, sign, notarize, deploy. No CI runners to babysit." />
          <ShipCard />
        </Section>

        <Section>
          <Statement eyebrow="Networking" title={<>Expose a port. Get a link.</>} sub="Run a server inside a sandbox and share it instantly — a named subdomain, real TLS, zero inbound ports opened." />
          <ExposeCard />
        </Section>

        <Section>
          <Statement eyebrow="Observability" title={<>Every run, fully observable.</>} sub="Stream logs, metrics, and status in real time. Nothing hidden, nothing stale — the machine narrates itself." />
          <ObserveCard />
        </Section>

        <Section>
          <Statement eyebrow="Stateful" title={<>Snapshot. Suspend. Resume.</>} sub="Freeze a machine mid-task and bring it back in seconds. Mount durable volumes so caches and builds persist." />
          <LifecycleCard />
        </Section>

        <Section>
          <Statement eyebrow="Built for agents" title={<>One API call. A whole machine.</>} sub="Your agents already write the code. Now they build it, run it, click through the app, and verify it — on real macOS." />
          <CodeCard />
        </Section>

        <Section>
          <Statement eyebrow="Security" title={<>A scoped key for every agent.</>} sub="Mint read, run, or admin tokens per task. Hand one to an agent, watch what it does, revoke it the moment you're done." />
          <TokensCard />
        </Section>

        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
