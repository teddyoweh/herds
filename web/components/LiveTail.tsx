"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";
import { LiveDot } from "./ui";
import { uptime } from "@/lib/format";

/** An inline, always-on live log tail for a running process. */
export function LiveTail({ requestId, startedMs }: { requestId: string; startedMs?: number }) {
  const [lines, setLines] = useState<{ stream: string; text: string }[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);
  const restarts = lines.filter((l) => l.text.includes("restarting (#")).length;

  useEffect(() => {
    const ws = new WebSocket(wsUrl(`/v1/jobs/${requestId}/logs`));
    setLines([]);
    ws.onmessage = (e) => {
      const f = JSON.parse(e.data);
      if (f.type === "stdout" || f.type === "stderr")
        setLines((p) => [...p.slice(-500), { stream: f.type, text: f.data.text }]);
    };
    return () => ws.close();
  }, [requestId]);

  useEffect(() => {
    boxRef.current?.scrollTo(0, boxRef.current.scrollHeight);
  }, [lines]);

  return (
    <div className="surface overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-3 text-[12px]">
        <span className="flex items-center gap-2">
          <LiveDot size={6} />
          <span className="text-signal-400">Live output</span>
        </span>
        {startedMs && <span className="text-[11px] text-zinc-600">up {uptime(startedMs)}</span>}
        {restarts > 0 && (
          <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
            {restarts} restart{restarts > 1 ? "s" : ""}
          </span>
        )}
        <span className="ml-auto tnum text-[11px] text-zinc-600">{lines.length} lines</span>
      </div>
      <div ref={boxRef} className="max-h-[280px] overflow-auto bg-black/25 px-5 py-3 font-mono text-[12px] leading-[1.7]">
        {lines.length === 0 && <div className="text-zinc-700">waiting for output…</div>}
        {lines.map((l, i) => (
          <div key={i} className={l.stream === "stderr" ? "text-amber-300/80" : "text-zinc-300"}>
            {l.text.replace(/\n$/, "") || " "}
          </div>
        ))}
      </div>
    </div>
  );
}
