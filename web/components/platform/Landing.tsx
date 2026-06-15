"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { GitHubMark } from "@/components/Auth";
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

const SETUP: { cmd?: string; ok?: React.ReactNode }[] = [
  { cmd: "herds host" },
  { ok: <>This Mac · <span className="text-stone-200">M3 Max</span> · live at <span className="text-signal-400">you.herds.run</span></> },
  { cmd: "herds connect mac-mini.local" },
  { ok: <>Mac mini joined the fleet</> },
  { cmd: "herds connect studio.local" },
  { ok: <>Mac Studio joined the fleet</> },
];

/* The hero centerpiece — a setup terminal: a few commands turn your spare Macs
   into one fleet. (The part everyone loves, made explicit.) */
function SetupTerminal() {
  return (
    <div className="overflow-hidden rounded-2xl bg-[#0f141a] text-left shadow-[0_24px_60px_-26px_rgba(20,24,33,0.55)]">
      <div className="flex items-center gap-2 bg-white/[0.05] px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="mx-auto pr-10 font-mono text-[11px] text-stone-500">herds — zsh</span>
      </div>
      <div className="space-y-1 px-5 py-4 font-mono text-[12.5px] leading-[1.8]">
        {SETUP.map((l, i) => (
          <div key={i} className={l.cmd ? "pt-1.5 first:pt-0" : ""}>
            {l.cmd
              ? <><span className="text-signal-400">$</span> <span className="text-stone-100">{l.cmd}</span></>
              : <span className="text-stone-400"><span className="text-signal-400">✓</span> {l.ok}</span>}
          </div>
        ))}
        <div className="mt-2.5 flex items-center gap-2 text-[11.5px] text-stone-400">
          <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-400" /> <span className="text-stone-300">3 Macs online</span> · ready for agents
          <span className="ml-1 inline-block h-[12px] w-[6px] translate-y-[2px] animate-breathe bg-signal-400/80 align-middle" />
        </div>
      </div>
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

/* ---- dashboard mockup pieces ---- */

function NavIcon({ d }: { d: string }) {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{d.split("|").map((p, i) => <path key={i} d={p} />)}</svg>;
}
const NAV = [
  { label: "Overview", d: "M3 3h7v7H3z|M14 3h7v7h-7z|M14 14h7v7h-7z|M3 14h7v7H3z", active: true },
  { label: "Sandboxes", d: "M21 8V7l-9-4-9 4v10l9 4 9-4v-1|M3.3 7 12 11l8.7-4|M12 11v10", active: false },
  { label: "Machines", d: "M3 4h18v12H3z|M2 20h20|M9 16l-.5 4|M15 16l.5 4", active: false },
  { label: "Volumes", d: "M4 5c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z|M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5", active: false },
  { label: "Runs", d: "M5 3l14 9-14 9z", active: false },
];

function Spark({ points, tone = "text-signal-500" }: { points: string; tone?: string }) {
  return (
    <svg viewBox="0 0 80 26" preserveAspectRatio="none" className={`h-6 w-full ${tone}`}>
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StatTile({ label, value, delta, up = true, spark }: { label: string; value: string; delta: string; up?: boolean; spark: string }) {
  return (
    <div className="rounded-xl bg-[#f6f5f2] p-3">
      <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-stone-400">{label}</div>
      <div className="mt-1.5 flex items-end justify-between">
        <span className="tnum text-[22px] font-semibold leading-none tracking-tight text-stone-900">{value}</span>
        <span className={`text-[10px] font-medium ${up ? "text-signal-600" : "text-stone-400"}`}>{delta}</span>
      </div>
      <div className="mt-2"><Spark points={spark} tone={up ? "text-signal-500" : "text-stone-300"} /></div>
    </div>
  );
}

function FleetRow({ name, kind, load, delay }: { name: string; kind: string; load: number; delay: number }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-[#f6f5f2] px-3 py-2.5">
      <Logo size={24} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-semibold tracking-tight text-stone-900">{name}</span>
          <span className="tnum text-[10.5px] text-stone-400">{load}%</span>
        </div>
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-black/[0.07]">
          <motion.div initial={{ width: 0 }} whileInView={{ width: `${load}%` }} viewport={{ once: true }} transition={{ delay, duration: 1, ease: [0.22, 1, 0.36, 1] }} className="h-full rounded-full bg-signal-500" />
        </div>
        <div className="mt-1 text-[9.5px] text-stone-400">{kind}</div>
      </div>
      <span className="inline-flex h-1.5 w-1.5 shrink-0 animate-breathe rounded-full bg-signal-500" />
    </div>
  );
}

const ACTIVITY: { tone: "ok" | "link" | "dot"; head: React.ReactNode; meta: string; time: string }[] = [
  { tone: "ok", head: <>Build succeeded <span className="text-stone-400">· App.ipa</span></>, meta: "m3max · 42.1s", time: "2m" },
  { tone: "link", head: <>Exposed <span className="text-signal-600">app.you.herds.run</span></>, meta: ":3000 · TLS", time: "5m" },
  { tone: "ok", head: <>Tests passed <span className="text-stone-400">· 128</span></>, meta: "swift test", time: "8m" },
  { tone: "dot", head: <>Sandbox started</>, meta: "sbx_9fa2 · m2pro", time: "14m" },
  { tone: "ok", head: <>Snapshot saved <span className="text-stone-400">· derived-data</span></>, meta: "84 GB volume", time: "21m" },
];

function ActivityRow({ a }: { a: (typeof ACTIVITY)[number] }) {
  const dot =
    a.tone === "ok" ? <Check size={16} />
    : a.tone === "link" ? <span className="grid h-4 w-4 place-items-center rounded-full bg-signal-500/15 text-signal-600"><svg width="9" height="9" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 11 11 5M6 5h5v5" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
    : <span className="h-4 w-4 rounded-full bg-stone-200" />;
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      {dot}
      <div className="min-w-0 flex-1 leading-tight">
        <div className="truncate text-[12px] text-stone-800">{a.head}</div>
        <div className="text-[10px] text-stone-400">{a.meta}</div>
      </div>
      <span className="shrink-0 text-[10px] tabular-nums text-stone-400">{a.time}</span>
    </div>
  );
}

function DashboardCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 28, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.4, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
      className={`relative mx-auto w-full max-w-[1000px] overflow-hidden rounded-3xl ${CARD}`}
    >
      <Chrome title="you.herds.run" />
      <div className="grid grid-cols-1 sm:grid-cols-[176px_1fr]">
        {/* sidebar */}
        <aside className="hidden flex-col gap-4 p-4 sm:flex">
          <div className="flex items-center gap-2 px-1">
            <Logo size={22} />
            <div className="leading-none">
              <div className="text-[12.5px] font-semibold text-stone-900">spawnlabs</div>
              <div className="mt-0.5 text-[9.5px] text-stone-400">Team · Pro</div>
            </div>
          </div>
          <nav className="space-y-0.5">
            {NAV.map((n) => (
              <div key={n.label} className={`flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[12.5px] ${n.active ? "bg-white font-medium text-stone-900" : "text-stone-500"}`}>
                <span className={n.active ? "text-signal-600" : "text-stone-400"}><NavIcon d={n.d} /></span>
                {n.label}
              </div>
            ))}
          </nav>
          <div className="mt-auto flex items-center gap-2 rounded-lg bg-white px-2.5 py-2">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-signal-500/15 text-[10px] font-semibold text-signal-700">T</span>
            <div className="leading-none">
              <div className="text-[11px] font-medium text-stone-800">Teddy</div>
              <div className="mt-0.5 text-[9px] text-stone-400">teddy@spawnlabs.ai</div>
            </div>
          </div>
        </aside>

        {/* main canvas */}
        <main className="bg-white p-5 text-left">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[15px] font-semibold tracking-tight text-stone-900">Overview</div>
              <div className="mt-0.5 text-[11px] text-stone-400">Your fleet at a glance</div>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-signal-500/10 px-2.5 py-1 text-[11px] font-medium text-signal-700">
              <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> 3 Macs online
            </span>
          </div>

          {/* stat tiles */}
          <div className="mt-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            <StatTile label="Machines" value="3" delta="online" spark="0,18 16,16 32,17 48,8 64,10 80,6" />
            <StatTile label="Sandboxes" value="9" delta="+2" spark="0,20 16,14 32,16 48,9 64,11 80,5" />
            <StatTile label="Runs today" value="1,284" delta="+18%" spark="0,22 16,17 32,12 48,14 64,7 80,4" />
            <StatTile label="Avg build" value="42s" delta="-6%" up={false} spark="0,8 16,12 32,9 48,13 64,11 80,15" />
          </div>

          {/* fleet + activity */}
          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[1.05fr_1fr]">
            <section>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-stone-400">Fleet</span>
                <span className="text-[10.5px] text-stone-400">CPU</span>
              </div>
              <div className="space-y-2">
                <FleetRow name="M3 Max" kind="Mac Studio · 3 sandboxes" load={38} delay={0.7} />
                <FleetRow name="M2 Pro" kind="Mac mini · 5 sandboxes" load={71} delay={0.85} />
                <FleetRow name="M3" kind="MacBook Air · 1 sandbox" load={12} delay={1.0} />
              </div>
            </section>
            <section>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-stone-400">Live activity</span>
                <span className="inline-flex items-center gap-1.5 text-[10px] text-stone-400"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> live</span>
              </div>
              <div className="rounded-xl bg-[#f6f5f2] px-3 py-1.5">
                {ACTIVITY.map((a, i) => <ActivityRow key={i} a={a} />)}
              </div>
            </section>
          </div>
        </main>
      </div>
    </motion.div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="relative mx-auto max-w-[1080px] px-6 pb-16 pt-14 text-center">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-center"><Eyebrow>Modal, for Macs</Eyebrow></motion.div>
        <motion.h1 variants={stagger} initial="hidden" animate="show" className="ed mx-auto mt-6 max-w-[16ch] text-[10vw] leading-[1] text-stone-900 sm:text-[48px] lg:text-[60px]">
          <motion.span variants={fadeUp} className="block">Give your agents</motion.span>
          <motion.span variants={fadeUp} className="block">real Macs.</motion.span>
        </motion.h1>
        <motion.p initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }} className="ed-soft mx-auto mt-6 max-w-[37rem] text-[18px] leading-[1.5] text-stone-500 sm:text-[20px]">
          Connect any Mac you own and it becomes a programmable cloud runtime — driven by agents, SDKs, and CLIs from anywhere.
        </motion.p>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.34 }} className="mx-auto mt-8 max-w-[40rem]">
          <SetupTerminal />
          <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
            <Link href="/signup" className="inline-flex items-center rounded-full bg-signal-600 px-5 py-2.5 text-[14px] font-medium text-white transition-all hover:-translate-y-px hover:bg-signal-500">Start free</Link>
            <CurlPill />
          </div>
        </motion.div>
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

