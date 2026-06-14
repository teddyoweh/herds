"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { WorldMap } from "./WorldMap";
import Link from "next/link";
import { motion, type Variants } from "framer-motion";

/* ------------------------------------------------------------------ *
 * Herds — public marketing landing page.
 * Renders its own full-page layout (top bar → footer). Premium dark
 * theme; accent green used sparingly; elevation via fill + shadow,
 * never border lines. Motion is subtle: fade + lift on scroll/mount.
 * ------------------------------------------------------------------ */

const GITHUB = "https://github.com/teddyoweh/herds";

/* A single, reusable entrance: fade up. Used everywhere for cohesion. */
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
  },
};

/* Stagger container — children animate in sequence. */
const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
};

/** Section wrapper that reveals its children once when scrolled into view. */
function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      transition={{ delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Apple glyph mark used in the wordmark and footer. */
function Mark({ size = 22 }: { size?: number }) {
  return (
    <Logo size={size} />
  );
}

/* ------------------------------------------------------------------ *
 * Top bar
 * ------------------------------------------------------------------ */

function TopBar() {
  return (
    <header className="sticky top-0 z-40 bg-ink-950/70 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] max-w-[1100px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <Mark />
          <span className="text-[16px] font-semibold tracking-tightest text-white">Herds</span>
        </Link>
        <div className="flex items-center gap-2.5">
          <Link
            href="/login"
            className="hidden rounded-lg px-3 py-1.5 text-[13px] text-zinc-400 transition-colors hover:text-zinc-100 sm:inline-flex"
          >
            Log in
          </Link>
          <Link
            href="/signup"
            className="inline-flex items-center rounded-full bg-zinc-100 px-4 py-1.5 text-[13px] font-medium text-ink-950 shadow-e1 transition-colors hover:bg-white"
          >
            Start free
          </Link>
        </div>
      </div>
      <div className="h-px w-full bg-white/[0.05]" />
    </header>
  );
}

/* ------------------------------------------------------------------ *
 * Terminal mockup
 * ------------------------------------------------------------------ */

function TerminalLine({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`leading-[1.85] ${className}`}>{children}</div>;
}

function Prompt() {
  return <span className="text-signal-400">$</span>;
}

const TERM_LINES: { cmd?: boolean; node: React.ReactNode }[] = [
  { cmd: true, node: <><Prompt /> <span className="text-zinc-100">herds auth</span></> },
  { node: <><span className="text-signal-400">✓</span> Authenticated as <span className="text-zinc-300">teddy@spawnlabs.ai</span></> },
  { cmd: true, node: <><Prompt /> <span className="text-zinc-100">herds host</span></> },
  { node: <><span className="text-zinc-600">→</span> Registering this Mac · M3 Max · macOS 15.4</> },
  { node: <><span className="text-signal-400">✓</span> Live at <span className="text-signal-400 underline decoration-signal-500/40 underline-offset-2">https://you.herds.run</span></> },
  { cmd: true, node: <><Prompt /> <span className="text-zinc-100">herds.mac().run(&quot;xcodebuild&quot;)</span></> },
  { node: <><span className="text-signal-400">✓</span> Build succeeded · <span className="text-zinc-300">42.1s</span></> },
];

function Terminal() {
  return (
    <div className="relative">
      {/* ambient glow + reflection under the window */}
      <div aria-hidden className="absolute -inset-6 rounded-[32px] bg-signal-500/[0.07] blur-[44px]" />
      <div
        aria-hidden
        className="absolute -inset-x-6 -bottom-10 h-24 rounded-full bg-signal-500/[0.06] blur-3xl"
      />
      <div className="relative overflow-hidden rounded-2xl bg-ink-900/80 backdrop-blur-xl shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_2px_8px_rgba(0,0,0,0.5),0_40px_90px_-32px_rgba(0,0,0,0.95)]">
        {/* top sheen */}
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        {/* window chrome */}
        <div className="flex items-center gap-2 bg-white/[0.025] px-4 py-3">
          <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
          <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
          <span className="h-3 w-3 rounded-full bg-[#28c840]" />
          <span className="mx-auto pr-12 text-[11px] tracking-tight text-zinc-600">herds — zsh</span>
        </div>
        <motion.div
          className="space-y-1 px-5 py-6 font-mono text-[12.5px] leading-[1.85] tnum sm:text-[13px]"
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.33, delayChildren: 0.45 } } }}
        >
          {TERM_LINES.map((l, i) => (
            <motion.div
              key={i}
              variants={{ hidden: { opacity: 0, y: 3 }, show: { opacity: 1, y: 0 } }}
              transition={{ duration: 0.22 }}
              className={l.cmd ? "pt-2 text-zinc-300 first:pt-0" : "text-zinc-500"}
            >
              {l.node}
              {i === TERM_LINES.length - 1 && (
                <span className="ml-1 inline-block h-[15px] w-[7px] translate-y-[2px] animate-breathe bg-signal-400/80 align-middle" />
              )}
            </motion.div>
          ))}
        </motion.div>
      </div>
    </div>
  );
}

