import type { Metadata } from "next";
import "./globals.css";
import { DisclaimerBanner } from "@/components/disclaimer-banner";

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
    <html lang="en">
      <body className="min-h-screen bg-neutral-50 text-neutral-900">
        {/*The disclaimer is STRUCTURAL.*/}
        <DisclaimerBanner />
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
