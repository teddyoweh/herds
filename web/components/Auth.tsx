"use client";

import { Logo } from "@/components/Logo";
import Link from "next/link";
import { motion } from "framer-motion";

/* Shared auth chrome — flat light theme matching the marketing landing:
   pure-white page, gray (#f3f2ee) card, white input fields, green primary
   action, serif heading. No shadows, no border lines. */

export const INPUT =
  "w-full rounded-xl bg-white px-3.5 py-2.5 text-[14px] text-stone-900 outline-none ring-1 ring-transparent transition focus:ring-2 focus:ring-signal-500/40 placeholder:text-stone-400";
export const SUBMIT =
  "flex w-full items-center justify-center gap-2 rounded-xl bg-signal-600 py-2.5 text-[14px] font-medium text-white transition hover:bg-signal-500 disabled:cursor-not-allowed disabled:opacity-40";

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-stone-400">{label}</label>
      {children}
    </div>
  );
}

export function AuthShell({ children, footer }: { children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-[80] grid place-items-center overflow-y-auto bg-white px-4 py-12 font-sans text-stone-900 antialiased">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-sm"
      >
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <Logo size={30} />
          <span className="text-[16px] font-semibold tracking-tight text-stone-900">Herds</span>
        </Link>

        <div className="rounded-2xl bg-[#f3f2ee] px-7 py-8">{children}</div>

        {footer && <p className="mt-6 text-center text-[13px] text-stone-400">{footer}</p>}
      </motion.div>
    </div>
  );
}

export function Divider() {
  return (
    <div className="my-6 flex items-center gap-3">
      <span className="h-px flex-1 bg-black/[0.08]" />
      <span className="text-[11px] uppercase tracking-[0.14em] text-stone-400">or</span>
      <span className="h-px flex-1 bg-black/[0.08]" />
    </div>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <motion.p
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-2 rounded-xl bg-rose-500/[0.08] px-3 py-2 text-[12.5px] leading-relaxed text-rose-600"
    >
      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" />
      <span>{children}</span>
    </motion.p>
  );
}

export function Spinner() {
  return <span className="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-white/40 border-t-white" />;
}

export function GitHubButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-7 flex w-full items-center justify-center gap-2.5 rounded-xl bg-white py-2.5 text-[13.5px] font-medium text-stone-800 transition hover:bg-stone-50"
    >
      <GitHubMark />
      Continue with GitHub
    </button>
  );
}

export function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