function HeroBackground() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* masked dot grid */}
      <div className="absolute inset-0 [background-image:radial-gradient(circle,rgba(255,255,255,0.05)_1px,transparent_1px)] [background-size:30px_30px] [mask-image:radial-gradient(ellipse_72%_56%_at_50%_-2%,black,transparent)]" />
      {/* primary signal aurora */}
      <div className="absolute -top-52 left-1/2 h-[600px] w-[980px] -translate-x-1/2 rounded-full bg-signal-500/[0.10] blur-[140px]" />
      {/* secondary cool wash */}
      <div className="absolute top-4 right-[6%] h-[380px] w-[380px] rounded-full bg-[#7c93f5]/[0.06] blur-[120px]" />
      {/* fade into the page */}
      <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-b from-transparent to-ink-950" />
    </div>
  );
}

function CurlPill() {
  const [copied, setCopied] = useState(false);
  const cmd = "curl -fsSL herds.run/install | sh";
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(cmd); setCopied(true); setTimeout(() => setCopied(false), 1400); }}
      className="surface surface-hover group inline-flex items-center gap-2.5 px-3 py-2 font-mono text-[12.5px] text-zinc-400"
    >
      <span className="text-signal-400">$</span>
      <span>{cmd}</span>
      <span className={`text-[11px] ${copied ? "text-signal-400" : "text-zinc-600 group-hover:text-zinc-400"}`}>
        {copied ? "copied" : "copy"}
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ *
 * Hero
 * ------------------------------------------------------------------ */

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="tnum mt-2 font-mono text-[30px] font-semibold leading-none tracking-tightest text-white sm:text-[38px]">
        {value}
      </div>
    </div>
  );
}

/** Marker-highlight behind text — the town.com move, in signal green. */
function Highlight({ children }: { children: React.ReactNode }) {
  return (
    <span className="relative inline-block whitespace-nowrap text-white">
      <span
        aria-hidden
        className="absolute inset-x-[-0.1em] bottom-[0.1em] top-[0.2em] -z-10 -rotate-[0.9deg] rounded-[5px] bg-gradient-to-r from-signal-500/40 to-signal-400/25 shadow-[0_0_48px_10px_rgba(52,211,158,0.16)]"
      />
      {children}
    </span>
  );
}

/** A floating glass chip with a soft entrance — scattered around the collage. */
function FloatChip({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className={`absolute z-20 hidden items-center rounded-2xl bg-ink-900/75 px-3.5 py-2.5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08),0_28px_70px_-28px_rgba(0,0,0,0.95)] ring-1 ring-white/[0.06] backdrop-blur-xl lg:flex ${className}`}
    >
      {children}
    </motion.div>
  );
}

