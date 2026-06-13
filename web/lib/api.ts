"use client";

import useSWR from "swr";

// The dashboard talks to the control plane. In host mode the control plane
// serves the dashboard, so the API is same-origin; in dev a build-time override
// points at the separate control plane.
export const API = (() => {
  const env = process.env.NEXT_PUBLIC_HERDS_API?.replace(/\/$/, "");
  if (env) return env;
  if (typeof window !== "undefined") return window.location.origin;
  return "http://127.0.0.1:8787";
})();

// ---- auth (host mode) ------------------------------------------------------
export function getToken(): string {
  return (typeof window !== "undefined" && localStorage.getItem("herds_token")) || "";
}
export function setToken(t: string) {
  if (typeof window !== "undefined") localStorage.setItem("herds_token", t);
}
export function authInit(init: RequestInit = {}): RequestInit {
  const t = getToken();
  return t ? { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${t}` } } : init;
}
/** Build a same-origin WS url with the token as a query param (browsers can't set WS headers). */
export function wsUrl(path: string): string {
  const base = API.replace(/^http/, "ws");
  const t = getToken();
  if (!t) return `${base}${path}`;
  return `${base}${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(t)}`;
}

class Unauthorized extends Error {}
export const isUnauthorized = (e: unknown) => e instanceof Unauthorized;

const fetcher = async (path: string) => {
  const res = await fetch(`${API}${path}`, authInit());
  if (res.status === 401) throw new Unauthorized("unauthorized");
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
};

// Poll fast enough to feel alive, slow enough to be calm.
const live = { refreshInterval: 2000, revalidateOnFocus: true };

export type Machine = {
  machine_id: string;
  name: string;
  status: "online" | "offline";
  last_seen_ms?: number;
  live_cpu?: number | null;
  live_mem?: number | null;
  info?: {
    chip?: string;
    model?: string;
    memory_gb?: number;
    cpu_count?: number;
    macos_version?: string;
    arch?: string;
  } | null;
};

export type Sandbox = {
  sandbox_id: string;
  machine_id: string;
  image: string | null;
  status: string;
  created_ms: number;
  last_used_ms: number;
  exec_count: number;
  live?: boolean;
  running?: number;
};

export type Volume = {
  name: string;
  machine_id: string;
  size_bytes: number;
  file_count: number;
  updated_ms: number;
};

export type SecretMeta = { name: string; keys: string[]; created_ms: number };

export type Job = {
  request_id: string;
  machine_id: string;
  command: string;
  state: string;
  exit_code: number | null;
  duration_ms: number | null;
  created_ms: number;
};

export type Metrics = {
  machines_total: number;
  machines_online: number;
  sandboxes_active: number;
  sandboxes_live: number;
  sandboxes_total: number;
  volumes: number;
  volumes_bytes: number;
  secrets: number;
  jobs_total: number;
  jobs_running: number;
  jobs_succeeded: number;
  jobs_failed: number;
};

export const useMetrics = () =>
  useSWR<Metrics>("/v1/metrics", fetcher, live);

export const useMachines = () =>
  useSWR<{ machines: Machine[] }>("/v1/machines", fetcher, live);

export const useSandboxes = () =>
  useSWR<{ sandboxes: Sandbox[] }>("/v1/sandboxes", fetcher, live);

export const useSandbox = (id: string) =>
  useSWR<{ sandbox: Sandbox; jobs: Job[] }>(`/v1/sandboxes/${id}`, fetcher, live);

export const useVolumes = () =>
  useSWR<{ volumes: Volume[] }>("/v1/volumes", fetcher, live);

export const useSecrets = () =>
  useSWR<{ secrets: SecretMeta[] }>("/v1/secrets", fetcher, live);

export const useJobs = () =>
  useSWR<{ jobs: Job[] }>("/v1/jobs", fetcher, live);

export type Timeseries = {
  now: number;
  minutes: number;
  bucket_ms: number;
  runs: { t: number; count: number }[];
  sandboxes: { t: number; count: number }[];
  cpu_mem: { t: number; cpu: number; mem: number }[];
  runs_total: number;
  live_cpu: number;
  live_mem: number;
};

export const useTimeseries = (minutes = 15, buckets = 90, machineId?: string) =>
  useSWR<Timeseries>(
    `/v1/metrics/timeseries?minutes=${minutes}&buckets=${buckets}${machineId ? `&machine_id=${machineId}` : ""}`,
    fetcher,
    live
  );

export type Port = { port: number; name: string; created_ms: number; path: string; url: string };
export const usePorts = (id: string) =>
  useSWR<{ ports: Port[] }>(`/v1/sandboxes/${id}/ports`, fetcher, live);

export async function exposePort(id: string, port: number, name: string) {
  const res = await fetch(`${API}/v1/sandboxes/${id}/ports`, authInit({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ port, name }),
  }));
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to expose");
  return res.json();
}

export async function unexposePort(id: string, port: number) {
  const res = await fetch(`${API}/v1/sandboxes/${id}/ports/${port}`, authInit({ method: "DELETE" }));
  if (!res.ok) throw new Error("failed");
  return res.json();
}

export type HostInfo = { public_url: string; token: string; connect: string; hosted: boolean };
export const useHost = () =>
  useSWR<HostInfo>("/v1/host", fetcher, { refreshInterval: 0 });

export const useHealth = () =>
  useSWR<{ ok: boolean; agents_online: string[] }>("/healthz", fetcher, {
    refreshInterval: 3000,
  });

export type JobOutput = {
  request_id: string;
  state: string;
  exit_code: number | null;
  command: string;
  output: [string, string][]; // [stream, text]
};

export async function fetchJobOutput(id: string): Promise<JobOutput> {
  const res = await fetch(`${API}/v1/jobs/${id}/output`, authInit());
  if (!res.ok) throw new Error("no output");
  return res.json();
}

export type FileEntry = { name: string; dir: boolean; size: number; mtime_ms: number };
export type FileContent = {
  path: string;
  size: number;
  binary: boolean;
  truncated: boolean;
  content?: string;
  mtime_ms?: number;
};

export async function fetchFiles(
  sandboxId: string,
  path: string
): Promise<{ path: string; entries: FileEntry[] }> {
  const res = await fetch(`${API}/v1/sandboxes/${sandboxId}/files?path=${encodeURIComponent(path)}`, authInit());
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to list");
  return res.json();
}

export async function fetchFile(sandboxId: string, path: string): Promise<FileContent> {
  const res = await fetch(`${API}/v1/sandboxes/${sandboxId}/file?path=${encodeURIComponent(path)}`, authInit());
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to read");
  return res.json();
}

export async function fetchVolumeFiles(
  name: string,
  machineId: string,
  path: string
): Promise<{ path: string; entries: FileEntry[] }> {
  const res = await fetch(
    `${API}/v1/volumes/${encodeURIComponent(name)}/files?machine_id=${machineId}&path=${encodeURIComponent(path)}`, authInit());
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to list");
  return res.json();
}

export async function fetchVolumeFile(name: string, machineId: string, path: string): Promise<FileContent> {
  const res = await fetch(
    `${API}/v1/volumes/${encodeURIComponent(name)}/file?machine_id=${machineId}&path=${encodeURIComponent(path)}`, authInit());
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to read");
  return res.json();
}

export async function createSandbox(
  machineId: string,
  body: { image?: string; command?: string; keep_alive?: boolean; inherit_home?: boolean }
): Promise<{ sandbox_id: string; machine_id: string; request_id: string | null }> {
  const res = await fetch(`${API}/v1/machines/${machineId}/sandboxes`, authInit({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to create");
  return res.json();
}

export async function runInSandbox(
  machineId: string,
  body: { command: string; sandbox_id: string; keep_alive?: boolean; inherit_home?: boolean }
): Promise<{ request_id: string }> {
  const res = await fetch(`${API}/v1/machines/${machineId}/exec`, authInit({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to run");
  return res.json();
}

export type ApiKey = { label: string; masked: string };
export const useKeys = () => useSWR<{ keys: ApiKey[] }>("/v1/keys", fetcher, { refreshInterval: 0 });

export async function createKey(label: string): Promise<{ key: string; label: string }> {
  const res = await fetch(`${API}/v1/keys`, authInit({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  }));
  if (!res.ok) throw new Error("failed to create key");
  return res.json();
}

export async function revokeKey(prefix: string) {
  const res = await fetch(`${API}/v1/keys/${encodeURIComponent(prefix)}`, authInit({ method: "DELETE" }));
  if (!res.ok) throw new Error("failed to revoke");
  return res.json();
}

export async function stopSandbox(sandboxId: string) {
  const res = await fetch(`${API}/v1/sandboxes/${sandboxId}/stop`, authInit({ method: "POST" }));
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to stop");
  return res.json();
}

export async function terminateSandbox(sandboxId: string) {
  const res = await fetch(`${API}/v1/sandboxes/${sandboxId}`, authInit({ method: "DELETE" }));
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "failed to terminate");
  return res.json();
}

export async function createSecret(name: string, values: Record<string, string>) {
  const res = await fetch(`${API}/v1/secrets`, authInit({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, values }),
  }));
  if (!res.ok) throw new Error((await res.json()).detail || "failed");
  return res.json();
}

export async function deleteSecret(name: string) {
  const res = await fetch(`${API}/v1/secrets/${encodeURIComponent(name)}`, authInit({ method: "DELETE" }));
  if (!res.ok) throw new Error("failed to delete");
  return res.json();
}
