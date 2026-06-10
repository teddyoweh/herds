"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

/** A thin top loading bar: creeps on link click, completes on route change. */
export function NavProgress() {
  const pathname = usePathname();
  const [state, setState] = useState<"idle" | "loading" | "done">("idle");

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement)?.closest?.("a");
      if (
        a &&
        a.getAttribute("href")?.startsWith("/") &&
        new URL(a.href).pathname !== window.location.pathname
      ) {
        setState("loading");
      }
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  useEffect(() => {
    setState("done");
    const t = setTimeout(() => setState("idle"), 280);
    return () => clearTimeout(t);
  }, [pathname]);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[80] h-[2px]">
      <div
        className={
          "h-full bg-signal-400 shadow-[0_0_8px_rgba(52,211,158,0.6)] " +
          (state === "loading"
            ? "w-[88%] opacity-100 transition-[width] duration-[8000ms] ease-out"
            : state === "done"
            ? "w-full opacity-0 transition-all duration-200"
            : "w-0 opacity-0")
        }
      />
    </div>
  );
}
