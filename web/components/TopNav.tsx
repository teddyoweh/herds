"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useHealth, useMetrics } from "@/lib/api";
import { LiveDot } from "./ui";

const TABS = [
  { href: "/", label: "Overview" },
  { href: "/sandboxes", label: "Sandboxes" },
  { href: "/machines", label: "Machines" },
  { href: "/volumes", label: "Volumes" },
  { href: "/secrets", label: "Secrets" },
  { href: "/runs", label: "Runs" },
  { href: "/settings", label: "Settings" },
] as const;

export function TopNav() {
  const pathname = usePathname();
  const { data: health, error } = useHealth();
  const { data: m } = useMetrics();
  const connected = !!health?.ok && !error;
  const online = m?.machines_online ?? health?.agents_online.length ?? 0;

  return (
    <header className="sticky top-0 z-30 bg-ink-950/80 backdrop-blur-xl">
      {/* Row 1 — context + account */}
      <div className="mx-auto flex h-[60px] max-w-[1240px] items-center justify-between px-8">
        <div className="flex items-center gap-2.5">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-[22px] w-[22px] place-items-center rounded-md bg-gradient-to-br from-signal-400 to-signal-600 text-[11px]">
              🍎
            </span>
            <span className="text-[15px] font-semibold tracking-tightest text-white">Darwin</span>
          </Link>
          <Slash />
          <button className="group flex items-center gap-2 rounded-lg py-1 pl-1.5 pr-2 transition-colors hover:bg-white/[0.05]">
            <span className="grid h-[18px] w-[18px] place-items-center rounded bg-gradient-to-br from-violet-400 to-indigo-500 text-[10px] font-bold text-white">S</span>
            <span className="text-[13px] font-medium text-zinc-200">spawnlabs-team</span>
            <Chevron />
          </button>
          <Slash />
          <span className="rounded-md bg-white/[0.05] px-2 py-[3px] font-mono text-[11px] text-zinc-400">main</span>
        </div>

        <div className="flex items-center gap-3 text-[12px]">
          <button
            onClick={() => window.dispatchEvent(new Event("darwin-open-cmdk"))}
            className="flex w-56 items-center justify-between rounded-lg bg-white/[0.04] py-1.5 pl-3 pr-2 text-zinc-500 transition-colors hover:bg-white/[0.06] hover:text-zinc-400"
          >
            <span className="flex items-center gap-2">
              <SearchGlyph />
              Search…
            </span>
            <kbd className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">⌘K</kbd>
          </button>

          <div className="flex items-center gap-2.5 rounded-lg bg-white/[0.04] px-3 py-1.5">
            <LiveDot on={connected} size={6} />
            <span className={connected ? "text-zinc-300" : "text-zinc-600"}>
              {connected ? "Live" : "Offline"}
            </span>
            <span className="h-3 w-px bg-white/10" />
            <span className="text-zinc-500">
              <span className="tnum text-zinc-300">{online}</span> online
            </span>
          </div>

          <span className="grid h-[30px] w-[30px] place-items-center rounded-full bg-gradient-to-br from-zinc-200 to-zinc-400 text-[12px] font-semibold text-ink-950 ring-1 ring-white/10">
            T
          </span>
        </div>
      </div>

      {/* Row 2 — tabs as pills */}
      <nav className="mx-auto flex h-12 max-w-[1240px] items-center gap-1 overflow-x-auto px-4 sm:px-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {TABS.map((t) => {
          const active = t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`flex h-8 items-center rounded-lg px-3 text-[13px] transition-colors ${
                active
                  ? "bg-white/[0.07] font-medium text-white"
                  : "text-zinc-500 hover:bg-white/[0.03] hover:text-zinc-300"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>

      {/* hairline under the whole nav */}
      <div className="h-px w-full bg-white/[0.05]" />
    </header>
  );
}

function Slash() {
  return <span className="select-none text-[14px] font-light text-zinc-700">/</span>;
}

function Chevron() {
  return (
    <svg width="9" height="9" viewBox="0 0 12 12" fill="none" className="text-zinc-600">
      <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" className="text-zinc-600">
      <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.3" />
      <path d="M9 9L12 12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