/* syntax helpers for the Xcode editor */
const K = ({ c }: { c: string }) => <span className="text-[#9b4dca]">{c}</span>;       // keyword
const Ty = ({ c }: { c: string }) => <span className="text-[#0d8a72]">{c}</span>;      // type
const St = ({ c }: { c: string }) => <span className="text-[#c0392b]">{c}</span>;      // string
const Nu = ({ c }: { c: string }) => <span className="text-[#2d6df6]">{c}</span>;      // number
const At = ({ c }: { c: string }) => <span className="text-[#d6336c]">{c}</span>;      // attribute
const Pr = ({ c }: { c: string }) => <span className="text-[#0d8a72]">{c}</span>;      // member

const SWIFT: React.ReactNode[] = [
  <><K c="import" /> <Ty c="SwiftUI" /></>,
  <> </>,
  <><K c="struct" /> <Ty c="ContentView" />: <Ty c="View" /> {"{"}</>,
  <>{"  "}<At c="@State" /> <K c="private" /> <K c="var" /> builds = <Nu c="0" /></>,
  <> </>,
  <>{"  "}<K c="var" /> body: <K c="some" /> <Ty c="View" /> {"{"}</>,
  <>{"    "}<Ty c="VStack" />(spacing: <Nu c="16" />) {"{"}</>,
  <>{"      "}<Ty c="Text" />(<St c="&quot;Herds&quot;" />)</>,
  <>{"        "}.<Pr c="font" />(.<Pr c="largeTitle" />)</>,
  <>{"      "}<Ty c="Button" />(<St c="&quot;Run build&quot;" />) {"{"} builds += <Nu c="1" /> {"}"}</>,
  <>{"        "}.<Pr c="buttonStyle" />(.<Pr c="borderedProminent" />)</>,
  <>{"    "}{"}"}</>,
  <>{"  "}{"}"}</>,
  <>{"}"}</>,
];

