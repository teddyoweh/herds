"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { StatePill } from "./ui";
import { wsUrl, fetchJobOutput, type Job } from "@/lib/api";

const RUNNING = ["running", "dispatched", "queued"];

/** Drawer that shows a run's logs: stored output for finished runs, live tail
 *  (WebSocket) for in-flight ones. */
export function LogDrawer({ job, onClose }: { job: Job; onClose: () => void }) {
  const [lines, setLines] = useState<{ stream: string; text: string }[]>([]);
  const [status, setStatus] = useState("loading…");
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;

    const liveTail = () => {
      ws = new WebSocket(wsUrl(`/v1/jobs/${job.request_id}/logs`));
      setLines([]);
      ws.onopen = () => setStatus("streaming");
      ws.onmessage = (e) => {
        const f = JSON.parse(e.data);
        if (f.type === "stdout" || f.type === "stderr")
          setLines((p) => [...p, { stream: f.type, text: f.data.text }]);
        else if (f.type === "exit") setStatus(`exited ${f.data.exit_code}`);
      };
      ws.onerror = () => setStatus("stream unavailable");
    };

    (async () => {
      try {
        const d = await fetchJobOutput(job.request_id);
        if (cancelled) return;
        if (!RUNNING.includes(d.state)) {
          setLines(d.output.map(([stream, text]) => ({ stream, text })));
          setStatus(d.output.length ? `exited ${d.exit_code}` : `exited ${d.exit_code} · no output`);
          return;
        }
      } catch {
        /* fall through to live tail */
      }
      if (!cancelled) liveTail();
    })();

    return () => {
      cancelled = true;
      ws?.close();
    };
  }, [job.request_id]);

  useEffect(() => {
    boxRef.current?.scrollTo(0, boxRef.current.scrollHeight);
  }, [lines]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm"
    >
      <motion.div
        initial={{ x: 48 }}
        animate={{ x: 0 }}
        exit={{ x: 48, opacity: 0 }}
        transition={{ type: "spring", stiffness: 320, damping: 34 }}
        onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-2xl flex-col bg-ink-900"
      >
        <div className="flex items-center justify-between px-6 py-4">
          <div>
            <div className="font-mono text-[12px] text-zinc-300">{job.request_id}</div>
            <div className="mt-0.5 text-[11px] text-zinc-700">{job.machine_id}</div>
          </div>
          <div className="flex items-center gap-4">
            <StatePill state={job.state} />
            <button onClick={onClose} className="text-[12px] text-zinc-600 hover:text-zinc-200">Esc</button>
          </div>
        </div>

        <div className="px-6 pb-3">
          <code className="font-mono text-[12px] text-zinc-500">$ {job.command}</code>
        </div>

        <div ref={boxRef} className="flex-1 overflow-auto bg-black/25 px-6 py-4 font-mono text-[12px] leading-[1.7]">
          {lines.length === 0 && <div className="text-zinc-700">— {status} —</div>}
          {lines.map((l, i) => (
            <div key={i} className={l.stream === "stderr" ? "text-amber-300/80" : "text-zinc-300"}>
              {l.text.replace(/\n$/, "") || " "}
            </div>
          ))}
        </div>

        <div className="px-6 py-2.5 text-[11px] text-zinc-700">{status} · {lines.length} lines</div>
      </motion.div>
    </motion.div>
  );
}
