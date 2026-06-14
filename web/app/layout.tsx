import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { ToastProvider } from "@/components/Toast";
import { AppChrome } from "@/components/AppChrome";

export const metadata: Metadata = {
  title: "Herds — Give your agents real Macs",
  description: "Connect any Mac and turn it into a programmable cloud runtime. Modal, for Macs.",
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
          <AppChrome>{children}</AppChrome>
        </ToastProvider>
      </body>
    </html>
  );
}
