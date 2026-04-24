import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "ARIA — Agentic Resource & Intent Assistant",
  description:
    "Live dashboard for the ARIA agent — voice, environment, reward, and event trace.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-200`}>
        {children}
      </body>
    </html>
  );
}
