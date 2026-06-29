import type { Metadata } from "next";
import "./globals.css";
import { display, body } from "./fonts";
import { DisclaimerBanner } from "@/components/disclaimer-banner";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "Medical AI Gateway",
  description:
    "Cost-transparent, data-sovereign, domain-specialised RAG. Demo & educational tool — not medical advice.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="min-h-screen font-body">
        {/*
          Disclaimer is STRUCTURAL: rendered in the root layout, present on every
          page, above the shell. The shell then frames all page content.
        */}
        <DisclaimerBanner />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
