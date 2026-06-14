"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/Toast";
import { AuthShell, Field, Divider, ErrorNote, Spinner, GitHubButton, INPUT, SUBMIT } from "@/components/Auth";
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
    <AuthShell footer={<>New here?{" "}<Link href="/signup" className="text-stone-800 underline-offset-4 transition hover:text-stone-950 hover:underline">Sign up</Link></>}>
      <h1 className="ed text-center text-[26px] leading-tight text-stone-900">Log in to Herds</h1>
      <p className="mt-2 text-center text-[13.5px] leading-relaxed text-stone-500">
        {mode === "password" ? "Welcome back." : "Paste an access token from the CLI."}
      </p>

      <GitHubButton onClick={() => toast("GitHub sign-in is coming soon.", "default")} />

      <Divider />

      <form onSubmit={onSubmit} className="space-y-3.5">
        {mode === "password" ? (
          <>
            <Field label="Email">
              <input id="email" type="email" autoFocus autoComplete="email" value={email}
                onChange={(e) => { setEmail(e.target.value); if (error) setError(null); }}
                placeholder="you@company.com" className={INPUT} />
            </Field>
            <Field label="Password">
              <input id="password" type="password" autoComplete="current-password" value={password}
                onChange={(e) => { setPassword(e.target.value); if (error) setError(null); }}
                placeholder="••••••••" className={INPUT} />
            </Field>
          </>
        ) : (
          <Field label="Access token">
            <input id="token" type="password" autoFocus autoComplete="off" spellCheck={false} value={token}
              onChange={(e) => { setToken(e.target.value); if (error) setError(null); }}
              placeholder="hx_…" className={`${INPUT} font-mono text-[13px]`} />
          </Field>
        )}

        {error && <ErrorNote>{error}</ErrorNote>}

        <button type="submit" disabled={!valid || loading} className={SUBMIT}>
          {loading ? (<><Spinner /> Signing in…</>) : "Log in"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => { setMode(mode === "password" ? "token" : "password"); setError(null); }}
        className="mt-5 block w-full text-center text-[12.5px] text-stone-400 transition hover:text-stone-700"
      >
        {mode === "password" ? "Sign in with an access token instead" : "Sign in with email + password instead"}
      </button>
    </AuthShell>
  );
}
