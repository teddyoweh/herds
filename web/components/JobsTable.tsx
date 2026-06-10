"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { StatePill } from "./ui";
import { LogDrawer } from "./LogDrawer";
import { type Job } from "@/lib/api";
import { ago, dur } from "@/lib/format";

/** Flat log table on the canvas. Click or ↑↓+↵ to open a row's logs. */
export function JobsTable({ jobs, showMachine = true }: { jobs: Job[]; showMachine?: boolean }) {
  const [selected, setSelected] = useState<Job | null>(null);
  const [cursor, setCursor] = useState(-1);
  const rowsRef = useRef<HTMLDivElement>(null);
  const cols = showMachine
    ? "grid grid-cols-[96px_1fr_140px_72px_72px] gap-4"
    : "grid grid-cols-[96px_1fr_72px_72px] gap-4";

  // Keyboard nav — only when not typing and no drawer open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (selected) return;
      const el = document.activeElement as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      if (e.key === "ArrowDown" || e.key === "j") {
        e.preventDefault();
        setCursor((c) => Math.min(c + 1, jobs.length - 1));
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault();
        setCursor((c) => Math.max(c - 1, 0));
      } else if (e.key === "Enter" && cursor >= 0 && jobs[cursor]) {
        e.preventDefault();
        setSelected(jobs[cursor]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [jobs, cursor, selected]);

  useEffect(() => {
    if (cursor >= 0)
      rowsRef.current?.children[cursor]?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  return (
    <div>
      <div className={`${cols} px-3 pb-2.5`}>
        <span className="label">State</span>
        <span className="label">Command</span>
        {showMachine && <span className="label">Machine</span>}
        <span className="label text-right">Time</span>
        <span className="label text-right">When</span>
      </div>
      <div ref={rowsRef} className="hairline">
        {jobs.map((j, i) => (
          <button
            key={j.request_id}
            onClick={() => setSelected(j)}
            onMouseMove={() => setCursor(i)}
            className={`${cols} row w-full items-center rounded-md px-3 py-2.5 text-left ${
              i === cursor ? "bg-white/[0.05]" : ""
            }`}
          >
            <StatePill state={j.state} />
            <code className="truncate font-mono text-[12px] text-zinc-400">{j.command || "—"}</code>
            {showMachine && (
              <span className="truncate font-mono text-[11px] text-zinc-700">{j.machine_id}</span>
            )}
            <span className="tnum text-right font-mono text-[11px] text-zinc-600">{dur(j.duration_ms)}</span>
            <span className="text-right text-[12px] text-zinc-600">{ago(j.created_ms)}</span>
          </button>
        ))}
      </div>

      <AnimatePresence>
        {selected && <LogDrawer job={selected} onClose={() => setSelected(null)} />}
      </AnimatePresence>
    </div>
  );
}
