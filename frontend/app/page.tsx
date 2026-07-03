"use client";

/**
 * Chat — the home page. Ask across your corpora, pick model + thinking depth,
 * see the grounded answer with a collapsible provenance-rich thinking panel and
 * a live cost panel (this query + cumulative session spend).
 *
 * Cost shown is time-based (RunPod per-second billing). In mock mode the answer
 * is simulated; retrieval, provenance, trace, and cost math are all real.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type QueryModelsResponse,
  type QueryResponse,
  type Collection,
} from "@/lib/api";
import { Button, Card, Spinner, cn } from "@/components/ui/primitives";
import { ChatControls } from "@/components/chat/chat-controls";
import { ThinkingPanel } from "@/components/chat/thinking-panel";

interface Turn {
  question: string;
  response: QueryResponse | null; // null while loading
  error?: string;
}

export default function ChatPage() {
  const [meta, setMeta] = useState<QueryModelsResponse | null>(null);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [model, setModel] = useState("");
  const [tier, setTier] = useState("low");
  const [scope, setScope] = useState<string[]>([]); // empty = all
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      const [m, cols] = await Promise.all([
        api.queryModels(),
        api.listCollections().catch(() => []),
      ]);
      setMeta(m);
      setModel(m.default);
      setCollections(cols);
    })();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const toggleCollection = (id: string) => {
    setScope((prev) => {
      // start from "all selected" when empty
      const base = prev.length === 0 ? collections.map((c) => c.id) : prev;
      const next = base.includes(id)
        ? base.filter((x) => x !== id)
        : [...base, id];
      // if all are selected again, normalize back to [] (= all)
      return next.length === collections.length ? [] : next;
    });
  };

  const sessionCost = turns.reduce(
    (sum, t) => sum + (t.response?.cost.total_cost_usd ?? 0),
    0,
  );

  const ask = useCallback(async () => {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [...t, { question: q, response: null }]);
    try {
      const res = await api.runQuery({
        question: q,
        model_key: model,
        thinking_tier: tier as "low" | "medium" | "high",
        collection_ids: scope.length ? scope : undefined,
      });
      setTurns((t) =>
        t.map((turn, i) =>
          i === t.length - 1 ? { ...turn, response: res } : turn,
        ),
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setTurns((t) =>
        t.map((turn, i) =>
          i === t.length - 1 ? { ...turn, error: msg } : turn,
        ),
      );
    } finally {
      setBusy(false);
    }
  }, [question, busy, model, tier, scope]);

  const resetChat = () => setTurns([]);

  if (!meta) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading chat…
      </div>
    );
  }

  const noCorpora = collections.length === 0;

  return (
    <div className="flex h-full flex-col gap-4 lg:flex-row">
      {/* ── left: controls ── */}
      <div className="lg:w-80 lg:shrink-0">
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-lg text-ink">Query setup</h2>
            {turns.length > 0 && (
              <button
                onClick={resetChat}
                className="text-xs text-ink-mute underline hover:text-ink-soft"
              >
                Reset chat
              </button>
            )}
          </div>
          <ChatControls
            models={meta.models}
            selectedModel={model}
            onModel={setModel}
            tiers={meta.tiers}
            selectedTier={tier}
            onTier={setTier}
            collections={collections}
            selectedCollections={scope}
            onToggleCollection={toggleCollection}
            disabled={busy}
          />
        </Card>

        {/* session cost */}
        <Card className="mt-3 p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-mute">
            Session cost
          </h3>
          <div className="font-display text-2xl font-semibold text-ink">
            ${sessionCost.toFixed(5)}
          </div>
          <p className="mt-1 text-xs text-ink-mute">
            {turns.filter((t) => t.response).length} queries this session ·
            time-based (per-second GPU)
          </p>
        </Card>
      </div>

      {/* ── right: conversation ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-2">
          <h1 className="font-display text-3xl font-semibold text-ink">Chat</h1>
          <p className="text-sm text-ink-soft">
            The first message may take up to <strong>3 minutes</strong>to load
            because the system needs to find an available GPU to rent and load
            the model weights before generating a response. This delay exists
            due to financial constraints, as keeping a GPU running 24/7 is not
            feasible for a portfolio project.
            <br />
            <br />
            In a production environment, the model would run on a readily
            available GPU or a warm server, reducing the first-message wait time
            to only a few seconds. There is also a chance the first message may
            return a <strong>524</strong> error due to timeout. This is
            expected; simply send the message again, and it should respond much
            faster the second time.
          </p>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto pb-4">
          {turns.length === 0 && (
            <Card className="p-8 text-center text-sm text-ink-mute">
              {noCorpora ? (
                <>
                  No documents indexed yet. Add some in the{" "}
                  <a href="/knowledge-base" className="text-brand underline">
                    Knowledge Base
                  </a>{" "}
                  first.
                </>
              ) : (
                "Ask a question to begin. Try: “What is the HbA1c target for type 2 diabetes?”"
              )}
            </Card>
          )}

          {turns.map((turn, i) => (
            <div key={i} className="space-y-2">
              {/* user question */}
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-lg bg-brand px-4 py-2 text-sm text-white">
                  {turn.question}
                </div>
              </div>

              {/* answer */}
              <div className="max-w-[95%]">
                {turn.error ? (
                  <Card className="border-[var(--danger)]/30 bg-[var(--warn-soft)] p-3 text-sm text-danger">
                    {turn.error}
                  </Card>
                ) : !turn.response ? (
                  <Card className="flex items-center gap-2 p-3 text-sm text-ink-mute">
                    <Spinner /> Retrieving and reasoning…
                  </Card>
                ) : (
                  <Card className="p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs font-medium text-ink-soft">
                        {turn.response.model.display_name}
                      </span>
                      <span className="rounded-sm bg-ink/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink-mute">
                        {turn.response.thinking_tier}
                      </span>
                      {turn.response.mocked && (
                        <span className="rounded-sm bg-[var(--warn-soft)] px-1.5 py-0.5 text-[10px] font-medium text-warn">
                          simulated · no GPU billed
                        </span>
                      )}
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-ink">
                      {turn.response.answer}
                    </p>

                    <ThinkingPanel
                      events={turn.response.trace_events}
                      nCalls={turn.response.cost.n_inference_calls}
                    />

                    <div className="mt-2 flex items-center gap-3 text-[11px] text-ink-mute">
                      <span>
                        cost ${turn.response.cost.total_cost_usd.toFixed(5)}
                      </span>
                      <span>
                        {(turn.response.cost.total_latency_ms / 1000).toFixed(
                          1,
                        )}
                        s
                      </span>
                      <span>
                        {turn.response.cost.n_inference_calls} inference{" "}
                        {turn.response.cost.n_inference_calls === 1
                          ? "call"
                          : "calls"}
                      </span>
                    </div>
                  </Card>
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        {/* input */}
        <div className="flex gap-2 border-t border-border pt-3">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask();
              }
            }}
            placeholder={
              noCorpora ? "Index documents first…" : "Ask a question…"
            }
            disabled={busy || noCorpora}
            rows={2}
            className="flex-1 resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand disabled:opacity-50"
          />
          <Button
            onClick={ask}
            disabled={busy || noCorpora || !question.trim()}
          >
            {busy ? <Spinner /> : "Send"}
          </Button>
        </div>
      </div>
    </div>
  );
}
