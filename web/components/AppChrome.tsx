"use client";

import { usePathname } from "next/navigation";
import { TopNav } from "./TopNav";
import { CommandPalette } from "./CommandPalette";
import { NavProgress } from "./NavProgress";
import { OfflineBanner } from "./OfflineBanner";
import { TokenGate } from "./TokenGate";

const PLATFORM = process.env.NEXT_PUBLIC_HERDS_MODE === "platform";
// Marketing + auth pages render bare (their own layout, no dashboard chrome).
const BARE = new Set(["/login", "/signup", "/welcome", "/skill", "/docs", "/dashboard"]);

export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Normalize static-export paths (/docs.html, trailing slash) before matching.
  const norm = pathname.replace(/\.html$/, "").replace(/\/+$/, "") || "/";
  const bare = BARE.has(norm) || (PLATFORM && norm === "/");
  if (bare) return <>{children}</>;
  return (
    <TokenGate>
      <NavProgress />
      <TopNav />
      <OfflineBanner />
      <main className="mx-auto w-full max-w-[1240px] px-4 py-8 sm:px-8 sm:py-10">{children}</main>
      <CommandPalette />
    </TokenGate>
  );
}
