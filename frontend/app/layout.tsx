import type { Metadata } from "next";
import { JetBrains_Mono, Geist } from "next/font/google";
import "./globals.css";

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
  weight: ["300", "400", "500", "600", "700"],
});

const geistSans = Geist({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-geist-sans",
});

export const metadata: Metadata = {
  title: "ARIA // Agentic Real-time Intelligent Assistant",
  description:
    "Voice-first personal AI manager — Meta PyTorch OpenEnv Hackathon 2026.",
  metadataBase: new URL("https://aria.local"),
  icons: [{ rel: "icon", url: "/favicon.svg" }],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${jetbrainsMono.variable} ${geistSans.variable}`}
      suppressHydrationWarning
    >
      {/*
        suppressHydrationWarning is on <html> and <body> deliberately:
        browser extensions (ColorZilla, Grammarly, LastPass, dark-mode
        extensions, etc.) inject attributes after the HTML is shipped but
        before React hydrates. This is the one documented Next.js escape
        hatch for those attributes; see
        https://nextjs.org/docs/messages/react-hydration-error
      */}
      <body
        className="min-h-screen bg-bg text-fg"
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
