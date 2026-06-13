"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { useMachines, useSandboxes, useVolumes, useSecrets } from "@/lib/api";
import { bytes } from "@/lib/format";

type Type = "page" | "action" | "sandbox" | "machine" | "volume" | "secret";
type Cmd = { id: string; label: string; sub?: string; run: () => void; keywords?: string; type: Type; live?: boolean };
type Group = { key: string; items: Cmd[] };

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: md } = useMachines();
  const { data: sd } = useSandboxes();
  const { data: vd } = useVolumes();
  const { data: secd } = useSecrets();

  const groups = useMemo<Group[]>(() => {
    const go = (href: string) => () => { router.push(href); setOpen(false); };
    return [
      { key: "Navigation", items: [
        { id: "n-ov", label: "Overview", run: go("/"), type: "page", keywords: "home dashboard metrics" },
        { id: "n-sb", label: "Sandboxes", run: go("/sandboxes"), type: "page", keywords: "boxes" },
        { id: "n-mc", label: "Machines", run: go("/machines"), type: "page", keywords: "macs" },
        { id: "n-vol", label: "Volumes", run: go("/volumes"), type: "page", keywords: "storage files" },
        { id: "n-sec", label: "Secrets", run: go("/secrets"), type: "page", keywords: "keys env" },
        { id: "n-runs", label: "Runs", run: go("/runs"), type: "page", keywords: "jobs logs" },
        { id: "n-set", label: "Settings", run: go("/settings"), type: "page", keywords: "api keys" },
      ]},
      { key: "Actions", items: [
        { id: "a-sb", label: "New sandbox", sub: "Create & spawn", run: go("/sandboxes?new=1"), type: "action", keywords: "create spawn agent run" },
        { id: "a-sec", label: "New secret", sub: "Add key/value", run: go("/secrets?new=1"), type: "action", keywords: "create add key" },
      ]},
      { key: "Sandboxes", items: (sd?.sandboxes ?? []).map((s) => ({
        id: "s-" + s.sandbox_id, label: s.sandbox_id, sub: s.image ?? "host", live: s.live,
        run: go(`/sandbox?id=${s.sandbox_id}`), type: "sandbox" as Type, keywords: s.image ?? "",
      }))},
      { key: "Machines", items: (md?.machines ?? []).map((m) => ({
        id: "m-" + m.machine_id, label: m.name, sub: m.machine_id, live: m.status === "online",
        run: go(`/machine?id=${m.machine_id}`), type: "machine" as Type, keywords: m.machine_id,
      }))},
      { key: "Volumes", items: (vd?.volumes ?? []).map((v) => ({
        id: "v-" + v.name, label: v.name, sub: bytes(v.size_bytes),
        run: go(`/volume?name=${encodeURIComponent(v.name)}&machine=${v.machine_id}`), type: "volume" as Type, keywords: "storage",
      }))},
      { key: "Secrets", items: (secd?.secrets ?? []).map((s) => ({
        id: "k-" + s.name, label: s.name, sub: `${s.keys.length} keys`,
        run: go("/secrets"), type: "secret" as Type, keywords: s.keys.join(" "),
      }))},
    ];
  }, [router, md, sd, vd, secd]);

  // Filter + cap each group; flatten for keyboard nav.
  const visible = useMemo<Group[]>(() => {
    const s = q.trim().toLowerCase();
    return groups
      .map((g) => {
        let items = g.items;
        if (s) items = items.filter((c) => (c.label + " " + (c.sub ?? "") + " " + (c.keywords ?? "")).toLowerCase().includes(s));
        else if (["Sandboxes", "Machines", "Volumes", "Secrets"].includes(g.key)) items = items.slice(0, 5);
        return { key: g.key, items };
      })
      .filter((g) => g.items.length > 0);
  }, [groups, q]);

  const flat = useMemo(() => visible.flatMap((g) => g.items), [visible]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((v) => !v); }
      else if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    const c = new URLSearchParams(window.location.search).get("cmdk");
    if (c) { setOpen(true); if (c !== "1") setTimeout(() => setQ(c), 30); }
    window.addEventListener("keydown", onKey);
    window.addEventListener("herds-open-cmdk", onOpen as EventListener);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("herds-open-cmdk", onOpen as EventListener); };
  }, []);

  useEffect(() => { if (open) { setQ(""); setCursor(0); setTimeout(() => inputRef.current?.focus(), 10); } }, [open]);
  useEffect(() => setCursor(0), [q]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${cursor}"]`)?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, flat.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); flat[cursor]?.run(); }
  };

  let idx = -1;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-[70] flex items-start justify-center bg-black/60 px-4 pt-[14vh] backdrop-blur-md"
        >
          <motion.div
            initial={{ scale: 0.985, y: -8 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.985, opacity: 0 }}
            transition={{ type: "spring", stiffness: 480, damping: 36 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[600px] overflow-hidden rounded-2xl bg-ink-850/95 shadow-e2 ring-1 ring-white/[0.06] backdrop-blur-2xl"
          >
            <div className="flex items-center gap-3 px-5 py-4">
              <Glyph type="search" />
              <input
                ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKeyDown}
                placeholder="Search sandboxes, machines, volumes, actions…"
                className="flex-1 bg-transparent text-[14px] text-zinc-100 outline-none placeholder:text-zinc-600"
              />
              <kbd className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[10px] text-zinc-600">esc</kbd>
            </div>
            <div className="h-px bg-white/[0.06]" />

            <div ref={listRef} className="max-h-[52vh] overflow-y-auto py-2">
              {flat.length === 0 && (
                <div className="px-5 py-10 text-center text-[13px] text-zinc-600">No results for “{q}”</div>
              )}
              {visible.map((g) => (
                <div key={g.key} className="mb-1">
                  <div className="px-5 pb-1 pt-2 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-600">{g.key}</div>
                  {g.items.map((c) => {
                    idx++;
                    const i = idx;
                    return (
                      <button
                        key={c.id} data-idx={i}
                        onMouseMove={() => setCursor(i)}
                        onClick={c.run}
                        className={`flex w-full items-center gap-3 px-5 py-2 text-left ${i === cursor ? "bg-white/[0.07]" : ""}`}
                      >
                        <span className="relative grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/[0.05]">
                          <Glyph type={c.type} />
                          {c.live && <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-signal-400 ring-2 ring-ink-850" />}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className={`block truncate text-[13px] ${c.type === "sandbox" || c.type === "machine" ? "font-mono text-[12px]" : ""} ${i === cursor ? "text-white" : "text-zinc-200"}`}>
                            {c.label}
                          </span>
                          {c.sub && <span className="block truncate text-[11px] text-zinc-600">{c.sub}</span>}
                        </span>
                        {i === cursor && <span className="shrink-0 text-[11px] text-zinc-500">↵</span>}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>

            <div className="flex items-center gap-4 border-t border-white/[0.06] px-5 py-2.5 text-[11px] text-zinc-600">
              <span><kbd className="font-mono text-zinc-500">↑↓</kbd> navigate</span>
              <span><kbd className="font-mono text-zinc-500">↵</kbd> open</span>
              <span className="ml-auto tnum">{flat.length} results</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Glyph({ type }: { type: Type | "search" }) {
  const cn = "text-zinc-500";
  const sw = 1.4;
  switch (type) {
    case "search":
      return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-zinc-500"><circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth={sw} /><path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" /></svg>;
    case "sandbox":
      return <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className={cn}><path d="M8 2L14 5.2V10.8L8 14L2 10.8V5.2L8 2Z" stroke="currentColor" strokeWidth={sw} strokeLinejoin="round" /><path d="M2 5.2L8 8.4L14 5.2M8 8.4V14" stroke="currentColor" strokeWidth={sw} strokeLinejoin="round" /></svg>;
    case "machine":
      return <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className={cn}><rect x="2" y="3" width="12" height="8" rx="1.2" stroke="currentColor" strokeWidth={sw} /><path d="M6 14h4" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" /></svg>;
    case "volume":
      return <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className={cn}><ellipse cx="8" cy="4" rx="5" ry="2" stroke="currentColor" strokeWidth={sw} /><path d="M3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4" stroke="currentColor" strokeWidth={sw} /></svg>;
    case "secret":
      return <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className={cn}><circle cx="6" cy="6" r="3" stroke="currentColor" strokeWidth={sw} /><path d="M8.5 8.5L13 13M11 11l1.5-1.5" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" /></svg>;
    case "action":
      return <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className={cn}><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" /></svg>;
    default: // page
      return <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className={cn}><path d="M5 3l5 5-5 5" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" /></svg>;
  }
}