/** Interactive command line — town's "Ask Bud anything", for Macs. */
function CommandBar() {
  const EX = ["xcodebuild -scheme App build", "swift test --parallel", "npm run build && ./deploy.sh", "open -a Simulator"];
  const [i, setI] = useState(0);
  useEffect(() => { const t = setInterval(() => setI((v) => (v + 1) % EX.length), 2800); return () => clearInterval(t); }, []);
  return (
    <div className="surface flex items-center gap-3 px-4 py-3">
      <span className="font-mono text-[13px] text-signal-400">$</span>
      <div className="min-w-0 flex-1 overflow-hidden whitespace-nowrap font-mono text-[13px] text-zinc-500">
        herds.mac().run(<span className="text-zinc-300">&quot;</span>
        <motion.span key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.45 }} className="text-zinc-200">{EX[i]}</motion.span>
        <span className="text-zinc-300">&quot;</span>)
      </div>
      <Link href="/signup" className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-signal-500 text-ink-950 transition hover:bg-signal-400" aria-label="run">
        <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </Link>
    </div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <HeroBackground />
      {/* faint global herd behind everything */}
      <div className="pointer-events-none absolute inset-0 hidden opacity-[0.5] [mask-image:radial-gradient(ellipse_60%_70%_at_72%_42%,black,transparent)] lg:block">
        <WorldMap className="absolute right-0 top-1/2 w-[80%] -translate-y-1/2" />
      </div>

      <div className="relative mx-auto max-w-[1140px] px-6 pb-24 pt-20 lg:pb-28">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <span className="inline-flex items-center gap-2 rounded-full bg-white/[0.05] px-3 py-1 text-[12px] text-zinc-300 shadow-e1">
            <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-400 shadow-[0_0_8px_1px_rgba(52,211,158,0.45)]" />
            Modal, for Macs
          </span>
        </motion.div>

        {/* editorial headline + floating product collage */}
        <div className="relative mt-7">
          <motion.h1
            variants={stagger} initial="hidden" animate="show"
            className="relative z-10 text-[15.5vw] font-semibold leading-[0.92] tracking-tightest text-white sm:text-[88px] lg:text-[104px]"
          >
            <motion.span variants={fadeUp} className="block">Give your</motion.span>
            <motion.span variants={fadeUp} className="block">agents <Highlight>real Macs.</Highlight></motion.span>
          </motion.h1>

          {/* floating terminal, lower-right, rotated — the collage */}
          <motion.div
            initial={{ opacity: 0, y: 28, rotate: 3.4 }}
            animate={{ opacity: 1, y: 0, rotate: 2 }}
            transition={{ delay: 0.3, duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
            className="absolute right-[-16px] top-[112%] hidden w-[400px] xl:block"
          >
            <Terminal />
          </motion.div>

          {/* floating live chips, clear of the headline */}
          <FloatChip className="right-[1%] top-[18%] gap-2" delay={0.55}>
            <span className="h-2 w-2 rounded-full bg-signal-400 shadow-[0_0_8px_1px_rgba(52,211,158,0.6)]" />
            <span className="font-mono text-[12px] text-zinc-300">you.herds.run</span>
            <span className="text-[11px] font-medium text-signal-400">live</span>
          </FloatChip>
          <FloatChip className="right-[6%] top-[104%] gap-2.5" delay={0.8}>
            <Logo size={20} />
            <div className="leading-none">
              <div className="text-[9px] uppercase tracking-[0.14em] text-zinc-600">M3 Max · online</div>
              <div className="tnum mt-1 text-[13px] font-semibold text-white">3 sandboxes</div>
            </div>
          </FloatChip>
        </div>

        <motion.p
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
          className="relative z-10 mt-8 max-w-[34rem] text-[16px] leading-relaxed text-zinc-400 sm:text-[17.5px]"
        >
          Connect any Mac you own and it becomes a programmable cloud runtime — Xcode builds,
          native app testing, real macOS automation — that agents, SDKs, CLIs, and apps drive
          from anywhere. <span className="text-zinc-200">One command to go live.</span>
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.36 }}
          className="relative z-10 mt-9 max-w-[34rem]"
        >
          <CommandBar />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link href="/signup" className="inline-flex items-center rounded-full bg-zinc-100 px-5 py-2.5 text-[14px] font-medium text-ink-950 shadow-[0_1px_2px_rgba(0,0,0,0.4),0_8px_24px_-8px_rgba(255,255,255,0.25)] transition-all hover:-translate-y-px hover:bg-white">Start free</Link>
            <CurlPill />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}
          className="relative z-10 mt-16 grid max-w-md grid-cols-3 gap-8"
        >
          <HeroStat label="Setup time" value="60s" />
          <HeroStat label="Inbound ports" value="0" />
          <HeroStat label="Your hardware" value="100%" />
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Shared section heading
 * ------------------------------------------------------------------ */

