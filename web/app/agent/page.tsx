"use client";

import { useEffect, useRef, useState } from "react";
import { MarkdownView } from "@/components/markdown";

type Msg = { role: "user" | "assistant"; content: string };
type Source = { title?: string; label?: string; href?: string; url?: string };

const SUGGESTIONS = [
  "How does the pipeline work?",
  "What are the gates?",
  "How does the Figma plugin assemble ads?",
  "What can't ADAM do (the constraints)?",
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
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Ask ADAM</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Read-only assistant — ask how ADAM is built or how to use it. It answers from the wiki.
        </p>
      </div>

      <div className="mt-6 flex-1 space-y-5 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="rounded-xl border bg-muted/30 p-5">
            <p className="text-sm text-muted-foreground">Try asking:</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border px-3 py-1.5 text-sm text-muted-foreground hover:border-primary hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

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
          placeholder="Ask anything about ADAM…"
          className="flex-1 bg-transparent px-3 py-1.5 text-sm outline-none"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-40"
        >
          {streaming ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
