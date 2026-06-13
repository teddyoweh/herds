import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { TopNav } from "@/components/TopNav";
import { CommandPalette } from "@/components/CommandPalette";
import { ToastProvider } from "@/components/Toast";
import { NavProgress } from "@/components/NavProgress";
import { OfflineBanner } from "@/components/OfflineBanner";
import { TokenGate } from "@/components/TokenGate";

export const metadata: Metadata = {
  title: "Herds",
  description: "Every Mac becomes an API.",
};

export const viewport: Viewport = {
  themeColor: "#09090b",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen">
        <ToastProvider>
          <TokenGate>
            <NavProgress />
            <TopNav />
            <OfflineBanner />
            <main className="mx-auto w-full max-w-[1240px] px-4 py-8 sm:px-8 sm:py-10">{children}</main>
            <CommandPalette />
          </TokenGate>
        </ToastProvider>
      </body>
    </html>
  );
}
