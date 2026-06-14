// Platform (self-serve) client for the Herds relay.
//
// Auth here is token-based and password-free (ngrok-style): we provision an
// account against the relay, get back an `hx_…` token + the account's dashboard
// URL, and persist that as the local session.

// Use a *.relay.herds.run subdomain (not the apex): the apex can get stale-cached
// to the old wildcard, but fresh subdomains always resolve straight to the box.
const RELAY_API =
  process.env.NEXT_PUBLIC_HERDS_RELAY_API?.replace(/\/$/, "") || "https://api.relay.herds.run";

export type Session = { token: string; account: string; url: string };

const SESSION_KEY = "herds_session";

/** Turn an email local-part (or arbitrary string) into a relay-safe account slug. */
export function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/@.*$/, "") // drop the domain if a full email was passed
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && typeof data.error === "string") return data.error;
    if (data && typeof data.message === "string") return data.message;
  } catch {
    /* not json */
  }
  return `Relay error (${res.status})`;
}

/**
 * Provision a brand new account on the relay.
 * POST `${RELAY_API}/relay/provision` with an optional `{ name }`.
 * Returns `{ token, account, url }`.
 */
export async function provisionAccount(name?: string): Promise<Session> {
  let res: Response;
  try {
    res = await fetch(`${RELAY_API}/relay/provision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(name ? { name } : {}),
    });
  } catch {
    throw new Error("Couldn't reach the relay. Check your connection and try again.");
  }
  if (!res.ok) throw new Error(await readError(res));

  const data = (await res.json()) as Partial<Session>;
  if (!data.token || !data.account || !data.url) {
    throw new Error("The relay returned an unexpected response.");
  }
  return { token: data.token, account: data.account, url: data.url };
}

/**
 * Validate an existing token and resolve its session.
 * GET `${RELAY_API}/relay/whoami?token=…`. Returns `{ account, url }`.
 */
export async function signInWithToken(token: string): Promise<Session> {
  const trimmed = token.trim();
  if (!trimmed) throw new Error("Enter your token to continue.");

  let res: Response;
  try {
    res = await fetch(`${RELAY_API}/relay/whoami?token=${encodeURIComponent(trimmed)}`);
  } catch {
    throw new Error("Couldn't reach the relay. Check your connection and try again.");
  }
  if (res.status === 401 || res.status === 403) {
    throw new Error("That token isn't valid. Double-check and try again.");
  }
  if (!res.ok) throw new Error(await readError(res));

  const data = (await res.json()) as { account?: string; url?: string };
  if (!data.account || !data.url) {
    throw new Error("The relay returned an unexpected response.");
  }
  return { token: trimmed, account: data.account, url: data.url };
}

/** Create an account with email + password. POST `/relay/register`. */
export async function registerWithEmail(email: string, password: string): Promise<Session> {
  let res: Response;
  try {
    res = await fetch(`${RELAY_API}/relay/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), password, name: slugify(email) }),
    });
  } catch {
    throw new Error("Couldn't reach the relay. Check your connection and try again.");
  }
  if (!res.ok) throw new Error(await readError(res));
  const data = (await res.json()) as Partial<Session>;
  if (!data.token || !data.account || !data.url) throw new Error("The relay returned an unexpected response.");
  const s = { token: data.token, account: data.account, url: data.url };
  setSession(s);
  return s;
}

/** Sign in with email + password. POST `/relay/login`. */
export async function loginWithEmail(email: string, password: string): Promise<Session> {
  let res: Response;
  try {
    res = await fetch(`${RELAY_API}/relay/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), password }),
    });
  } catch {
    throw new Error("Couldn't reach the relay. Check your connection and try again.");
  }
  if (res.status === 401) throw new Error("Invalid email or password.");
  if (!res.ok) throw new Error(await readError(res));
  const data = (await res.json()) as Partial<Session>;
  if (!data.token || !data.account || !data.url) throw new Error("The relay returned an unexpected response.");
  const s = { token: data.token, account: data.account, url: data.url };
  setSession(s);
  return s;
}

export type AccountStatus = { account: string; url: string; email: string | null; online: boolean };

export type ApiToken = { label: string; scope: string; masked: string };

/** Manage scoped tokens on the connected Mac's control plane (CORS is open). */
export async function listTokens(url: string, token: string): Promise<ApiToken[]> {
  const res = await fetch(`${url}/v1/keys`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error("Couldn't load tokens");
  return ((await res.json()).keys || []) as ApiToken[];
}

export async function createToken(url: string, token: string, label: string, scope: string): Promise<{ key: string; scope: string; label: string }> {
  const res = await fetch(`${url}/v1/keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ label, scope }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function revokeToken(url: string, token: string, prefix: string): Promise<void> {
  const head = prefix.split("…")[0];
  const res = await fetch(`${url}/v1/keys/${encodeURIComponent(head)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await readError(res));
}

/** Live account status (is the Mac connected?). GET `/relay/status?token=…`. */
export async function getStatus(token: string): Promise<AccountStatus | null> {
  try {
    const res = await fetch(`${RELAY_API}/relay/status?token=${encodeURIComponent(token)}`);
    if (!res.ok) return null;
    return (await res.json()) as AccountStatus;
  } catch {
    return null;
  }
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    if (!s || !s.token || !s.account || !s.url) return null;
    return s;
  } catch {
    return null;
  }
}

export function setSession(s: Session): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(s));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(SESSION_KEY);
}