function SectionHead({
  eyebrow,
  title,
  sub,
}: {
  eyebrow: string;
  title: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <div className="label !text-signal-500">{eyebrow}</div>
      <h2 className="mt-3 text-[30px] font-semibold tracking-tightest text-white sm:text-[36px]">
        {title}
      </h2>
      {sub && <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-zinc-500">{sub}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * How it works
 * ------------------------------------------------------------------ */

const STEPS = [
  {
    n: "01",
    cmd: "herds auth",
    title: "Sign in",
    body: "Install the CLI and authenticate. No servers to provision, no images to build.",
  },
  {
    n: "02",
    cmd: "herds host",
    title: "Your Mac goes live",
    body: "One command turns the Mac on your desk into a cloud runtime at you.herds.run.",
  },
  {
    n: "03",
    cmd: "herds.mac().run(…)",
    title: "Agents run on it",
    body: "Drive it from any SDK, CLI, or agent — anywhere. Real macOS, on demand.",
  },
];

function HowItWorks() {
  return (
    <section className="mx-auto max-w-[1100px] px-6 py-24">
      <Reveal>
        <SectionHead
          eyebrow="How it works"
          title="From your desk to the cloud in three commands"
          sub="No Dockerfiles. No CI runners to babysit. Just your Mac, exposed as an API."
        />
      </Reveal>

      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        className="mt-14 grid grid-cols-1 gap-4 md:grid-cols-3"
      >
        {STEPS.map((s) => (
          <motion.div
            key={s.n}
            variants={fadeUp}
            className="surface surface-hover flex flex-col p-6"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[12px] tracking-tight text-zinc-600 tnum">{s.n}</span>
              <span className="label">step</span>
            </div>
            <div className="mt-5 inline-flex w-fit items-center rounded-lg bg-ink-950/60 px-3 py-1.5 font-mono text-[12.5px] text-signal-400 shadow-e1">
              <span className="mr-1.5 text-zinc-600">$</span>
              {s.cmd}
            </div>
            <h3 className="mt-5 text-[16px] font-semibold tracking-tight text-white">{s.title}</h3>
            <p className="mt-2 text-[13.5px] leading-relaxed text-zinc-500">{s.body}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Feature grid (bento)
 * ------------------------------------------------------------------ */

function PortIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-signal-400">
      <path
        d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.07 0l-3 3A5 5 0 0 0 11 21l1.71-1.71"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function MacIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-signal-400">
      <rect x="3" y="4" width="18" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M2 20h20M9 16l-.5 4M15 16l.5 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function VolumeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-signal-400">
      <ellipse cx="12" cy="5" rx="8" ry="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
function DashIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-signal-400">
      <rect x="3" y="3" width="7" height="9" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
      <rect x="14" y="3" width="7" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
      <rect x="14" y="12" width="7" height="9" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
      <rect x="3" y="16" width="7" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function FeatureCard({
  icon,
  title,
  body,
  className = "",
  children,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <motion.div
      variants={fadeUp}
      className={`surface surface-hover flex flex-col p-6 ${className}`}
    >
      <span className="grid h-9 w-9 place-items-center rounded-lg bg-signal-500/10 shadow-e1">
        {icon}
      </span>
      <h3 className="mt-5 text-[16px] font-semibold tracking-tight text-white">{title}</h3>
      <p className="mt-2 text-[13.5px] leading-relaxed text-zinc-500">{body}</p>
      {children}
    </motion.div>
  );
}

function Features() {
  return (
    <section className="mx-auto max-w-[1100px] px-6 py-24">
      <Reveal>
        <SectionHead
          eyebrow="Capabilities"
          title="Things no Linux sandbox can do"
          sub="It's not an emulator or a VM you rent — it's the real machine, exposed as programmable infrastructure."
        />
      </Reveal>

      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        className="mt-14 grid grid-cols-1 gap-4 md:grid-cols-3"
      >
        {/* Wide hero feature */}
        <FeatureCard
          icon={<MacIcon />}
          title="Real macOS"
          body="Xcode builds, iOS/macOS simulators, native app testing, codesigning, AppleScript & Mac automation. The whole platform, not a stub."
          className="md:col-span-2"
        >
          <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {["Xcode", "Simulators", "Codesign", "AppleScript"].map((t) => (
              <span
                key={t}
                className="rounded-lg bg-ink-950/60 px-3 py-2 text-center font-mono text-[11.5px] text-zinc-400 shadow-e1"
              >
                {t}
              </span>
            ))}
          </div>
        </FeatureCard>

        <FeatureCard
          icon={<PortIcon />}
          title="Expose ports → URLs"
          body="Run a server inside a sandbox and get a public link instantly. Share a preview, hit an endpoint, ship a demo."
        >
          <div className="mt-5 rounded-lg bg-ink-950/60 px-3 py-2 font-mono text-[11.5px] shadow-e1">
            <span className="text-zinc-600">:3000</span>
            <span className="mx-2 text-zinc-700">→</span>
            <span className="text-signal-400">app.you.herds.run</span>
          </div>
        </FeatureCard>

        <FeatureCard
          icon={<VolumeIcon />}
          title="Persistent sandboxes & volumes"
          body="Snapshot, suspend, resume. Mount durable volumes so caches, builds, and state survive across runs."
        />

        <FeatureCard
          icon={<DashIcon />}
          title="Live dashboard"
          body="Watch every machine, sandbox, and run in real time. Logs, metrics, and status — streamed, never stale."
          className="md:col-span-2"
        >
          <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
            {[
              { k: "machines online", v: "3" },
              { k: "active sandboxes", v: "12" },
              { k: "runs today", v: "1,284" },
            ].map((s) => (
              <div key={s.k} className="flex items-baseline gap-2">
                <span className="font-mono text-[22px] font-semibold tracking-tight text-white tnum">
                  {s.v}
                </span>
                <span className="text-[12px] text-zinc-600">{s.k}</span>
              </div>
            ))}
          </div>
        </FeatureCard>
      </motion.div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Built for agents
 * ------------------------------------------------------------------ */

function BuiltForAgents() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 right-1/4 h-[360px] w-[600px] rounded-full bg-signal-500/[0.06] blur-[120px]"
      />
      <div className="relative mx-auto grid max-w-[1100px] grid-cols-1 items-center gap-12 px-6 py-24 lg:grid-cols-[1fr_1fr]">
        <Reveal>
          <div className="label !text-signal-500">Built for agents</div>
          <h2 className="mt-3 text-[30px] font-semibold tracking-tightest text-white sm:text-[38px]">
            Give Claude hands on a&nbsp;real&nbsp;Mac.
          </h2>
          <p className="mt-5 max-w-lg text-[15.5px] leading-relaxed text-zinc-400">
            Your agents already write the code. Now they can build it, run it, click through the
            app, and verify it — on the same macOS your users run. A single API call hands an agent a
            full machine: file system, GUI, network, the works.
          </p>
          <ul className="mt-7 space-y-3">
            {[
              "Build & ship iOS apps end-to-end, autonomously",
              "Drive native UI, screenshot, and assert on real pixels",
              "Isolated sandboxes per task — spin up, tear down, repeat",
            ].map((t) => (
              <li key={t} className="flex items-start gap-3 text-[14px] text-zinc-300">
                <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-signal-400 shadow-[0_0_8px_1px_rgba(52,211,158,0.4)]" />
                {t}
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/skill"
              className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] px-4 py-2 text-[13.5px] font-medium text-zinc-200 transition-colors hover:bg-white/[0.1]"
            >
              Get the skill
              <span aria-hidden className="text-zinc-500">→</span>
            </Link>
            <a
              href="/skill.md"
              className="font-mono text-[12.5px] text-zinc-600 transition-colors hover:text-zinc-400"
            >
              herds.run/skill.md
            </a>
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="surface overflow-hidden font-mono text-[12.5px] sm:text-[13px]">
            <div className="flex items-center gap-2 bg-white/[0.03] px-4 py-3">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              <span className="ml-2 text-[11px] tracking-tight text-zinc-600">agent.py</span>
            </div>
            <pre className="overflow-x-auto px-5 py-5 leading-[1.85] text-zinc-400">
              <code>
                <span className="text-zinc-600">{"# hand an agent a real Mac\n"}</span>
                <span className="text-signal-400">{"mac"}</span>
                {" = herds."}
                <span className="text-zinc-200">{"mac"}</span>
                {"()\n\n"}
                <span className="text-signal-400">{"build"}</span>
                {" = mac."}
                <span className="text-zinc-200">{"run"}</span>
                {'("xcodebuild -scheme App")\n'}
                <span className="text-zinc-200">{"url"}</span>
                {"  = mac."}
                <span className="text-zinc-200">{"expose"}</span>
                {"(3000)  "}
                <span className="text-zinc-600">{"# → public link"}</span>
                {"\n\n"}
                <span className="text-zinc-200">{"agent"}</span>
                {".verify("}
                <span className="text-zinc-200">{"url"}</span>
                {", screenshot="}
                <span className="text-signal-400">{"True"}</span>
                {")"}
              </code>
            </pre>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Final CTA
 * ------------------------------------------------------------------ */

function FinalCTA() {
  return (
    <section className="mx-auto max-w-[1100px] px-6 py-24">
      <Reveal>
        <div className="surface relative overflow-hidden px-8 py-16 text-center sm:px-16 sm:py-20">
          <div
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-0 h-[300px] w-[600px] -translate-x-1/2 rounded-full bg-signal-500/[0.1] blur-[110px]"
          />
          <div className="relative">
            <h2 className="text-[32px] font-semibold tracking-tightest text-white sm:text-[42px]">
              Connect your Mac in 60 seconds.
            </h2>
            <p className="mx-auto mt-4 max-w-md text-[15px] leading-relaxed text-zinc-400">
              Every Mac becomes an API. Your own machine, your own infra — live with one command.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/signup"
                className="inline-flex items-center rounded-full bg-signal-500 px-6 py-3 text-[14px] font-medium text-ink-950 shadow-e1 transition-colors hover:bg-signal-400"
              >
                Start free
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center rounded-full bg-white/[0.06] px-6 py-3 text-[14px] font-medium text-zinc-200 transition-colors hover:bg-white/[0.1]"
              >
                Log in
              </Link>
            </div>
            <div className="mt-6 font-mono text-[12.5px] text-zinc-600">
              <span className="text-signal-400">$</span> herds host
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Footer
 * ------------------------------------------------------------------ */

function Footer() {
  return (
    <footer className="mx-auto max-w-[1100px] px-6 pb-14 pt-6">
      <div className="h-px w-full bg-white/[0.05]" />
      <div className="flex flex-col items-start justify-between gap-6 pt-8 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2.5">
          <Mark size={20} />
          <span className="text-[14px] font-semibold tracking-tightest text-white">Herds</span>
          <span className="ml-2 text-[12.5px] text-zinc-600">Your Mac is the cloud.</span>
        </div>
        <nav className="flex items-center gap-6 text-[13px] text-zinc-500">
          <Link href={GITHUB} className="transition-colors hover:text-zinc-200">
            Docs
          </Link>
          <Link href={GITHUB} className="transition-colors hover:text-zinc-200">
            GitHub
          </Link>
          <Link href="https://spawnlabs.ai" className="transition-colors hover:text-zinc-200">
            Spawn Labs
          </Link>
        </nav>
      </div>
      <div className="mt-8 text-[12px] text-zinc-700">
        © {new Date().getFullYear()} Herds — a Spawn Labs project. All rights reserved.
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ *
 * Page
 * ------------------------------------------------------------------ */

export function Landing() {
  return (
    <div className="min-h-screen bg-ink-950">
      <TopBar />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <BuiltForAgents />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
