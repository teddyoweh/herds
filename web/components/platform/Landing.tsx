"use client";

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
    <span
      className="grid place-items-center rounded-md bg-gradient-to-br from-signal-400 to-signal-600 text-ink-950 shadow-e1"
      style={{ width: size, height: size, fontSize: size * 0.5 }}
    >
      🍎
    </span>
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

function Terminal() {
  return (
    <div className="surface overflow-hidden font-mono text-[12.5px] sm:text-[13px]">
      {/* window chrome */}
      <div className="flex items-center gap-2 bg-white/[0.03] px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
        <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
        <span className="h-3 w-3 rounded-full bg-[#28c840]" />
        <span className="ml-2 text-[11px] tracking-tight text-zinc-600">herds — bash — 80×24</span>
      </div>
      <div className="space-y-1 px-5 py-5 tnum">
        <TerminalLine className="text-zinc-300">
          <Prompt /> <span className="text-zinc-100">herds auth</span>
        </TerminalLine>
        <TerminalLine className="text-zinc-500">
          <span className="text-signal-400">✓</span> Authenticated as{" "}
          <span className="text-zinc-300">teddy@spawnlabs.ai</span>
        </TerminalLine>
        <TerminalLine className="pt-2 text-zinc-300">
          <Prompt /> <span className="text-zinc-100">herds host</span>
        </TerminalLine>
        <TerminalLine className="text-zinc-500">
          <span className="text-zinc-600">→</span> Registering this Mac · M3 Max · macOS 15.4
        </TerminalLine>
        <TerminalLine className="text-zinc-500">
          <span className="text-signal-400">✓</span> Live at{" "}
          <span className="text-signal-400 underline decoration-signal-500/40 underline-offset-2">
            https://you.herds.run
          </span>
        </TerminalLine>
        <TerminalLine className="pt-2 text-zinc-300">
          <Prompt /> <span className="text-zinc-100">herds.mac().run(&quot;xcodebuild&quot;)</span>
        </TerminalLine>
        <TerminalLine className="text-zinc-500">
          <span className="text-signal-400">✓</span> Build succeeded ·{" "}
          <span className="text-zinc-300">42.1s</span>
          <span className="ml-1 inline-block h-[15px] w-[7px] translate-y-[2px] animate-breathe bg-signal-400/80 align-middle" />
        </TerminalLine>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Hero
 * ------------------------------------------------------------------ */

function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* faint accent bloom, top-left — color used very sparingly */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[440px] w-[760px] -translate-x-1/2 rounded-full bg-signal-500/[0.07] blur-[120px]"
      />
      <div className="relative mx-auto grid max-w-[1100px] grid-cols-1 items-center gap-14 px-6 pb-20 pt-20 lg:grid-cols-[1.05fr_1fr] lg:pb-28 lg:pt-28">
        <motion.div variants={stagger} initial="hidden" animate="show">
          <motion.div variants={fadeUp}>
            <span className="inline-flex items-center gap-2 rounded-full bg-white/[0.05] px-3 py-1 text-[12px] text-zinc-400 shadow-e1">
              <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-400 shadow-[0_0_8px_1px_rgba(52,211,158,0.45)]" />
              Modal, for Macs
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="mt-6 text-[44px] font-semibold leading-[1.04] tracking-tightest text-white sm:text-[58px]"
          >
            Give your agents
            <br />
            <span className="text-signal-400">real Macs.</span>
          </motion.h1>

          <motion.p
            variants={fadeUp}
            className="mt-6 max-w-[34rem] text-[16px] leading-relaxed text-zinc-400 sm:text-[17px]"
          >
            Connect any Mac you own and it becomes a programmable cloud runtime — Xcode builds,
            native app testing, real macOS automation — that agents, SDKs, CLIs, and apps drive
            from anywhere. One command to go live. Your Mac, your infra.
          </motion.p>

          <motion.div variants={fadeUp} className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/signup"
              className="inline-flex items-center rounded-full bg-zinc-100 px-5 py-2.5 text-[14px] font-medium text-ink-950 shadow-e1 transition-colors hover:bg-white"
            >
              Start free
            </Link>
            <Link
              href={GITHUB}
              className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] px-5 py-2.5 text-[14px] font-medium text-zinc-200 transition-colors hover:bg-white/[0.1]"
            >
              Read the docs
              <span aria-hidden className="text-zinc-500">
                →
              </span>
            </Link>
          </motion.div>

          <motion.div
            variants={fadeUp}
            className="mt-8 flex items-center gap-2 text-[12.5px] text-zinc-600"
          >
            <span className="font-mono text-zinc-500">curl -fsSL herds.run/install | sh</span>
          </motion.div>
        </motion.div>

        <motion.div
          variants={fadeUp}
          initial="hidden"
          animate="show"
          transition={{ delay: 0.18 }}
        >
          <Terminal />
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
