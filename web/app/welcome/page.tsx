"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
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
    return <div className="fixed inset-0 z-[80] bg-white" />;
  }

  const authCmd = `herds auth --token ${session.token}`;
  const hostCmd = `herds host`;

  return (
    <div className="fixed inset-0 z-[80] overflow-y-auto bg-white px-4 py-12 font-sans text-stone-900 antialiased">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="mx-auto w-full max-w-xl"
      >
        <div className="mb-9 flex items-center justify-center gap-2.5">
          <Logo size={30} />
          <span className="text-[16px] font-semibold tracking-tight text-stone-900">Herds</span>
        </div>

        <div className="text-center">
          <motion.div
            initial={{ scale: 0.7, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, type: "spring", stiffness: 360, damping: 22 }}
            className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-signal-500/15 text-signal-600"
          >
            <CheckIcon />
          </motion.div>
          <h1 className="ed mt-5 text-[28px] leading-tight text-stone-900">Account ready</h1>
          <p className="mt-2 text-[14px] leading-relaxed text-stone-500">
            Your relay is live at{" "}
            <span className="font-mono text-stone-700">{session.account}.relay.herds.run</span>.
            Connect a Mac to start serving requests.
          </p>
        </div>

        <div className="mt-8 rounded-2xl bg-[#f3f2ee] px-6 py-6">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-stone-400">Connect your Mac</p>
            <span className="text-[11px] tabular-nums text-stone-400">2 steps</span>
          </div>

          <div className="mt-4 space-y-3">
            <CommandRow step={1} label="Authenticate this machine" command={authCmd} />
            <CommandRow step={2} label="Start serving" command={hostCmd} />
          </div>

          <WaitingIndicator />
        </div>

        <a
          href={session.url}
          target="_blank"
          rel="noreferrer"
          className="group mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-signal-600 py-3 text-[14px] font-medium text-white transition hover:bg-signal-500"
        >
          Open my dashboard
          <span className="transition-transform duration-200 group-hover:translate-x-0.5">→</span>
        </a>

        <div className="mt-6 flex items-center justify-center gap-4 text-[12.5px] text-stone-400">
          <span className="font-mono">{session.url}</span>
          <span className="text-stone-300">·</span>
          <button
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
            className="underline-offset-4 transition hover:text-stone-700 hover:underline"
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
        <span className="grid h-4 w-4 place-items-center rounded-full bg-white text-[10px] font-medium tabular-nums text-stone-500">
          {step}
        </span>
        <span className="text-[12.5px] text-stone-500">{label}</span>
      </div>
      <div className="group flex items-center gap-3 rounded-xl bg-white px-3.5 py-2.5">
        <span className="select-none text-stone-400">$</span>
        <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-[12.5px] text-stone-800 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {command}
        </code>
        <button
          onClick={copy}
          aria-label="Copy command"
          className="shrink-0 rounded-md px-2 py-1 text-[11px] font-medium text-stone-400 transition hover:bg-black/[0.04] hover:text-stone-700"
        >
          {copied ? (
            <span className="flex items-center gap-1 text-signal-600">
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
    <div className="mt-5 flex items-center gap-2.5 rounded-xl bg-white px-3.5 py-2.5">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-signal-400/60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-500" />
      </span>
      <span className="text-[12.5px] text-stone-500">Waiting for your Mac to connect…</span>
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
