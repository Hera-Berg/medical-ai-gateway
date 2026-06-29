/**
 * Custom 404 — replaces the bare Next.js default so stray URLs land somewhere
 * that matches the app's clinical/editorial design.
 */
import Link from "next/link";

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "60vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "3rem 1.5rem",
      }}
    >
      <p
        style={{
          fontFamily: "var(--font-serif, Fraunces), serif",
          fontSize: "4rem",
          lineHeight: 1,
          color: "var(--brand)",
          margin: 0,
        }}
      >
        404
      </p>
      <h1
        style={{
          fontFamily: "var(--font-serif, Fraunces), serif",
          fontSize: "1.5rem",
          color: "var(--ink)",
          marginTop: "1rem",
          marginBottom: ".5rem",
        }}
      >
        Page not found
      </h1>
      <p style={{ color: "var(--ink-soft)", maxWidth: "28rem", marginBottom: "1.75rem" }}>
        That page doesn&apos;t exist. It may have moved, or the link was mistyped.
      </p>
      <Link
        href="/"
        style={{
          display: "inline-block",
          background: "var(--brand)",
          color: "#fff",
          padding: ".6rem 1.1rem",
          borderRadius: "var(--radius-sm)",
          textDecoration: "none",
          fontWeight: 600,
        }}
      >
        Back to Chat
      </Link>
    </div>
  );
}
