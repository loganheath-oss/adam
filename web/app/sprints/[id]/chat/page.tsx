"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { MarkdownView } from "@/components/markdown";

type Msg = { role: "user" | "assistant"; content: string };

export default function SprintChatPage() {
  const params = useParams();
  const id = String(params.id);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  // Restore history on load.
  useEffect(() => {
    fetch(`/api/sprints/${id}/chat`)
      .then((r) => r.json())
      .then((d) => {
        const msgs: Msg[] = (d.messages ?? [])
          .filter((m: Msg) => m.role === "user" || m.role === "assistant")
          .map((m: Msg) => ({ role: m.role, content: m.content }));
        if (msgs.length) setMessages(msgs);
      })
      .catch(() => {});
  }, [id]);

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

    let botText = "";
    const setBot = (t: string) =>
      setMessages((m) => {
        const c = [...m];
        c[c.length - 1] = { role: "assistant", content: t };
        return c;
      });

    try {
      const resp = await fetch(`/api/sprints/${id}/chat`, {
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
          let evt: { type: string; text?: string; message?: string };
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
            setStatus("working…");
          } else if (evt.type === "error") {
            setStatus("");
            setBot("⚠️ " + (evt.message ?? "Something went wrong."));
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
        <Link href={`/sprints/${id}`} className="text-sm text-muted-foreground hover:text-foreground">← Sprint</Link>
        <h1 className="mt-3 text-3xl font-medium tracking-tight">Sprint chat</h1>
        <p className="mt-1 font-mono text-xs text-muted-foreground">{id}</p>
      </div>

      <div className="mt-5 flex-1 space-y-5 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Ask ADAM to drive this sprint — approve gates, review copy, or explain what’s happening.
          </p>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground">{m.content}</div>
            </div>
          ) : (
            <div key={i} className="max-w-[92%] text-sm leading-relaxed [&_p]:my-2 [&_p:first-child]:mt-0">
              {m.content ? <MarkdownView>{m.content}</MarkdownView> : status && <span className="text-muted-foreground">{status}</span>}
            </div>
          ),
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="mt-4 flex items-center gap-2 rounded-full border bg-background px-2 py-1.5 shadow-sm"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message this sprint…"
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
