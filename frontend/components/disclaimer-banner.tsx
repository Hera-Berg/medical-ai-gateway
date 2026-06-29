/**
 * Persistent, structural disclaimer. Rendered in the root layout so it appears
 * on every page, above the app shell. Not dismissible — a tool that compares
 * health records to clinical guidelines must keep this framing load-bearing.
 */
export function DisclaimerBanner() {
  return (
    <div className="relative z-20 w-full border-b border-[var(--border)] bg-[var(--warn-soft)] px-6 py-1.5 text-center text-[13px] text-[var(--warn)]">
      <strong className="font-semibold">Demo &amp; educational tool.</strong>{" "}
      Not medical advice. Not a diagnostic device. All personal records shown are
      synthetic.
    </div>
  );
}
