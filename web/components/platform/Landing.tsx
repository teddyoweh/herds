"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { getSession } from "@/lib/platform";
import Link from "next/link";
import { motion, type Variants } from "framer-motion";

/* ------------------------------------------------------------------ *
 * Herds — public marketing landing page.
 * Warm editorial light theme: off-white paper, high-contrast serif
 * display (Fraunces), generous whitespace, restrained signal-green
 * accent. Elevation via soft shadow + hairline, never heavy borders.
 * ------------------------------------------------------------------ */

const GITHUB = "https://github.com/teddyoweh/herds";

/* Borderless elevation on a light surface: white fill lifts off the warm paper,
   a soft layered shadow gives depth. No edge lines — ever (brand rule). */
const CARD =
  "shadow-[0_2px_4px_rgba(20,20,16,0.04),0_16px_44px_-14px_rgba(20,20,16,0.16)]";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
};
const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
};

function Reveal({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
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

/* ------------------------------------------------------------------ *
 * Top bar
 * ------------------------------------------------------------------ */

function TopBar() {
  const [account, setAccount] = useState<string | null>(null);
  useEffect(() => {
    const s = getSession();
    if (s) setAccount(s.account);
  }, []);
  return (
    <header className="sticky top-0 z-40 bg-[#faf9f6]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] max-w-[1120px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <Logo size={22} />
          <span className="text-[16px] font-semibold tracking-tight text-stone-900">Herds</span>
        </Link>
        <div className="flex items-center gap-2">
          {account ? (
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 rounded-full bg-signal-600 px-4 py-1.5 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-signal-500"
            >
              Dashboard <span aria-hidden className="text-white/60">→</span>
            </Link>
          ) : (
            <>
              <Link href="/login" className="hidden rounded-lg px-3 py-1.5 text-[13px] text-stone-500 transition-colors hover:text-stone-900 sm:inline-flex">
                Log in
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center rounded-full bg-signal-600 px-4 py-1.5 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-signal-500"
              >
                Start free
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ *
 * Small shared pieces
 * ------------------------------------------------------------------ */

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-[12px] font-medium text-stone-600 shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
      <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500 shadow-[0_0_8px_1px_rgba(27,189,134,0.45)]" />
      {children}
    </span>
  );
}

/** Interactive command line — town's "ask anything", for Macs. */
function CommandBar() {
  const EX = ["xcodebuild -scheme App build", "swift test --parallel", "npm run build && ./deploy.sh", "open -a Simulator"];
  const [i, setI] = useState(0);
  useEffect(() => { const t = setInterval(() => setI((v) => (v + 1) % EX.length), 2800); return () => clearInterval(t); }, []);
  return (
    <div className={`flex items-center gap-3 rounded-2xl bg-white px-4 py-3 ${CARD}`}>
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
    <button
      onClick={() => { navigator.clipboard?.writeText(cmd); setCopied(true); setTimeout(() => setCopied(false), 1400); }}
      className="group inline-flex items-center gap-2.5 rounded-full bg-white px-4 py-2.5 font-mono text-[12.5px] text-stone-500 shadow-[0_1px_2px_rgba(0,0,0,0.05)] transition hover:shadow-[0_3px_12px_rgba(20,20,16,0.12)]"
    >
      <span className="text-signal-600">$</span>
      <span>{cmd}</span>
      <span className={`text-[11px] ${copied ? "text-signal-600" : "text-stone-400 group-hover:text-stone-600"}`}>{copied ? "copied" : "copy"}</span>
    </button>
  );
}

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-serif text-[34px] leading-none text-stone-900 sm:text-[40px]">{value}</div>
      <div className="mt-2 text-[11px] uppercase tracking-[0.14em] text-stone-400">{label}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Hero product artifact — a light browser-chromed live dashboard.
 * ------------------------------------------------------------------ */

function ArtifactMachine({ name, kind, load, delay }: { name: string; kind: string; load: number; delay: number }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-[#f4f2ec] px-3.5 py-3">
      <span className="grid h-8 w-8 flex-none place-items-center rounded-lg">
        <Logo size={26} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-[12.5px] font-semibold tracking-tight text-stone-900">{name}</span>
          <span className="tnum font-mono text-[11px] text-stone-400">{load}%</span>
        </div>
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-black/[0.07]">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${load}%` }}
            transition={{ delay, duration: 1, ease: [0.22, 1, 0.36, 1] }}
            className="h-full rounded-full bg-gradient-to-r from-signal-500 to-signal-400"
          />
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

function HeroArtifact() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 28, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.4, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
      className={`relative mx-auto w-full max-w-[940px] overflow-hidden rounded-3xl bg-white ${CARD}`}
    >
      {/* browser chrome */}
      <div className="flex items-center gap-2 bg-[#f1efe9] px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
        <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
        <span className="h-3 w-3 rounded-full bg-[#28c840]" />
        <div className="mx-auto flex items-center gap-1.5 rounded-md bg-white px-3 py-1 text-[11px] text-stone-400">
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" className="text-stone-400"><rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" strokeWidth="2" /></svg>
          <span className="font-mono">you.herds.run</span>
        </div>
      </div>
      {/* dashboard body */}
      <div className="grid sm:grid-cols-[1.05fr_1fr]">
        <div className="bg-white p-5 text-left">
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-semibold tracking-tight text-stone-700">Your fleet</span>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-stone-500">
              <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> 3 online
            </span>
          </div>
          <div className="mt-4 space-y-2.5">
            <ArtifactMachine name="M3 Max" kind="Mac Studio · 3 sandboxes" load={38} delay={0.7} />
            <ArtifactMachine name="M2 Pro" kind="Mac mini · 5 sandboxes" load={71} delay={0.85} />
            <ArtifactMachine name="M3" kind="MacBook Air · 1 sandbox" load={12} delay={1.0} />
          </div>
        </div>
        <div className="flex flex-col bg-white p-5 text-left">
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-semibold tracking-tight text-stone-700">Live run</span>
            <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-stone-400">
              <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> m3max
            </span>
          </div>
          <motion.div
            className="mt-4 space-y-1.5 font-mono text-[11.5px] leading-[1.7] tnum"
            initial="hidden" animate="show"
            variants={{ show: { transition: { staggerChildren: 0.45, delayChildren: 0.7 } } }}
          >
            {RUN_LINES.map((l, i) => (
              <motion.div
                key={i}
                variants={{ hidden: { opacity: 0, y: 3 }, show: { opacity: 1, y: 0 } }}
                transition={{ duration: 0.25 }}
                className={l.cmd ? "text-stone-800" : "text-stone-500"}
              >
                {l.node}
                {i === RUN_LINES.length - 1 && (
                  <span className="ml-1 inline-block h-[12px] w-[6px] translate-y-[2px] animate-breathe bg-signal-500/80 align-middle" />
                )}
              </motion.div>
            ))}
          </motion.div>
          <div className="mt-auto pt-5">
            <div className="text-[10px] uppercase tracking-[0.14em] text-stone-400">Exposed</div>
            <div className="mt-2.5 space-y-1.5">
              {[{ port: ":3000", url: "app.you.herds.run" }, { port: ":8000", url: "api.you.herds.run" }].map((e) => (
                <div key={e.port} className="flex items-center gap-2 rounded-lg bg-[#f4f2ec] px-2.5 py-1.5 font-mono text-[11px]">
                  <span className="text-stone-500">{e.port}</span>
                  <span className="text-stone-300">→</span>
                  <span className="truncate text-signal-600">{e.url}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ *
 * Hero
 * ------------------------------------------------------------------ */

function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* faint warm halo behind the headline */}
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-[-120px] h-[420px] w-[820px] -translate-x-1/2 rounded-full bg-signal-500/[0.06] blur-[130px]" />

      <div className="relative mx-auto max-w-[1080px] px-6 pb-16 pt-14 text-center">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-center">
          <Eyebrow>Modal, for Macs</Eyebrow>
        </motion.div>

        <motion.h1
          variants={stagger} initial="hidden" animate="show"
          className="mx-auto mt-6 max-w-[16ch] font-serif text-[12.5vw] font-medium leading-[0.98] tracking-[-0.01em] text-stone-900 sm:text-[64px] lg:text-[80px]"
        >
          <motion.span variants={fadeUp} className="block">Give your agents</motion.span>
          <motion.span variants={fadeUp} className="block italic">real Macs.</motion.span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }}
          className="mx-auto mt-6 max-w-[36rem] text-[15.5px] leading-relaxed text-stone-500 sm:text-[16.5px]"
        >
          Connect any Mac you own and it becomes a programmable cloud runtime — Xcode builds,
          native app testing, real macOS automation — driven by agents, SDKs, and CLIs from
          anywhere. <span className="text-stone-800">One command to go live.</span>
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.34 }}
          className="mx-auto mt-8 max-w-[34rem]"
        >
          <CommandBar />
          <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
            <Link href="/signup" className="inline-flex items-center rounded-full bg-signal-600 px-5 py-2.5 text-[14px] font-medium text-white shadow-sm transition-all hover:-translate-y-px hover:bg-signal-500">Start free</Link>
            <CurlPill />
          </div>
        </motion.div>

        <div className="mt-12">
          <HeroArtifact />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}
          className="mx-auto mt-12 grid max-w-md grid-cols-3 gap-8 text-center"
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
 * Section heading
 * ------------------------------------------------------------------ */

function SectionHead({ eyebrow, title, sub }: { eyebrow: string; title: React.ReactNode; sub?: string }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <div className="text-[12px] font-medium uppercase tracking-[0.16em] text-signal-600">{eyebrow}</div>
      <h2 className="mt-4 font-serif text-[32px] font-medium leading-[1.05] tracking-[-0.01em] text-stone-900 sm:text-[42px]">{title}</h2>
      {sub && <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-stone-500">{sub}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The gap — agency
 * ------------------------------------------------------------------ */

function TheGap() {
  return (
    <section className="relative mx-auto max-w-[1080px] px-6 py-24">
      <Reveal>
        <div className="text-[12px] font-medium uppercase tracking-[0.16em] text-signal-600">The gap</div>
        <h2 className="mt-5 max-w-[20ch] font-serif text-[34px] font-medium leading-[1.04] tracking-[-0.01em] text-stone-900 sm:text-[52px]">
          Your agent writes a flawless iOS app. Then it just <span className="italic text-stone-400">…stops.</span>
        </h2>
        <p className="mt-6 max-w-[44rem] text-[16px] leading-relaxed text-stone-500">
          It can&rsquo;t build it. Can&rsquo;t open the simulator. Can&rsquo;t tap a button or read a crash
          log. The model has a brain — what it&rsquo;s missing is <span className="text-stone-900">hands</span>.
          Every other sandbox hands it Linux. Real apps need a <span className="text-stone-900">real Mac</span>.
        </p>
      </Reveal>

      <motion.div
        variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}
        className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-2"
      >
        <motion.div variants={fadeUp} className={`flex flex-col rounded-2xl bg-white p-7 ${CARD}`}>
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-stone-400">Without Herds</span>
          <ul className="mt-5 space-y-3.5">
            {["A Linux box that can't run Xcode", "No simulator, no codesigning, no GUI", "“Works on my machine” — but the agent has no machine", "You babysit CI runners and Dockerfiles"].map((t) => (
              <li key={t} className="flex items-start gap-3 text-[14px] text-stone-500">
                <span className="mt-[6px] h-1.5 w-1.5 flex-none rounded-full bg-stone-300" />
                {t}
              </li>
            ))}
          </ul>
        </motion.div>
        <motion.div variants={fadeUp} className={`relative flex flex-col overflow-hidden rounded-2xl bg-white p-7 ${CARD}`}>
          <div aria-hidden className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-signal-500/[0.10] blur-[60px]" />
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-signal-600">With Herds</span>
          <ul className="mt-5 space-y-3.5">
            {["The real macOS your users actually run", "Xcode, simulators, codesigning, AppleScript", "The Mac on your desk — exposed as an API", "One command. No infra to babysit."].map((t) => (
              <li key={t} className="flex items-start gap-3 text-[14px] text-stone-700">
                <span className="mt-[6px] h-1.5 w-1.5 flex-none rounded-full bg-signal-500 shadow-[0_0_8px_1px_rgba(27,189,134,0.4)]" />
                {t}
              </li>
            ))}
          </ul>
        </motion.div>
      </motion.div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * How it works
 * ------------------------------------------------------------------ */

const STEPS = [
  { n: "01", cmd: "herds auth", title: "Sign in", body: "Install the CLI and authenticate. No servers to provision, no images to build." },
  { n: "02", cmd: "herds host", title: "Your Mac goes live", body: "One command turns the Mac on your desk into a cloud runtime at you.herds.run." },
  { n: "03", cmd: "herds.mac().run(…)", title: "Agents run on it", body: "Drive it from any SDK, CLI, or agent — anywhere. Real macOS, on demand." },
];

function HowItWorks() {
  return (
    <section className="mx-auto max-w-[1080px] px-6 py-24">
      <Reveal>
        <SectionHead
          eyebrow="How it works"
          title={<>From your desk to the cloud<br className="hidden sm:block" /> in three commands</>}
          sub="No Dockerfiles. No CI runners to babysit. Just your Mac, exposed as an API."
        />
      </Reveal>
      <motion.div
        variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}
        className="mt-14 grid grid-cols-1 gap-4 md:grid-cols-3"
      >
        {STEPS.map((s) => (
          <motion.div key={s.n} variants={fadeUp} className={`flex flex-col rounded-2xl bg-white p-6 ${CARD}`}>
            <div className="flex items-center justify-between">
              <span className="font-serif text-[26px] text-stone-300 tnum">{s.n}</span>
              <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-stone-400">step</span>
            </div>
            <div className="mt-5 inline-flex w-fit items-center rounded-lg bg-[#f4f2ec] px-3 py-1.5 font-mono text-[12.5px] text-signal-600">
              <span className="mr-1.5 text-stone-400">$</span>{s.cmd}
            </div>
            <h3 className="mt-5 font-serif text-[19px] font-medium text-stone-900">{s.title}</h3>
            <p className="mt-2 text-[13.5px] leading-relaxed text-stone-500">{s.body}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Fleet — connection
 * ------------------------------------------------------------------ */

const FLEET = [
  { name: "M3 Max", kind: "Mac Studio", load: 38, sandboxes: 3 },
  { name: "M2 Pro", kind: "Mac mini", load: 71, sandboxes: 5 },
  { name: "M3", kind: "MacBook Air", load: 12, sandboxes: 1 },
];

function FleetNode({ m, delay }: { m: (typeof FLEET)[number]; delay: number }) {
  return (
    <motion.div variants={fadeUp} className={`relative flex flex-col rounded-2xl bg-white p-5 ${CARD}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Logo size={28} />
          <div className="leading-none">
            <div className="text-[14px] font-semibold tracking-tight text-stone-900">{m.name}</div>
            <div className="mt-1 text-[11px] text-stone-400">{m.kind}</div>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-signal-500/10 px-2 py-1 text-[10px] font-medium text-signal-600">
          <span className="h-1.5 w-1.5 animate-breathe rounded-full bg-signal-500" /> online
        </span>
      </div>
      <div className="mt-5 flex items-center justify-between text-[11px]">
        <span className="text-stone-400">CPU</span>
        <span className="tnum font-mono text-stone-500">{m.load}%</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-black/[0.07]">
        <motion.div initial={{ width: 0 }} whileInView={{ width: `${m.load}%` }} viewport={{ once: true }} transition={{ delay: delay + 0.2, duration: 0.9, ease: [0.22, 1, 0.36, 1] }} className="h-full rounded-full bg-gradient-to-r from-signal-500 to-signal-400" />
      </div>
      <div className="mt-4 font-mono text-[11px] text-stone-400">
        <span className="tnum text-stone-600">{m.sandboxes}</span> sandboxes · <span className="text-signal-600">{m.name.toLowerCase().replace(/\s/g, "")}.herds.run</span>
      </div>
    </motion.div>
  );
}

function Fleet() {
  return (
    <section className="mx-auto max-w-[1080px] px-6 py-24">
      <Reveal>
        <div className="grid items-end gap-6 md:grid-cols-[1fr_auto]">
          <div>
            <div className="text-[12px] font-medium uppercase tracking-[0.16em] text-signal-600">Connection</div>
            <h2 className="mt-4 max-w-[16ch] font-serif text-[34px] font-medium leading-[1.04] tracking-[-0.01em] text-stone-900 sm:text-[48px]">
              Every Mac you own. <span className="italic">One fleet.</span>
            </h2>
          </div>
          <p className="max-w-sm text-[15px] leading-relaxed text-stone-500 md:text-right">
            The Studio under your desk, the mini in the closet, the laptop in your bag — sign each one
            in and they join a private fleet you drive from anywhere.
          </p>
        </div>
      </Reveal>
      <motion.div
        variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}
        className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        {FLEET.map((m, i) => <FleetNode key={m.name} m={m} delay={i * 0.1} />)}
      </motion.div>
      <Reveal delay={0.1}>
        <div className="mt-5 flex items-center justify-center gap-2 font-mono text-[12.5px] text-stone-400">
          <span className="text-signal-600">$</span> herds host <span className="text-stone-300">— and the Mac is in the fleet.</span>
        </div>
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Capabilities — Orchid-style column row (line icons + serif heads)
 * ------------------------------------------------------------------ */

function MacIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><rect x="3" y="4" width="18" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><path d="M2 20h20M9 16l-.5 4M15 16l.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
function PortIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.07 0l-3 3A5 5 0 0 0 11 21l1.71-1.71" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
function VolumeIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><ellipse cx="12" cy="5" rx="8" ry="3" stroke="currentColor" strokeWidth="1.5" /><path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>;
}
function BoltIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-stone-800"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>;
}

const CAPS = [
  { icon: <MacIcon />, title: "Communication layer", body: "Real macOS — Xcode builds, iOS/macOS simulators, native app testing, codesigning, and AppleScript automation. The whole platform, not a stub." },
  { icon: <PortIcon />, title: "Expose ports → URLs", body: "Run a server inside a sandbox and get a public link instantly. Share a preview, hit an endpoint, ship a demo — no inbound ports opened." },
  { icon: <VolumeIcon />, title: "Persistent sandboxes", body: "Snapshot, suspend, resume. Mount durable volumes so caches, builds, and state survive across runs and machines." },
  { icon: <BoltIcon />, title: "Invisible execution", body: "Beyond notifications — a real runtime your agents drive. One API call hands an agent a full machine: files, GUI, network, the works." },
];

function Capabilities() {
  return (
    <section className="mx-auto max-w-[1080px] px-6 py-24">
      <Reveal>
        <SectionHead eyebrow="Capabilities" title="Things no Linux sandbox can do" sub="It's not an emulator or a VM you rent — it's the real machine, exposed as programmable infrastructure." />
      </Reveal>
      <motion.div
        variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}
        className="mt-16 grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-4"
      >
        {CAPS.map((c) => (
          <motion.div key={c.title} variants={fadeUp}>
            {c.icon}
            <h3 className="mt-5 font-serif text-[20px] font-medium leading-snug text-stone-900">{c.title}</h3>
            <p className="mt-3 text-[13.5px] leading-relaxed text-stone-500">{c.body}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}

/* ------------------------------------------------------------------ *
 * Built for agents
 * ------------------------------------------------------------------ */

function BuiltForAgents() {
  return (
    <section className="mx-auto max-w-[1080px] px-6 py-24">
      <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-[1fr_1fr]">
        <Reveal>
          <div className="text-[12px] font-medium uppercase tracking-[0.16em] text-signal-600">Built for agents</div>
          <h2 className="mt-4 font-serif text-[32px] font-medium leading-[1.05] tracking-[-0.01em] text-stone-900 sm:text-[40px]">
            Give Claude hands on a <span className="italic">real Mac.</span>
          </h2>
          <p className="mt-5 max-w-lg text-[15.5px] leading-relaxed text-stone-500">
            Your agents already write the code. Now they can build it, run it, click through the app, and
            verify it — on the same macOS your users run. A single API call hands an agent a full machine.
          </p>
          <ul className="mt-7 space-y-3">
            {["Build & ship iOS apps end-to-end, autonomously", "Drive native UI, screenshot, and assert on real pixels", "Isolated sandboxes per task — spin up, tear down, repeat"].map((t) => (
              <li key={t} className="flex items-start gap-3 text-[14px] text-stone-700">
                <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-signal-500 shadow-[0_0_8px_1px_rgba(27,189,134,0.4)]" />
                {t}
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/skill" className="inline-flex items-center gap-1.5 rounded-full bg-stone-900 px-4 py-2 text-[13.5px] font-medium text-white transition-colors hover:bg-stone-700">
              Get the skill <span aria-hidden className="text-white/50">→</span>
            </Link>
            <a href="/skill.md" className="font-mono text-[12.5px] text-stone-400 transition-colors hover:text-stone-600">herds.run/skill.md</a>
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <div className={`overflow-hidden rounded-2xl bg-white font-mono text-[12.5px] sm:text-[13px] ${CARD}`}>
            <div className="flex items-center gap-2 bg-[#f1efe9] px-4 py-3">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              <span className="ml-2 text-[11px] tracking-tight text-stone-400">agent.py</span>
            </div>
            <pre className="overflow-x-auto px-5 py-5 leading-[1.85] text-stone-600">
              <code>
                <span className="text-stone-400">{"# hand an agent a real Mac\n"}</span>
                <span className="text-signal-600">{"mac"}</span>{" = herds."}<span className="text-stone-800">{"mac"}</span>{"()\n\n"}
                <span className="text-signal-600">{"build"}</span>{" = mac."}<span className="text-stone-800">{"run"}</span>{'("xcodebuild -scheme App")\n'}
                <span className="text-stone-800">{"url"}</span>{"  = mac."}<span className="text-stone-800">{"expose"}</span>{"(3000)  "}<span className="text-stone-400">{"# → public link"}</span>{"\n\n"}
                <span className="text-stone-800">{"agent"}</span>{".verify("}<span className="text-stone-800">{"url"}</span>{", screenshot="}<span className="text-signal-600">{"True"}</span>{")"}
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
    <section className="mx-auto max-w-[1080px] px-6 py-24">
      <Reveal>
        <div className={`relative overflow-hidden rounded-3xl bg-stone-900 px-8 py-16 text-center sm:px-16 sm:py-20`}>
          <div aria-hidden className="pointer-events-none absolute left-1/2 top-0 h-[300px] w-[600px] -translate-x-1/2 rounded-full bg-signal-500/20 blur-[110px]" />
          <div className="relative">
            <h2 className="font-serif text-[32px] font-medium leading-[1.05] tracking-[-0.01em] text-white sm:text-[46px]">
              Connect your Mac in <span className="italic">60 seconds.</span>
            </h2>
            <p className="mx-auto mt-4 max-w-md text-[15px] leading-relaxed text-stone-400">
              Every Mac becomes an API. Your own machine, your own infra — live with one command.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link href="/signup" className="inline-flex items-center rounded-full bg-signal-500 px-6 py-3 text-[14px] font-medium text-white shadow-sm transition-colors hover:bg-signal-400">Start free</Link>
              <Link href="/login" className="inline-flex items-center rounded-full bg-white/[0.08] px-6 py-3 text-[14px] font-medium text-stone-200 transition-colors hover:bg-white/[0.14]">Log in</Link>
            </div>
            <div className="mt-6 font-mono text-[12.5px] text-stone-500"><span className="text-signal-400">$</span> herds host</div>
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
 * Page
 * ------------------------------------------------------------------ */

export function Landing() {
  return (
    <div className="min-h-screen bg-[#faf9f6] font-sans text-stone-900 antialiased">
      <TopBar />
      <main>
        <Hero />
        <TheGap />
        <HowItWorks />
        <Fleet />
        <Capabilities />
        <BuiltForAgents />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
