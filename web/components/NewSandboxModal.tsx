"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useToast } from "./Toast";
import { createSandbox } from "@/lib/api";

const IMAGES = ["host", "xcode:26", "node:22", "python:3.13"];

export function NewSandboxModal({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [image, setImage] = useState("host");
  const [command, setCommand] = useState("");
  const [keepAlive, setKeepAlive] = useState(false);
  const [inheritHome, setInheritHome] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    setBusy(true);
    try {
      const r = await createSandbox("default", {
        image: image === "host" ? undefined : image,
        command: command.trim() || undefined,
        keep_alive: keepAlive,
        inherit_home: inheritHome,
      });
      toast("Sandbox created", "success");
      router.push(`/sandbox?id=${r.sandbox_id}`);
    } catch (e: any) {
      setErr(e.message || "Failed to create sandbox");
      setBusy(false);
    }
  };

  const input =
    "w-full rounded-lg bg-black/30 px-3 py-2 text-[13px] text-zinc-100 outline-none ring-1 ring-white/[0.06] transition focus:ring-signal-500/50 placeholder:text-zinc-700";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-sm"
    >
      <motion.div
        initial={{ scale: 0.97, y: 6 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.97, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl bg-ink-850 p-6 shadow-e2"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-semibold text-white">New sandbox</h3>
          <button onClick={onClose} className="text-[12px] text-zinc-600 hover:text-zinc-300">Esc</button>
        </div>

        <div className="label mt-6 mb-2">Image</div>
        <div className="flex flex-wrap gap-1.5">
          {IMAGES.map((img) => (
            <button
              key={img}
              onClick={() => setImage(img)}
              className={`rounded-lg px-2.5 py-1 font-mono text-[12px] transition-colors ${
                image === img ? "bg-white/[0.08] text-white" : "bg-white/[0.03] text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {img}
            </button>
          ))}
        </div>

        <div className="label mt-5 mb-1.5">Command <span className="normal-case tracking-normal text-zinc-700">— optional</span></div>
        <textarea
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="claude -p 'review this repo'   ·   npm test   ·   leave empty for an idle sandbox"
          rows={2}
          className={`${input} resize-none font-mono text-[12px]`}
        />

        <div className="mt-5 space-y-2.5">
          <Toggle on={keepAlive} set={setKeepAlive} label="Keep alive" hint="Restart the process if it exits (a service)" />
          <Toggle on={inheritHome} set={setInheritHome} label="Run as me" hint="Use your real HOME, tools & logins (claude, git, gh)" />
        </div>

        {err && <div className="mt-3 text-[12px] text-rose-400">{err}</div>}

        <div className="mt-7 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-3.5 py-2 text-[12px] text-zinc-500 hover:text-zinc-200">Cancel</button>
          <button
            onClick={submit}
            disabled={busy}
            className="rounded-lg bg-signal-500 px-3.5 py-2 text-[12px] font-medium text-ink-950 transition hover:bg-signal-400 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create sandbox"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function Toggle({ on, set, label, hint }: { on: boolean; set: (v: boolean) => void; label: string; hint: string }) {
  return (
    <button onClick={() => set(!on)} className="flex w-full items-center gap-3 text-left">
      <span className={`relative h-[18px] w-[30px] shrink-0 rounded-full transition-colors ${on ? "bg-signal-500" : "bg-white/[0.1]"}`}>
        <span className={`absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white transition-all ${on ? "left-[14px]" : "left-[2px]"}`} />
      </span>
      <span className="min-w-0">
        <span className="text-[13px] text-zinc-200">{label}</span>
        <span className="ml-2 text-[11px] text-zinc-600">{hint}</span>
      </span>
    </button>
  );
}
