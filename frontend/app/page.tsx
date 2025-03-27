"use client";

import Link from "next/link";
import { Button, Card } from "@/components/ui/primitives";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <header className="fade-up">
        <h1 className="font-display text-3xl font-semibold text-ink">Chat</h1>
        <p className="mt-1 text-ink-soft">
          Ask questions across your corpora — compare a personal record against
          published guidelines, with provenance shown for every retrieved
          passage.
        </p>
      </header>

      <Card className="p-8 text-center">
        <div className="font-display text-xl text-ink">
          Coming in a later step
        </div>
        <p className="mx-auto mt-2 max-w-md text-sm text-ink-soft">
          The chat interface — model selection, thinking-depth tiers, the cost
          panel, and the provenance-rich thinking transparency view — is built
          once inference is wired up. The retrieval pipeline behind it is
          already working.
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <Link href="/knowledge-base">
            <Button>Go to Knowledge Base</Button>
          </Link>
          <Link href="/rag-inspector">
            <Button variant="outline">Open RAG Inspector</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
