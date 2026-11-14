import type { Metadata } from "next";
import { EB_Garamond, JetBrains_Mono } from "next/font/google";
import { Header } from "@/components/Header";
import "./globals.css";

// Truss brand type: EB Garamond everywhere, a monospace only for code
const serif = EB_Garamond({
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["normal", "italic"],
  variable: "--font-serif",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "SoldierPhysio · Evaluating frontier models on a field medic's heat-casualty calls",
  description:
    "14 frontier models make a field medic's heat-casualty calls on real heat-chamber data, graded against measured core temperature.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${mono.variable}`}>
      <head>
        <noscript>
          <style>{`.plot *{opacity:1!important;transform:none!important;clip-path:none!important;stroke-dashoffset:0!important}`}</style>
        </noscript>
      </head>
      <body>
        <Header />
        <main>{children}</main>
        <footer className="site-footer">
          <div className="wrap">
            <span>SoldierPhysio · micro1 Eval Hackathon · November 2026</span>
            <span>Data: D&apos;Lugos et al. 2025 (CC BY 4.0) · TB MED 507 (2022)</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
