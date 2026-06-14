"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { getSession, clearSession, type Session } from "@/lib/platform";

export default function WelcomePage() {
  const router = useRouter();
  const [session, setSessionState] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const s = getSession();
    if (!s) {
      router.replace("/signup");
      return;
    }
    setSessionState(s);
    setReady(true);
  }, [router]);

  if (!ready || !session) {
    return <div className="fixed inset-0 z-[80] bg-ink-950" />;
  }

  const authCmd = `herds auth --token ${session.token}`;
  const hostCmd = `herds host`;

  return (
    <div className="fixed inset-0 z-[80] overflow-y-auto bg-ink-950 px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="mx-auto w-full max-w-xl"
      >
        {/* Wordmark */}
        <div className="mb-9 flex items-center justify-center gap-2.5">
          <Logo size={32} />
          <span className="text-[16px] font-semibold tracking-tightest text-white">Herds</span>
        </div>

        {/* Account ready */}
        <div className="text-center">
          <motion.div
            initial={{ scale: 0.7, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, type: "spring", stiffness: 360, damping: 22 }}
            className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-signal-500/15 text-signal-400"
          >
            <CheckIcon />
          </motion.div>
          <h1 className="mt-4 text-[22px] font-semibold tracking-tightest text-white">
            Account ready
          </h1>
          <p className="mt-1.5 text-[14px] leading-relaxed text-zinc-500">
            Your relay is live at{" "}
            <span className="font-mono text-zinc-300">{session.account}.relay.herds.run</span>.
            Connect a Mac to start serving requests.
          </p>
        </div>

        {/* Commands */}
        <div className="surface mt-8 px-6 py-6">
          <div className="flex items-center justify-between">
            <p className="label">Connect your Mac</p>
            <span className="text-[11px] tabular-nums text-zinc-600">2 steps</span>
          </div>

          <div className="mt-4 space-y-3">
            <CommandRow step={1} label="Authenticate this machine" command={authCmd} />
            <CommandRow step={2} label="Start serving" command={hostCmd} />
          </div>

          <WaitingIndicator />
        </div>

        {/* CTA */}
        <a
          href={session.url}
          target="_blank"
          rel="noreferrer"
          className="group mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-signal-500 py-3 text-[14px] font-medium text-ink-950 transition hover:bg-signal-400"
        >
          Open my dashboard
          <span className="transition-transform duration-200 group-hover:translate-x-0.5">→</span>
        </a>

        <div className="mt-6 flex items-center justify-center gap-4 text-[12.5px] text-zinc-600">
          <span className="font-mono text-zinc-700">{session.url}</span>
          <span className="text-zinc-800">·</span>
          <button
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
            className="underline-offset-4 transition hover:text-zinc-400 hover:underline"
          >
            Sign out
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function CommandRow({ step, label, command }: { step: number; label: string; command: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <span className="grid h-4 w-4 place-items-center rounded-full bg-white/[0.06] text-[10px] font-medium tabular-nums text-zinc-400">
          {step}
        </span>
        <span className="text-[12.5px] text-zinc-500">{label}</span>
      </div>
      <div className="group flex items-center gap-3 rounded-lg bg-black/40 px-3.5 py-2.5 ring-1 ring-white/[0.05]">
        <span className="select-none text-zinc-700">$</span>
        <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-[12.5px] text-zinc-200 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {command}
        </code>
        <button
          onClick={copy}
          aria-label="Copy command"
          className="shrink-0 rounded-md px-2 py-1 text-[11px] font-medium text-zinc-500 transition hover:bg-white/[0.06] hover:text-zinc-200"
        >
          {copied ? (
            <span className="flex items-center gap-1 text-signal-400">
              <CheckIcon small /> Copied
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <CopyIcon /> Copy
            </span>
          )}
        </button>
      </div>
    </div>
  );
}

function WaitingIndicator() {
  return (
    <div className="mt-5 flex items-center gap-2.5 rounded-lg bg-white/[0.025] px-3.5 py-2.5">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-signal-400/60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-400" />
      </span>
      <span className="text-[12.5px] text-zinc-500">Waiting for your Mac to connect…</span>
    </div>
  );
}

function CheckIcon({ small }: { small?: boolean }) {
  const s = small ? 11 : 20;
  return (
    <svg viewBox="0 0 24 24" width={s} height={s} fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  );
}
