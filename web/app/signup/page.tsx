"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useToast } from "@/components/Toast";
import { AuthShell, Field, Divider, ErrorNote, Spinner, GitHubButton, INPUT, SUBMIT } from "@/components/Auth";
import { registerWithEmail, getSession } from "@/lib/platform";

export default function SignupPage() {
  const router = useRouter();
  const toast = useToast();
  useEffect(() => {
    if (getSession()) router.replace("/dashboard");
  }, [router]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
  const valid = emailValid && password.length >= 8;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    try {
      await registerWithEmail(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
      setLoading(false);
    }
  }

  return (
    <AuthShell footer={<>Already have an account?{" "}<Link href="/login" className="text-stone-800 underline-offset-4 transition hover:text-stone-950 hover:underline">Log in</Link></>}>
      <h1 className="ed text-center text-[26px] leading-tight text-stone-900">Create your account</h1>
      <p className="mt-2 text-center text-[13.5px] leading-relaxed text-stone-500">
        Turn any Mac into an API. No card required.
      </p>

      <GitHubButton onClick={() => toast("GitHub sign-in is coming soon.", "default")} />

      <Divider />

      <form onSubmit={onSubmit} className="space-y-3.5">
        <Field label="Work email">
          <input id="email" type="email" autoFocus autoComplete="email" inputMode="email" value={email}
            onChange={(e) => { setEmail(e.target.value); if (error) setError(null); }}
            placeholder="you@company.com" className={INPUT} />
        </Field>
        <Field label="Password">
          <input id="password" type="password" autoComplete="new-password" value={password}
            onChange={(e) => { setPassword(e.target.value); if (error) setError(null); }}
            placeholder="at least 8 characters" className={INPUT} />
        </Field>

        {error && <ErrorNote>{error}</ErrorNote>}

        <button type="submit" disabled={!valid || loading} className={SUBMIT}>
          {loading ? (<><Spinner /> Creating account…</>) : "Create account"}
        </button>
      </form>

      <p className="mt-5 text-center text-[12.5px] text-stone-400">Free to start. No card required.</p>
    </AuthShell>
  );
}
