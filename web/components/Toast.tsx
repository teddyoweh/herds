"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

type Kind = "default" | "success" | "error";
type Item = { id: number; msg: string; kind: Kind };
type ToastFn = (msg: string, kind?: Kind) => void;

const ToastCtx = createContext<ToastFn>(() => {});
export const useToast = () => useContext(ToastCtx);

const ACCENT: Record<Kind, string> = {
  default: "bg-zinc-500",
  success: "bg-signal-400",
  error: "bg-rose-400",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const seq = useRef(0);

  const toast = useCallback<ToastFn>((msg, kind = "default") => {
    const id = ++seq.current;
    setItems((p) => [...p, { id, msg, kind }]);
    setTimeout(() => setItems((p) => p.filter((i) => i.id !== id)), 3200);
  }, []);

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-[320px] flex-col gap-2">
        <AnimatePresence>
          {items.map((i) => (
            <motion.div
              key={i.id}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 16, transition: { duration: 0.15 } }}
              transition={{ type: "spring", stiffness: 420, damping: 32 }}
              className="surface pointer-events-auto flex items-center gap-3 px-4 py-3 shadow-e2"
            >
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${ACCENT[i.kind]}`} />
              <span className="text-[13px] text-zinc-200">{i.msg}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}