const FILES: { name: string; depth: number; folder?: boolean; active?: boolean }[] = [
  { name: "App", depth: 0, folder: true },
  { name: "HerdsApp.swift", depth: 1 },
  { name: "Views", depth: 1, folder: true },
  { name: "ContentView.swift", depth: 2, active: true },
  { name: "FeedView.swift", depth: 2 },
  { name: "Models", depth: 1, folder: true },
  { name: "Mac.swift", depth: 2 },
  { name: "Assets.xcassets", depth: 1, folder: true },
];

function MacWindowCard() {
  return (
    <Reveal className="mx-auto mt-14 w-full max-w-[900px]">
      <div className="rounded-[28px] bg-[#eef1f6] p-4 sm:p-7">
        <div className="overflow-hidden rounded-xl bg-[#fbfbfa] shadow-[0_24px_70px_-24px_rgba(20,24,33,0.4)] ring-1 ring-black/[0.06]">
          {/* title bar */}
          <div className="flex items-center gap-2 bg-[#e9e8e4] px-3.5 py-2.5">
            <span className="h-3 w-3 rounded-full bg-[#ff5f57]" /><span className="h-3 w-3 rounded-full bg-[#febc2e]" /><span className="h-3 w-3 rounded-full bg-[#28c840]" />
            <span className="mx-auto flex items-center gap-2 text-[11px] text-stone-500">
              <span className="font-semibold text-stone-700">App</span>
              <span className="text-stone-400">›</span> iPhone 15 Pro
            </span>
            <span className="flex items-center gap-1 rounded-md bg-signal-600 px-2 py-1 text-[10px] font-medium text-white">
              <svg width="8" height="8" viewBox="0 0 16 16" fill="currentColor"><path d="M4 3l9 5-9 5z" /></svg> Run
            </span>
          </div>

          {/* 3-pane IDE */}
          <div className="grid grid-cols-[120px_1fr] sm:grid-cols-[148px_1fr_150px]">
            {/* navigator */}
            <div className="bg-[#f3f2ef] py-3 text-left">
              <div className="px-3 pb-2 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-stone-400">Project</div>
              {FILES.map((f) => (
                <div key={f.name} className={`flex items-center gap-1.5 px-3 py-[3px] text-[11px] ${f.active ? "bg-[#dbe6ff] text-stone-900" : "text-stone-500"}`} style={{ paddingLeft: 12 + f.depth * 11 }}>
                  <span className={f.folder ? "text-[#5b9bd5]" : f.active ? "text-signal-600" : "text-stone-400"}>
                    {f.folder
                      ? <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
                      : <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 2h8l4 4v16H6z" strokeLinejoin="round" /></svg>}
                  </span>
                  <span className="truncate">{f.name}</span>
                </div>
              ))}
            </div>

            {/* editor */}
            <div className="flex bg-white">
              <div className="select-none border-r border-black/[0.05] py-3 pl-3 pr-2 text-right font-mono text-[10.5px] leading-[1.72] text-stone-300 tnum">
                {SWIFT.map((_, i) => <div key={i}>{i + 1}</div>)}
              </div>
              <pre className="flex-1 overflow-x-auto py-3 pl-3 font-mono text-[11px] leading-[1.72] text-stone-700">
                {SWIFT.map((l, i) => <div key={i}>{l}</div>)}
              </pre>
            </div>

            {/* simulator preview */}
            <div className="hidden items-center justify-center bg-[#f3f2ef] p-4 sm:flex">
              <div className="w-[118px] overflow-hidden rounded-[22px] bg-white shadow-[0_10px_30px_-10px_rgba(20,24,33,0.35)] ring-1 ring-black/[0.06]">
                <div className="relative flex h-5 items-center justify-center bg-white">
                  <span className="absolute top-1.5 h-1 w-8 rounded-full bg-stone-200" />
                </div>
                <div className="flex flex-col items-center gap-3 px-3 pb-6 pt-4">
                  <span className="ed text-[18px] text-stone-900">Herds</span>
                  <span className="tnum text-[11px] text-stone-400">builds: 1</span>
                  <span className="mt-1 rounded-lg bg-signal-600 px-4 py-1.5 text-[10px] font-medium text-white">Run build</span>
                </div>
              </div>
            </div>
          </div>

          {/* status bar */}
          <div className="flex items-center gap-2 border-t border-black/[0.05] bg-[#f3f2ef] px-3.5 py-2 text-[11px]">
            <Check size={15} />
            <span className="font-medium text-stone-700">Build Succeeded</span>
            <span className="text-stone-400">· App.app · 42.1s</span>
            <span className="ml-auto font-mono text-[10px] text-stone-400">arm64 · Debug</span>
          </div>
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
function ShipIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17l1.5 3h13L20 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>; }
function EyeIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.5" /></svg>; }

/* ---- crafted capability illustrations (SVG + UI, animated) ---- */

function FleetGlyph({ x, y, t }: { x: number; y: number; t: string }) {
  const gx = x - 30, gy = y - 1;
  if (t === "box") return <rect x={gx + 1} y={gy - 6} width="13" height="13" rx="2.6" className="fill-none stroke-stone-400" strokeWidth="1.2" />;
  if (t === "lap") return <g className="stroke-stone-400" strokeWidth="1.2" fill="none" strokeLinecap="round"><rect x={gx} y={gy - 6} width="15" height="9" rx="1.4" /><path d={`M${gx - 1.5} ${gy + 4.5} h18`} /></g>;
  return <g className="stroke-stone-400" strokeWidth="1.2" fill="none" strokeLinecap="round"><rect x={gx} y={gy - 7} width="15" height="10" rx="1.4" /><path d={`M${gx + 7.5} ${gy + 3} v2 M${gx + 4} ${gy + 5.5} h7`} /></g>;
}

function FleetViz() {
  const nodes = [
    { x: 100, y: 52, label: "M3 Max", t: "mon" },
    { x: 420, y: 48, label: "Mac mini", t: "box" },
    { x: 94, y: 150, label: "Mac Studio", t: "mon" },
    { x: 426, y: 152, label: "MacBook", t: "lap" },
  ];
  const d = (n: { x: number; y: number }) => `M260,100 Q260,${n.y} ${n.x},${n.y}`;
  return (
    <svg viewBox="0 0 520 200" className="h-full w-full font-sans">
      <defs>
        <radialGradient id="fleetGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgb(27,189,134)" stopOpacity="0.16" />
          <stop offset="100%" stopColor="rgb(27,189,134)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="260" cy="100" r="86" fill="url(#fleetGlow)" />
      {/* curved connectors */}
      {nodes.map((n, i) => <path key={"p" + i} id={`fp${i}`} d={d(n)} fill="none" className="stroke-signal-500/25" strokeWidth="1.5" />)}
      {/* dispatch particles (hub → node) */}
      {nodes.map((n, i) => (
        <circle key={"pt" + i} r="2.8" className="fill-signal-500">
          <animateMotion dur="2.1s" repeatCount="indefinite" begin={`${i * 0.42}s`} calcMode="spline" keyPoints="0;1" keyTimes="0;1" keySplines="0.4 0 0.2 1">
            <mpath href={`#fp${i}`} />
          </animateMotion>
        </circle>
      ))}
      {/* nodes */}
      {nodes.map((n, i) => (
        <g key={"n" + i}>
          <rect x={n.x - 45} y={n.y - 17} width="90" height="34" rx="11" className="fill-white" />
          <FleetGlyph x={n.x} y={n.y} t={n.t} />
          <text x={n.x - 10} y={n.y + 3.5} className="fill-stone-700" fontSize="9.5" fontWeight="600">{n.label}</text>
          <circle cx={n.x + 33} cy={n.y - 9} r="2.4" className="fill-signal-500" />
        </g>
      ))}
      {/* pulse rings */}
      {[0, 1].map((k) => (
        <motion.circle key={k} cx="260" cy="100" r="24" className="fill-none stroke-signal-500/40" strokeWidth="1.3" animate={{ r: [24, 52], opacity: [0.45, 0] }} transition={{ duration: 2.6, repeat: Infinity, ease: "easeOut", delay: k * 1.3 }} />
      ))}
      {/* hub */}
      <rect x={236} y={76} width="48" height="48" rx="14" className="fill-signal-600" />
      <g className="stroke-white" strokeWidth="1.7" strokeLinecap="round" opacity="0.9" fill="none"><path d="M260 90 L251 112 M260 90 L269 112 M251 112 L269 112" /></g>
      <circle cx="260" cy="89" r="3.4" className="fill-white" /><circle cx="250" cy="113" r="3.4" className="fill-white" /><circle cx="270" cy="113" r="3.4" className="fill-white" />
      {/* status pill */}
      <rect x="18" y="16" width="96" height="22" rx="11" className="fill-white" />
      <circle cx="33" cy="27" r="3" className="fill-signal-500" />
      <text x="42" y="30.5" className="fill-stone-600" fontSize="9.5" fontWeight="600">4 Macs · online</text>
    </svg>
  );
}

function AgentsViz() {
  const macs = [{ n: "M3 Max", ok: true }, { n: "Mac mini", ok: true }, { n: "Studio", ok: false }];
  return (
    <div className="flex h-full flex-col justify-center gap-3 px-6">
      <div className="mx-auto flex w-full max-w-[230px] items-center gap-2 rounded-xl bg-white px-3 py-2 text-[11px] text-stone-600 shadow-[0_2px_8px_-2px_rgba(20,24,33,0.12)]">
        <span className="grid h-4 w-4 place-items-center rounded bg-signal-600 text-[8px] font-bold text-white">⌘</span>
        <span className="truncate">&ldquo;run the suite on every Mac&rdquo;</span>
      </div>
      <svg viewBox="0 0 230 22" className="mx-auto h-5 w-[230px]"><g className="stroke-signal-500/40" strokeWidth="1.3" fill="none"><path d="M115 0 V8 M115 8 H40 V20 M115 8 H115 V20 M115 8 H190 V20" /></g></svg>
      <div className="mx-auto grid w-full max-w-[260px] grid-cols-3 gap-2">
        {macs.map((m) => (
          <div key={m.n} className="rounded-lg bg-white px-2 py-2 text-center shadow-[0_1px_4px_-1px_rgba(20,24,33,0.1)]">
            <div className="mx-auto mb-1 h-1.5 w-1.5 rounded-full" />
            <div className="text-[9.5px] font-semibold text-stone-700">{m.n}</div>
            <div className="mt-1 flex justify-center">
              {m.ok ? <Check size={14} /> : <span className="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-signal-500/30 border-t-signal-500" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BrowserViz() {
  return (
    <div className="relative flex h-full items-center px-6">
      <div className="w-full overflow-hidden rounded-xl bg-white shadow-[0_10px_30px_-12px_rgba(20,24,33,0.25)]">
        <div className="flex items-center gap-1.5 bg-[#f1efe9] px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-[#ff5f57]" /><span className="h-2 w-2 rounded-full bg-[#febc2e]" /><span className="h-2 w-2 rounded-full bg-[#28c840]" />
          <span className="mx-auto rounded bg-white px-3 py-0.5 font-mono text-[8.5px] text-stone-400">linkedin.com/in/…</span>
        </div>
        <div className="flex items-center gap-2.5 px-3.5 py-3">
          <span className="h-8 w-8 rounded-full bg-[#dbe6ff]" />
          <div className="flex-1">
            <div className="h-2 w-20 rounded bg-stone-200" />
            <div className="mt-1.5 h-1.5 w-28 rounded bg-stone-100" />
          </div>
          <span className="relative rounded-full bg-signal-600 px-3 py-1.5 text-[10px] font-medium text-white">Connect</span>
        </div>
      </div>
      {/* human cursor */}
      <motion.div className="pointer-events-none absolute" initial={{ left: "44%", top: "44%" }} animate={{ left: ["44%", "78%"], top: ["44%", "62%"] }} transition={{ duration: 1.6, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}>
        <svg width="16" height="16" viewBox="0 0 24 24" className="fill-stone-900 drop-shadow"><path d="M4 2l16 7-7 2-2 7z" /></svg>
      </motion.div>
    </div>
  );
}

function MacOSViz() {
  return (
    <div className="flex h-full items-center px-6">
      <div className="w-full overflow-hidden rounded-xl bg-white shadow-[0_10px_30px_-12px_rgba(20,24,33,0.22)]">
        <div className="flex items-center gap-1.5 bg-[#f1efe9] px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-[#ff5f57]" /><span className="h-2 w-2 rounded-full bg-[#febc2e]" /><span className="h-2 w-2 rounded-full bg-[#28c840]" />
          <span className="mx-auto font-mono text-[8.5px] text-stone-400">App — Xcode</span>
        </div>
        <div className="p-3.5">
          <div className="flex flex-wrap gap-1.5">
            {["Xcode", "Simulator", "Codesign", "AppleScript", "Homebrew"].map((t) => (
              <span key={t} className="rounded-md bg-[#f4f2ec] px-2 py-1 font-mono text-[9px] text-stone-600">{t}</span>
            ))}
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/[0.07]">
            <motion.div initial={{ width: 0 }} whileInView={{ width: "82%" }} viewport={{ once: true }} transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }} className="h-full rounded-full bg-signal-500" />
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[10px] text-stone-500"><Check size={13} /> Build Succeeded · 42.1s</div>
        </div>
      </div>
    </div>
  );
}

function ShipViz() {
  const steps = ["Clone", "Build", "Test", "TestFlight"];
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="w-full max-w-[200px] space-y-1.5">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-2.5 rounded-lg bg-white px-3 py-2 shadow-[0_1px_4px_-1px_rgba(20,24,33,0.08)]">
            {i < 3 ? <Check size={15} /> : <span className="h-[15px] w-[15px] animate-spin rounded-full border-[1.5px] border-signal-500/30 border-t-signal-500" />}
            <span className="text-[11px] font-medium text-stone-700">{s}</span>
            {i === 3 && <span className="ml-auto rounded bg-signal-500/10 px-1.5 py-0.5 text-[8.5px] font-medium text-signal-700">v1.4 (32)</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function PortsViz() {
  return (
    <div className="flex h-full items-center justify-center gap-3 px-6 sm:gap-6">
      <span className="rounded-lg bg-white px-3 py-2 font-mono text-[11px] text-stone-600 shadow-[0_1px_4px_-1px_rgba(20,24,33,0.1)]">localhost:3000</span>
      <svg viewBox="0 0 90 16" className="h-4 w-16 sm:w-24"><line x1="0" y1="8" x2="90" y2="8" className="stroke-signal-500/30" strokeWidth="1.4" strokeDasharray="3 4" /><motion.circle r="2.6" cy="8" className="fill-signal-500" animate={{ cx: [0, 90] }} transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }} /></svg>
      <span className="flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 font-mono text-[11px] shadow-[0_1px_4px_-1px_rgba(20,24,33,0.1)]">
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-signal-600"><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>
        <span className="text-signal-600">app.you.herds.run</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-signal-500/10 px-1.5 py-0.5 text-[8.5px] font-medium text-signal-700"><span className="h-1 w-1 animate-breathe rounded-full bg-signal-500" />live</span>
      </span>
    </div>
  );
}

const CAPS = [
  { viz: <FleetViz />, tint: "#edf6f0", eyebrow: "Fleet", title: "Run a fleet of real Macs", body: "The Studio on your desk, the minis in the closet, the laptop in your bag — one private fleet, online and addressable from anywhere.", span: "lg:col-span-2" },
  { viz: <AgentsViz />, tint: "#eef0fb", eyebrow: "Agents", title: "Control them all with agents", body: "Dispatch one prompt across the whole fleet — agents drive every machine remotely, in parallel.", span: "" },
  { viz: <BrowserViz />, tint: "#eef2f8", eyebrow: "Browser", title: "A real browser, like a human", body: "Not a patchy cloud-browser API — the actual browser on a real Mac. Log in, scroll, click, type, exactly like a person.", span: "" },
  { viz: <MacOSViz />, tint: "#fbf3ec", eyebrow: "Native", title: "The whole of real macOS", body: "Xcode, simulators, codesigning, AppleScript, Homebrew — the real platform, not a stub or an emulator.", span: "" },
  { viz: <ShipViz />, tint: "#fdf1f1", eyebrow: "End to end", title: "Ship iOS, autonomously", body: "Clone → build → test → notarize → TestFlight, in a single run.", span: "" },
  { viz: <PortsViz />, tint: "#ecf5f3", eyebrow: "Networking", title: "Expose any port as a public URL", body: "Run a server in a sandbox and get a named subdomain with real TLS — zero inbound ports opened.", span: "lg:col-span-3" },
];

function CapCard({ c }: { c: (typeof CAPS)[number] }) {
  return (
    <motion.div variants={fadeUp} className={c.span}>
      <div className="h-[200px] overflow-hidden rounded-2xl" style={{ backgroundColor: c.tint }}>{c.viz}</div>
      <div className="px-1 pt-5">
        <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-signal-600">{c.eyebrow}</div>
        <h3 className="ed mt-2 text-[20px] leading-snug text-stone-900">{c.title}</h3>
        <p className="mt-2 max-w-[44ch] text-[13.5px] leading-relaxed text-stone-500">{c.body}</p>
      </div>
    </motion.div>
  );
}

function Capabilities() {
  return (
    <Section>
      <Reveal className="mx-auto max-w-2xl text-center">
        <div className="text-[12px] font-medium uppercase tracking-[0.16em] text-signal-600">Capabilities</div>
        <h2 className="ed mt-3 text-[32px] leading-[1.05] text-stone-900 sm:text-[44px]">Everything a Linux sandbox can&rsquo;t do</h2>
        <p className="mx-auto mt-4 max-w-xl text-[15.5px] leading-relaxed text-stone-500">A fleet of real Macs, driven by agents from anywhere — the things a Linux box in the cloud simply can&rsquo;t be.</p>
      </Reveal>
      <motion.div variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {CAPS.map((c) => <CapCard key={c.title} c={c} />)}
      </motion.div>
    </Section>
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
    <Reveal className="mx-auto mt-14 w-full max-w-[880px]">
      <div className="rounded-[28px] bg-[#eaf3ee] p-4 sm:p-7">
        <div className="overflow-hidden rounded-xl bg-white shadow-[0_24px_70px_-24px_rgba(20,24,33,0.4)] ring-1 ring-black/[0.06]">
          {/* browser chrome */}
          <div className="flex items-center gap-2 bg-[#e9e8e4] px-3.5 py-2.5">
            <span className="h-3 w-3 rounded-full bg-[#ff5f57]" /><span className="h-3 w-3 rounded-full bg-[#febc2e]" /><span className="h-3 w-3 rounded-full bg-[#28c840]" />
            <div className="mx-auto flex items-center gap-1.5 rounded-md bg-white px-3 py-1 text-[11px] text-stone-500">
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-signal-600"><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>
              <span className="font-mono">app.you.herds.run</span>
            </div>
            <span className="hidden items-center gap-1.5 rounded-full bg-signal-500/10 px-2 py-0.5 text-[10px] font-medium text-signal-700 sm:inline-flex"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> live</span>
          </div>

          {/* rendered deployed app */}
          <div className="bg-white">
            {/* app nav */}
            <div className="flex items-center justify-between px-6 py-3.5">
              <span className="flex items-center gap-2 text-[13px] font-semibold text-stone-900"><span className="h-4 w-4 rounded-md bg-signal-600" /> Lumen</span>
              <div className="hidden items-center gap-5 text-[11.5px] text-stone-500 sm:flex">
                <span>Features</span><span>Pricing</span><span>Docs</span>
                <span className="rounded-full bg-stone-900 px-3 py-1 text-[11px] font-medium text-white">Sign up</span>
              </div>
            </div>
            {/* hero */}
            <div className="px-6 pb-7 pt-6 text-center">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f3f2ee] px-2.5 py-1 text-[10px] font-medium text-stone-500"><span className="h-1.5 w-1.5 rounded-full bg-signal-500" /> Live preview</span>
              <h3 className="ed mx-auto mt-3 max-w-[18ch] text-[26px] leading-[1.1] text-stone-900">Analytics that explains itself.</h3>
              <p className="mx-auto mt-2.5 max-w-[34ch] text-[12.5px] leading-relaxed text-stone-500">Dashboards your whole team actually reads — shipped from a sandbox in seconds.</p>
              <div className="mt-4 flex items-center justify-center gap-2.5">
                <span className="rounded-full bg-signal-600 px-4 py-2 text-[12px] font-medium text-white">Get started</span>
                <span className="rounded-full bg-[#f3f2ee] px-4 py-2 text-[12px] font-medium text-stone-700">Book a demo</span>
              </div>
              {/* product strip */}
              <div className="mx-auto mt-7 grid max-w-[440px] grid-cols-3 gap-2.5">
                {[{ k: "MRR", v: "$48.2k", d: "+12%", s: "0,18 16,14 32,15 48,9 64,11 80,5" }, { k: "Active users", v: "9,310", d: "+4%", s: "0,16 16,13 32,14 48,10 64,12 80,8" }, { k: "Churn", v: "1.2%", d: "-0.3", s: "0,8 16,11 32,9 48,12 64,10 80,13" }].map((m) => (
                  <div key={m.k} className="rounded-xl bg-[#f7f6f3] p-2.5 text-left">
                    <div className="text-[9px] font-medium uppercase tracking-[0.08em] text-stone-400">{m.k}</div>
                    <div className="mt-1 tnum text-[15px] font-semibold tracking-tight text-stone-900">{m.v}</div>
                    <div className="mt-1"><Spark points={m.s} /></div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* mapping status bar */}
          <div className="flex items-center gap-2 border-t border-black/[0.05] bg-[#f7f6f3] px-4 py-2 font-mono text-[11px]">
            <span className="text-stone-500">localhost:3000</span>
            <span className="text-stone-300">→</span>
            <span className="text-signal-600">app.you.herds.run</span>
            <span className="ml-auto flex items-center gap-3 text-[10px] text-stone-400">
              <span>TLS</span><span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-signal-500" /> 2 viewers</span>
            </span>
          </div>
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

const CPU_PTS = "0,62 26,52 52,58 78,40 104,49 130,31 156,41 182,24 208,35 234,18 260,30 286,20 320,27";

function MiniStat({ label, value, spark, up = true }: { label: string; value: string; spark: string; up?: boolean }) {
  return (
    <div className="rounded-xl bg-[#f7f6f3] p-2.5">
      <div className="text-[9.5px] font-medium uppercase tracking-[0.08em] text-stone-400">{label}</div>
      <div className="mt-1 tnum text-[14px] font-semibold tracking-tight text-stone-900">{value}</div>
      <div className="mt-1"><Spark points={spark} tone={up ? "text-signal-500" : "text-stone-300"} /></div>
    </div>
  );
}

function ObserveCard() {
  return (
    <Reveal className="mx-auto mt-14 w-full max-w-[900px]">
      <div className="rounded-[28px] bg-[#eef0f4] p-4 sm:p-7">
        <div className="overflow-hidden rounded-xl bg-white shadow-[0_24px_70px_-24px_rgba(20,24,33,0.4)] ring-1 ring-black/[0.06]">
          <Chrome title="you.herds.run/observe" />
          <div className="grid sm:grid-cols-[1.55fr_1fr]">
            {/* metrics */}
            <div className="p-5">
              <div className="flex items-center justify-between">
                <span className="text-[12.5px] font-semibold tracking-tight text-stone-800">m3max · metrics</span>
                <span className="inline-flex items-center gap-1.5 text-[10.5px] text-stone-400"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> live</span>
              </div>
              {/* big area chart */}
              <div className="mt-3 rounded-2xl bg-[#f7f6f3] p-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-stone-400">CPU</span>
                  <span className="tnum text-[24px] font-semibold leading-none tracking-tight text-stone-900">38<span className="text-[14px] text-stone-400">%</span></span>
                </div>
                <svg viewBox="0 0 320 90" preserveAspectRatio="none" className="mt-3 h-24 w-full">
                  <motion.polygon initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ duration: 1 }} points={`${CPU_PTS} 320,90 0,90`} className="fill-signal-500/10" />
                  <motion.polyline initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: 1.2, ease: "easeInOut" }} points={CPU_PTS} fill="none" className="stroke-signal-500" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
                </svg>
                <div className="mt-1 flex justify-between text-[9.5px] text-stone-400"><span>60s ago</span><span>now</span></div>
              </div>
              {/* mini stats */}
              <div className="mt-3 grid grid-cols-3 gap-2.5">
                <MiniStat label="Memory" value="12.4 GB" spark="0,20 16,16 32,17 48,11 64,13 80,9" />
                <MiniStat label="Network" value="8.7 MB/s" spark="0,18 16,12 32,16 48,8 64,12 80,6" />
                <MiniStat label="GPU" value="22%" spark="0,12 16,14 32,10 48,13 64,9 80,11" up={false} />
              </div>
            </div>
            {/* live logs */}
            <div className="bg-[#0f141a] p-5">
              <div className="mb-3 flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-stone-500">live logs</span>
                <span className="inline-flex items-center gap-1.5 text-[10px] text-stone-500"><span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-400" /> tail</span>
              </div>
              <div className="space-y-1.5 font-mono text-[11px] leading-relaxed text-stone-300">
                {LOGS.map((l, i) => <div key={i} className={l.includes("✓") || l.includes("↗") ? "text-signal-400" : "text-stone-400"}>{l}</div>)}
                <div className="inline-block h-[12px] w-[6px] translate-y-[2px] animate-breathe bg-signal-400/80" />
              </div>
            </div>
          </div>
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

/* ------------------------------------------------------------------ *
 * Stories — real use cases (OpenAI-style storytelling grid)
 * ------------------------------------------------------------------ */

function FoodThumb() {
  return (
    <div className="flex h-48 items-center justify-center bg-[#fbf2ea] px-6">
      <div className="w-full max-w-[200px] rounded-2xl bg-white p-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-stone-900">FreshBite</span>
          <span className="rounded-full bg-signal-500/15 px-2 py-0.5 text-[9px] font-medium text-signal-700">12 min</span>
        </div>
        <div className="mt-2.5 flex items-center gap-2.5 rounded-xl bg-[#faf7f2] p-2">
          <span className="h-9 w-9 rounded-lg bg-[#f0c89a]" />
          <div className="flex-1 leading-tight">
            <div className="text-[10.5px] font-medium text-stone-800">Pad Thai</div>
            <div className="text-[9px] text-stone-400">Spicy · 540 cal</div>
          </div>
          <span className="tnum text-[11px] font-semibold text-stone-900">$14</span>
        </div>
        <div className="mt-2.5 rounded-lg bg-signal-600 py-1.5 text-center text-[10px] font-medium text-white">Order now</div>
      </div>
    </div>
  );
}

function BrowserTaskThumb() {
  return (
    <div className="relative flex h-48 items-center justify-center bg-[#eef2f8] px-6">
      <div className="w-full max-w-[228px] overflow-hidden rounded-xl bg-white shadow-[0_10px_30px_-14px_rgba(20,24,33,0.22)]">
        <div className="flex items-center gap-1.5 bg-[#f1efe9] px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-[#ff5f57]" /><span className="h-2 w-2 rounded-full bg-[#febc2e]" /><span className="h-2 w-2 rounded-full bg-[#28c840]" />
          <span className="mx-auto rounded bg-white px-3 py-0.5 font-mono text-[8.5px] text-stone-400">jobs.acme.com/apply</span>
        </div>
        <div className="px-3.5 py-3">
          <div className="text-[10px] font-semibold text-stone-700">Application</div>
          <div className="mt-2 space-y-1.5">
            {[["Name", "Teddy O."], ["Résumé", "resume.pdf"]].map(([k, v]) => (
              <div key={k} className="flex items-center gap-2">
                <span className="w-12 text-[9px] text-stone-400">{k}</span>
                <span className="flex-1 rounded-md bg-[#f4f2ec] px-2 py-1 text-[9.5px] text-stone-700">{v}</span>
              </div>
            ))}
          </div>
          <div className="mt-2.5 rounded-lg bg-signal-600 py-1.5 text-center text-[10px] font-medium text-white">Submit application</div>
        </div>
      </div>
      <motion.div className="pointer-events-none absolute left-[58%] top-[72%]" animate={{ y: [0, -4, 0], opacity: [1, 1, 1] }} transition={{ duration: 1.4, repeat: Infinity }}>
        <svg width="15" height="15" viewBox="0 0 24 24" className="fill-stone-900"><path d="M4 2l16 7-7 2-2 7z" /></svg>
      </motion.div>
    </div>
  );
}

function FleetThumb() {
  const macs = [{ n: "M3 Max", p: 82 }, { n: "Mac mini", p: 64 }, { n: "Mac Studio", p: 91 }, { n: "MacBook", p: 48 }];
  return (
    <div className="flex h-48 flex-col justify-center gap-2.5 bg-[#edf6f0] px-6">
      <div className="mx-auto flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-[11px] text-stone-600 shadow-[0_2px_8px_-3px_rgba(20,24,33,0.14)]">
        <span className="grid h-4 w-4 place-items-center rounded bg-signal-600 text-[8px] font-bold text-white">⌘</span>
        <span>&ldquo;render every scene&rdquo;</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {macs.map((m) => (
          <div key={m.n} className="rounded-lg bg-white px-2.5 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[9.5px] font-semibold text-stone-700">{m.n}</span>
              <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" />
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-black/[0.07]">
              <motion.div initial={{ width: 0 }} whileInView={{ width: `${m.p}%` }} viewport={{ once: true }} transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }} className="h-full rounded-full bg-signal-500" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const STORIES = [
  { cat: "iOS · overnight", title: "A food-delivery app, shipped overnight", body: "An agent cloned the repo, ran Xcode, fixed the failing tests, and pushed to TestFlight by morning — on a Mac mini in the closet.", thumb: <FoodThumb /> },
  { cat: "Browser · human", title: "It applies, books, and files — like a person", body: "The real browser on a real Mac: log into the portal, fill the form, hit submit. No brittle scraping API, no headless workarounds.", thumb: <BrowserTaskThumb /> },
  { cat: "Fleet · agents", title: "A hundred Macs, one prompt", body: "Point an agent at the whole fleet — build, render, test, scrape — running for hours across every machine you own.", thumb: <FleetThumb /> },
];

const MORE_USES = ["Overnight iOS builds", "Browser tasks at scale", "Render farms", "E2E app testing", "Headless CI", "Data extraction", "Long-running agents", "Mac-only toolchains"];

function Stories() {
  return (
    <Section>
      <Reveal>
        <div className="flex items-end justify-between">
          <div>
            <div className="text-[12px] font-medium uppercase tracking-[0.16em] text-signal-600">Use cases</div>
            <h2 className="ed mt-3 text-[32px] leading-[1.05] text-stone-900 sm:text-[40px]">What people build on Herds</h2>
          </div>
          <Link href="/signup" className="hidden text-[13px] text-stone-500 transition-colors hover:text-stone-900 sm:block">Start building →</Link>
        </div>
      </Reveal>

      <motion.div variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="mt-12 grid grid-cols-1 gap-x-8 gap-y-12 md:grid-cols-3">
        {STORIES.map((s) => (
          <motion.div key={s.title} variants={fadeUp}>
            <div className="overflow-hidden rounded-2xl">{s.thumb}</div>
            <div className="mt-4 text-[11px] font-medium uppercase tracking-[0.14em] text-signal-600">{s.cat}</div>
            <h3 className="ed mt-2 text-[20px] leading-snug text-stone-900">{s.title}</h3>
            <p className="mt-2 text-[13.5px] leading-relaxed text-stone-500">{s.body}</p>
          </motion.div>
        ))}
      </motion.div>

      <Reveal delay={0.1}>
        <div className="mt-12 flex flex-wrap gap-2.5">
          {MORE_USES.map((u) => (
            <span key={u} className="rounded-full bg-[#f3f2ee] px-3.5 py-1.5 text-[12.5px] text-stone-600">{u}</span>
          ))}
        </div>
      </Reveal>
    </Section>
  );
}

/* ------------------------------------------------------------------ *
 * Mega footer
 * ------------------------------------------------------------------ */

const FOOTER_COLS: { head: string; links: { label: string; href: string }[] }[] = [
  { head: "Product", links: [
    { label: "Overview", href: "/" }, { label: "Sandboxes", href: "/signup" }, { label: "Volumes", href: "/signup" },
    { label: "Dashboard", href: "/dashboard" }, { label: "Pricing", href: "/signup" },
  ] },
  { head: "Use cases", links: [
    { label: "iOS & macOS builds", href: "/signup" }, { label: "Browser automation", href: "/signup" },
    { label: "iMessage", href: "/signup" }, { label: "CI runners", href: "/signup" }, { label: "Agent infrastructure", href: "/skill" },
  ] },
  { head: "Developers", links: [
    { label: "Docs", href: GITHUB }, { label: "Python SDK", href: GITHUB }, { label: "CLI", href: GITHUB },
    { label: "Agent skill", href: "/skill" }, { label: "Install", href: "/signup" },
  ] },
  { head: "Company", links: [
    { label: "Spawn Labs", href: "https://spawnlabs.ai" }, { label: "GitHub", href: GITHUB },
    { label: "Careers", href: "https://spawnlabs.ai" }, { label: "Contact", href: "mailto:teddy@spawnlabs.ai" },
  ] },
];

function XMark() {
  return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24h-6.66l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231Zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77Z" /></svg>;
}

function Footer() {
  return (
    <footer className="bg-[#f6f5f2]">
      <div className="mx-auto max-w-[1080px] px-6 py-16">
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 md:grid-cols-[1.4fr_repeat(4,1fr)]">
          {/* brand */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2.5">
              <Logo size={24} />
              <span className="text-[15px] font-semibold tracking-tight text-stone-900">Herds</span>
            </Link>
            <p className="mt-4 max-w-[15rem] text-[13px] leading-relaxed text-stone-500">
              Connect any Mac and turn it into a programmable cloud runtime your agents drive from anywhere.
            </p>
            <Link href="/signup" className="mt-5 inline-flex items-center rounded-full bg-signal-600 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-signal-500">Start free</Link>
          </div>
          {/* link columns */}
          {FOOTER_COLS.map((col) => (
            <div key={col.head}>
              <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-stone-400">{col.head}</div>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link href={l.href} className="text-[13px] text-stone-600 transition-colors hover:text-stone-900">{l.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-start justify-between gap-5 border-t border-black/[0.06] pt-7 sm:flex-row sm:items-center">
          <span className="text-[12px] text-stone-400">© 2026 Herds — a Spawn Labs project. All rights reserved.</span>
          <div className="flex items-center gap-4 text-stone-400">
            <Link href={GITHUB} aria-label="GitHub" className="transition-colors hover:text-stone-900"><GitHubMark /></Link>
            <Link href="https://x.com/spawnlabs" aria-label="X" className="transition-colors hover:text-stone-900"><XMark /></Link>
            <span className="ml-1 inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-[12px] text-stone-500">
              <span className="h-1.5 w-1.5 rounded-full bg-signal-500" /> All systems operational
            </span>
          </div>
        </div>
      </div>
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

        <Capabilities />

        <Stories />

        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
