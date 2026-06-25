"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AuthShell, Field, Divider, ErrorNote, Spinner, INPUT, SUBMIT } from "@/components/Auth";
import {
  approveDevice,
  lookupDevice,
  loginWithEmail,
  registerWithEmail,
  signInWithToken,
  setSession,
  getSession,
  clearSession,
  type Session,
} from "@/lib/platform";

/* The browser half of `herds auth`: the CLI opens this page with a ?code=, the
   user signs in here, and we bind the code to their account so the waiting CLI
   gets its token. Mirrors the GitHub / AWS-SSO device-approval pattern. */

type Mode = "login" | "create" | "token";

function Activate() {
  const params = useSearchParams();
  const [code, setCode] = useState((params.get("code") || "").toUpperCase());
  const [confirmed, setConfirmed] = useState(false); // code verified against the relay
  const [checking, setChecking] = useState(false);

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [doneAccount, setDoneAccount] = useState<string | null>(null);
  const [session, setLocalSession] = useState<Session | null>(null);

  useEffect(() => {
    setLocalSession(getSession());
  }, []);

  // Verify the code is real as soon as we have one, so we fail fast on a typo.
  useEffect(() => {
    if (!code || confirmed) return;
    let cancelled = false;
    setChecking(true);
    lookupDevice(code)
      .then(() => { if (!cancelled) { setConfirmed(true); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : "Invalid code."); })
      .finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, [code, confirmed]);

  async function approveWith(t: string) {
    const { account } = await approveDevice(code, t);
    setDoneAccount(account);
  }

  async function onApproveExisting() {
    if (!session || loading) return;
    setLoading(true); setError(null);
    try {
      await approveWith(session.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't approve. Try again.");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setLoading(true); setError(null);
    try {
      let s: Session;
      if (mode === "token") { s = await signInWithToken(token); setSession(s); }
      else if (mode === "create") s = await registerWithEmail(email, password);
      else s = await loginWithEmail(email, password);
      await approveWith(s.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't sign you in. Try again.");
    } finally {
      setLoading(false);
    }
  }

  // ---- success ----
  if (doneAccount) {
    return (
      <AuthShell>
        <div className="text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-signal-500 text-white">
            <svg width="22" height="22" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M3 8.5 6.5 12 13 4" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <h1 className="ed mt-5 text-[26px] leading-tight text-stone-900">You&rsquo;re connected</h1>
          <p className="mt-2 text-[13.5px] leading-relaxed text-stone-500">
            Signed in as <span className="font-medium text-stone-800">{doneAccount}</span>. Return to your terminal —
            the CLI is now authenticated. You can close this tab.
          </p>
          <Link href="/dashboard" className={`${SUBMIT} mt-6 inline-flex w-full justify-center`}>Open the dashboard</Link>
        </div>
      </AuthShell>
    );
  }

  // ---- no code yet: ask for it ----
  if (!code) {
    return (
      <AuthShell>
        <h1 className="ed text-center text-[26px] leading-tight text-stone-900">Connect your CLI</h1>
        <p className="mt-2 text-center text-[13.5px] leading-relaxed text-stone-500">
          Enter the code shown by <span className="font-mono text-stone-700">herds auth</span>.
        </p>
        <form
          onSubmit={(e) => { e.preventDefault(); setCode((e.currentTarget.elements.namedItem("code") as HTMLInputElement).value.trim().toUpperCase()); }}
          className="mt-6 space-y-3.5"
        >
          <Field label="Device code">
            <input id="code" name="code" autoFocus autoComplete="off" spellCheck={false} placeholder="ABCD-EF23"
              className={`${INPUT} text-center font-mono text-[16px] tracking-[0.25em]`} />
          </Field>
          <button type="submit" className={SUBMIT}>Continue</button>
        </form>
      </AuthShell>
    );
  }

  // ---- code present: confirm + sign in ----
  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
  const valid = mode === "token" ? token.trim().startsWith("hx_") : emailValid && password.length >= (mode === "create" ? 8 : 1);

  return (
    <AuthShell footer={<>Wrong code?{" "}<button onClick={() => { setCode(""); setConfirmed(false); setError(null); }} className="text-stone-800 underline-offset-4 transition hover:text-stone-950 hover:underline">Enter another</button></>}>
      <h1 className="ed text-center text-[26px] leading-tight text-stone-900">Approve this Mac</h1>
      <p className="mt-2 text-center text-[13.5px] leading-relaxed text-stone-500">
        Confirm the code matches the one in your terminal, then sign in to connect it.
      </p>

      <div className="mt-5 flex items-center justify-center gap-2">
        <span className="rounded-xl bg-[#f3f2ee] px-4 py-2.5 font-mono text-[18px] tracking-[0.22em] text-stone-900">{code}</span>
        {checking ? <Spinner /> : confirmed ? (
          <span className="grid h-5 w-5 place-items-center rounded-full bg-signal-500 text-white"><svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.6"><path d="M3 8.5 6.5 12 13 4" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
        ) : null}
      </div>

      {session ? (
        <div className="mt-6">
          <button type="button" disabled={loading || !confirmed} onClick={onApproveExisting} className={SUBMIT}>
            {loading ? (<><Spinner /> Connecting…</>) : <>Approve as {session.account}</>}
          </button>
          {error && <div className="mt-3"><ErrorNote>{error}</ErrorNote></div>}
          <button type="button" onClick={() => { clearSession(); setLocalSession(null); }} className="mt-4 block w-full text-center text-[12.5px] text-stone-400 transition hover:text-stone-700">
            Use a different account
          </button>
        </div>
      ) : (
        <>
          <Divider />
          <form onSubmit={onSubmit} className="space-y-3.5">
            {mode === "token" ? (
              <Field label="Access token">
                <input id="token" type="password" autoFocus autoComplete="off" spellCheck={false} value={token}
                  onChange={(e) => { setToken(e.target.value); if (error) setError(null); }}
                  placeholder="hx_…" className={`${INPUT} font-mono text-[13px]`} />
              </Field>
            ) : (
              <>
                <Field label="Email">
                  <input id="email" type="email" autoFocus autoComplete="email" value={email}
                    onChange={(e) => { setEmail(e.target.value); if (error) setError(null); }}
                    placeholder="you@company.com" className={INPUT} />
                </Field>
                <Field label="Password">
                  <input id="password" type="password" autoComplete={mode === "create" ? "new-password" : "current-password"} value={password}
                    onChange={(e) => { setPassword(e.target.value); if (error) setError(null); }}
                    placeholder="••••••••" className={INPUT} />
                </Field>
              </>
            )}

            {error && <ErrorNote>{error}</ErrorNote>}

            <button type="submit" disabled={!valid || loading || !confirmed} className={SUBMIT}>
              {loading ? (<><Spinner /> Connecting…</>) : "Sign in & connect"}
            </button>
          </form>

          <div className="mt-5 flex flex-col items-center gap-2 text-[12.5px] text-stone-400">
            {mode !== "create" && <button type="button" onClick={() => { setMode("create"); setError(null); }} className="transition hover:text-stone-700">New to Herds? Create an account</button>}
            {mode !== "login" && <button type="button" onClick={() => { setMode("login"); setError(null); }} className="transition hover:text-stone-700">Already have one? Log in</button>}
            {mode !== "token" && <button type="button" onClick={() => { setMode("token"); setError(null); }} className="transition hover:text-stone-700">Use an access token instead</button>}
          </div>
        </>
      )}
    </AuthShell>
  );
}

export default function ActivatePage() {
  return (
    <Suspense fallback={<AuthShell><div className="grid place-items-center py-8"><Spinner /></div></AuthShell>}>
      <Activate />
    </Suspense>
  );
}
