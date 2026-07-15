"use client";

import { useEffect, useRef, useState } from "react";
import { MarkdownView } from "@/components/markdown";

type Msg = { role: "user" | "assistant"; content: string };
type Source = { title?: string; label?: string; href?: string; url?: string };

const SUGGESTIONS = [
  "How do I add a new visual style?",
  "Why might generated copy come back blank?",
  "What are ADAM's hard constraints?",
  "Walk me through the pipeline stages.",
];

export default function AskAdamPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  async function send(text: string) {
    text = text.trim();
    if (!text || streaming) return;
    setInput("");
    const history: Msg[] = [...messages, { role: "user", content: text }];
    setMessages([...history, { role: "assistant", content: "" }]);
    setStreaming(true);
    setStatus("thinking…");
    setSources([]);

    let botText = "";
    const setBot = (t: string) =>
      setMessages((m) => {
        const c = [...m];
        c[c.length - 1] = { role: "assistant", content: t };
        return c;
      });

    try {
      const resp = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      const reader = resp.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const line of parts) {
          if (!line.startsWith("data: ")) continue;
          let evt: { type: string; text?: string; message?: string; sources?: Source[] };
          try {
            evt = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (evt.type === "text") {
            setStatus("");
            botText += evt.text ?? "";
            setBot(botText);
          } else if (evt.type === "tool_call") {
            setStatus("searching the wiki…");
          } else if (evt.type === "sources") {
            setSources(evt.sources ?? []);
          } else if (evt.type === "error") {
            setStatus("");
            botText = "⚠️ " + (evt.message ?? "Something went wrong.");
            setBot(botText);
          } else if (evt.type === "done") {
            setStatus("");
          }
        }
      }
    } catch {
      setBot("⚠️ Network error — try again.");
    }
    setStreaming(false);
    setStatus("");
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-11rem)] max-w-3xl flex-col">
      {messages.length === 0 ? (
        <div className="flex flex-1 flex-col items-center px-4 pt-10 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[#ECECEC] bg-[#F4FAF1] text-primary shadow-[0_1px_2px_rgba(0,0,0,0.04),0_4px_12px_rgba(0,0,0,0.05)]">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6"><path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z" /><path d="M20 2v4" /><path d="M22 4h-4" /><circle cx="4" cy="20" r="2" /></svg>
          </div>
          <h1 className="mt-5 text-4xl font-medium tracking-tight">Ask ADAM</h1>
          <p className="mt-3 max-w-md text-sm text-muted-foreground">
            A read-only assistant grounded in the ADAM wiki. Ask how the pipeline is built, how to run it, or where something lives — answers cite their wiki sources.
          </p>
          <div className="mt-8 grid w-full max-w-xl gap-3 sm:grid-cols-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-xl border border-[#ECECEC] bg-white px-4 py-3 text-left text-[13.5px] text-[#5b6660] shadow-[0_1px_2px_rgba(0,0,0,0.04),0_4px_12px_rgba(0,0,0,0.05)] transition-colors hover:border-primary/50 hover:text-foreground"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 space-y-5 overflow-y-auto pr-1">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground">
                {m.content}
              </div>
            </div>
          ) : (
            <div key={i} className="max-w-[92%]">
              {m.content ? (
                <div className="text-sm leading-relaxed [&_p]:my-2 [&_p:first-child]:mt-0">
                  <MarkdownView>{m.content}</MarkdownView>
                </div>
              ) : (
                status && <div className="text-sm text-muted-foreground">{status}</div>
              )}
              {i === messages.length - 1 && sources.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {sources.map((s, j) => {
                    const href = s.href || s.url || "#";
                    const label = s.title || s.label || href;
                    return (
                      <a
                        key={j}
                        href={href}
                        className="rounded-full border px-2.5 py-1 font-mono text-xs text-muted-foreground hover:text-foreground"
                      >
                        {label}
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          ),
        )}
        <div ref={endRef} />
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-4 flex items-center gap-2 rounded-full border bg-background px-2 py-1.5 shadow-sm"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about ADAM…"
          className="flex-1 bg-transparent px-3 py-1.5 text-sm outline-none"
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={streaming || !input.trim()}
          className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors hover:bg-[#108A00] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M12 19V5" /><path d="m5 12 7-7 7 7" /></svg>
        </button>
      </form>
      <p className="mt-2 text-center text-xs text-muted-foreground">
        ADAM answers from the wiki and may be imperfect — verify anything load-bearing.
      </p>
    </div>
  );
}
