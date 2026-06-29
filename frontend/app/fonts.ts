// Distinctive type pairing via next/font/google.
//
// NOTE: next/font/google downloads these at BUILD time, so `docker build` needs
// internet (your build machine has it — same as pulling npm/Docker/FastEmbed
// assets). If you ever need fully-offline builds, switch to next/font/local with
// self-hosted woff2 files; the rest of the app doesn't change.
//
// Fraunces: editorial display serif with optical sizing — considered and
// trustworthy, not generic-SaaS. IBM Plex Sans: precise, highly legible body
// face for dense clinical text and data.
import { Fraunces, IBM_Plex_Sans } from "next/font/google";

export const display = Fraunces({
  subsets: ["latin"],
  weight: ["400", "600"],
  display: "swap",
  variable: "--font-display",
});

export const body = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-body",
});
