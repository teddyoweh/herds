"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useToast } from "@/components/Toast";
import { loginWithEmail, signInWithToken, setSession, getSession } from "@/lib/platform";

export default function LoginPage() {
  const router = useRouter();
  const toast = useToast();
  useEffect(() => {
    if (getSession()) router.replace("/dashboard");
  }, [router]);
  const [mode, setMode] = useState<"password" | "token">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
  const valid = mode === "password" ? emailValid && password.length >= 1 : token.trim().startsWith("hx_");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    try {
      if (mode === "password") await loginWithEmail(email, password);
      else setSession(await signInWithToken(token));
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't sign you in. Try again.");
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <h1 className="text-center text-[19px] font-semibold tracking-tightest text-white">
        Log in to Herds
      </h1>
      <p className="mt-1.5 text-center text-[13px] leading-relaxed text-zinc-500">
        {mode === "password" ? "Welcome back." : "Paste an access token from the CLI."}
      </p>

      <button
        type="button"
        onClick={() => toast("GitHub sign-in is coming soon.", "default")}
        className="mt-7 flex w-full items-center justify-center gap-2.5 rounded-lg bg-white/[0.045] py-2.5 text-[13.5px] font-medium text-zinc-200 shadow-e1 transition hover:bg-white/[0.07]"
      >
        <GitHubMark />
        Continue with GitHub
      </button>

      <Divider />

      <form onSubmit={onSubmit} className="space-y-3.5">
        {mode === "password" ? (
          <>
            <div>
              <label htmlFor="email" className="label mb-1.5 block">Email</label>
              <input
                id="email" type="email" autoFocus autoComplete="email" value={email}
                onChange={(e) => { setEmail(e.target.value); if (error) setError(null); }}
                placeholder="you@company.com"
                className="w-full rounded-lg bg-black/30 px-3 py-2.5 text-[14px] text-zinc-100 outline-none ring-1 ring-white/[0.08] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
              />
            </div>
            <div>
              <label htmlFor="password" className="label mb-1.5 block">Password</label>
              <input
                id="password" type="password" autoComplete="current-password" value={password}
                onChange={(e) => { setPassword(e.target.value); if (error) setError(null); }}
                placeholder="••••••••"
                className="w-full rounded-lg bg-black/30 px-3 py-2.5 text-[14px] text-zinc-100 outline-none ring-1 ring-white/[0.08] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
              />
            </div>
          </>
        ) : (
          <div>
            <label htmlFor="token" className="label mb-1.5 block">Access token</label>
            <input
              id="token" type="password" autoFocus autoComplete="off" spellCheck={false} value={token}
              onChange={(e) => { setToken(e.target.value); if (error) setError(null); }}
              placeholder="hx_…"
              className="w-full rounded-lg bg-black/30 px-3 py-2.5 font-mono text-[13px] text-zinc-100 outline-none ring-1 ring-white/[0.08] transition focus:ring-signal-500/50 placeholder:text-zinc-700"
            />
          </div>
        )}

        {error && <ErrorNote>{error}</ErrorNote>}

        <button
          type="submit"
          disabled={!valid || loading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 py-2.5 text-[14px] font-medium text-ink-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? (<><Spinner /> Signing in…</>) : "Log in"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => { setMode(mode === "password" ? "token" : "password"); setError(null); }}
        className="mt-5 block w-full text-center text-[12.5px] text-zinc-500 transition hover:text-zinc-300"
      >
        {mode === "password" ? "Sign in with an access token instead" : "Sign in with email + password instead"}
      </button>
    </AuthShell>
  );
}

/* ── Shared auth chrome ── */

function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-[80] grid place-items-center overflow-y-auto bg-ink-950 px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-sm"
      >
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <Logo size={32} />
          <span className="text-[16px] font-semibold tracking-tightest text-white">Herds</span>
        </Link>

        <div className="surface px-7 py-8">{children}</div>

        <p className="mt-6 text-center text-[13px] text-zinc-600">
          New here?{" "}
          <Link href="/signup" className="text-zinc-300 underline-offset-4 transition hover:text-white hover:underline">
            Sign up
          </Link>
        </p>
      </motion.div>
    </div>
  );
}

function Divider() {
  return (
    <div className="my-6 flex items-center gap-3">
      <span className="h-px flex-1 bg-white/[0.07]" />
      <span className="text-[11px] uppercase tracking-[0.14em] text-zinc-700">or</span>
      <span className="h-px flex-1 bg-white/[0.07]" />
    </div>
  );
}

function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <motion.p
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-2 rounded-lg bg-rose-500/[0.08] px-3 py-2 text-[12.5px] leading-relaxed text-rose-300"
    >
      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
      <span>{children}</span>
    </motion.p>
  );
}

function Spinner() {
  return (
    <span className="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-ink-950/30 border-t-ink-950" />
  );
}

function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
