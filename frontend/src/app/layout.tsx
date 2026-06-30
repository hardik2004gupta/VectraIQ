import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "VectraIQ", template: "%s | VectraIQ" },
  description:
    "Production-grade AI Knowledge Platform — Kubernetes IT-Operations Copilot with Hybrid RAG, Text2SQL, and Enterprise Security.",
  keywords: ["RAG", "Kubernetes", "AI", "Knowledge Base", "SRE", "Platform Engineering"],
  authors: [{ name: "VectraIQ" }],
  openGraph: {
    title: "VectraIQ",
    description: "AI-powered Kubernetes IT-Operations Copilot",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#080808",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
