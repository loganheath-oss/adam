"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MarkdownView } from "@/components/markdown";

// ─── The "working with ADAM" surface ──────────────────────────────────────────
// Faithful React port of the FastAPI sprint_chat_ui: a two-column workspace with
// the agentic chat (feed + context-aware quick-bar + composer) on the left and a
// live Pipeline Gates rail on the right. On open it bootstraps ADAM to show
// whatever gate is open, streams live pipeline narration, and polls for
// server-pushed gate notifications — same behavior as the live tool.

type Role = "user" | "assistant" | "system";
type Item =
  | { kind: "msg"; role: Role; content: string; streaming?: boolean }
  | { kind: "tool"; name: string; done: boolean }
  | { kind: "pipeline"; lines: PipeLine[]; active: boolean };

type PipeLine = {
  message: string;
  eta: number;
  startedAt: number;
  itemIndex?: number;
  itemTotal?: number;
  itemLabel?: string;
  itemChangedAt?: number;
};

type QuickAction = { label: string; text?: string; href?: string; navHref?: string; primary?: boolean; pulse?: boolean; approveGate?: number };

const GATE_DEFS = [
  { num: 2, label: "Order + Refs", sub: "Brief & references review" },
  { num: 3, label: "Copy", sub: "Ad copy concepts" },
  { num: 4, label: "Image Prompts", sub: "Visual direction scan" },
  { num: 5, label: "Assembly", sub: "Manifest & layout" },
  { num: 6, label: "Final QA", sub: "Pre-Figma check" },
];
const GATE_NUMS = [2, 3, 4, 5, 6];

const ACTIVE_PIPELINE_STATES = new Set([
  "queued", "running",
  "stage_01_load_refs", "stage_02_copy_gen", "stage_03_image_prompts",
  "stage_04_generate_images", "stage_05_figma_assembly", "stage_06_deliver",
  "resuming_gate_2", "resuming_gate_3", "resuming_gate_4", "resuming_gate_5", "resuming_gate_6",
]);

function gateFromState(state: string): number | null {
  const m = state.match(/awaiting_gate_(\d+)/);
  return m ? parseInt(m[1]) : null;
}

// The artifact ADAM should surface automatically when each gate opens, so the
// user sees what they're approving without having to ask.
const GATE_ARTIFACT_PROMPT: Record<number, string> = {
  2: "Show me the order details and the references that were loaded",
  3: "Show me the copy concepts",
  4: "Show me the image prompts and photo picks",
  5: "Show me the assembly manifest and the copy-to-image pairings",
  6: "Show me the final QA / delivery package",
};
// Server-written gate-open notifications always contain this phrase; used to
// tell a bare teaser apart from a full artifact already on screen.
const isTeaser = (t: string) => /show me what'?s in it/i.test(t || "");

function fmtSec(s: number): string {
  s = Math.max(0, Math.round(s));
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60), r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

function quickActionsFor(sprintId: string, raw: string): QuickAction[] {
  const state = raw.toLowerCase();
  const currentGate = gateFromState(state);
  const isComplete = state === "complete";
  const isError = state === "error" || state.includes("interrupted");
  const isRunning = ACTIVE_PIPELINE_STATES.has(state);
  const GATE_ACTIONS: Record<number, QuickAction[]> = {
    2: [
      { label: "👁 Show me what's in it", text: "Show me the order details and references" },
      { label: "✏️ Edit order", text: "I want to change something in the order" },
      { label: "❔ What changed?", text: "What changed since the last gate?" },
    ],
    3: [
      { label: "👁 Show me what's in it", text: "Show me the copy concepts" },
      { label: "🔝 Top 2 only", text: "Show me only the top 2 copy concepts" },
      { label: "❔ What changed?", text: "What changed since the last gate?" },
    ],
    4: [
      { label: "👁 Show me what's in it", text: "Show me the image prompts" },
      { label: "❔ What changed?", text: "What changed since the last gate?" },
    ],
    5: [
      { label: "👁 Show me what's in it", text: "Show me the assembly manifest and copy-to-image pairings" },
      { label: "❔ What changed?", text: "What changed since the last gate?" },
    ],
    6: [
      { label: "👁 Show me the final delivery", text: "Show me the final QA package" },
      { label: "🖼 Upload / view final ads", navHref: `/sprints/${sprintId}/finals` },
      { label: "⬇ Download manifest (CSV)", href: `/api/sprints/${sprintId}/file/asset_manifest.csv` },
    ],
  };
  const actions: QuickAction[] = [];
  if (currentGate) {
    actions.push({ label: `✓ Approve gate ${currentGate}`, approveGate: currentGate, primary: true, pulse: true });
    for (const a of GATE_ACTIONS[currentGate] || []) actions.push(a);
  } else if (isComplete) {
    actions.push({ label: "🖼 Final ads", navHref: `/sprints/${sprintId}/finals`, primary: true });
    actions.push({ label: "⬇ Download manifest (CSV)", href: `/api/sprints/${sprintId}/file/asset_manifest.csv` });
    actions.push({ label: "📊 Run a post-mortem", text: "Walk me through what worked and what to improve next time" });
  } else if (isError) {
    actions.push({ label: "❓ What went wrong?", text: "What went wrong with the pipeline?", primary: true });
  } else if (isRunning) {
    actions.push({ label: "⏱ What's happening?", text: "What stage are we on right now and how long until the next gate?" });
    actions.push({ label: "📋 Show the brief", text: "Show me the original order and brief" });
    actions.push({ label: "🙋 What do you need from me?", text: "What do you need from me right now?" });
  } else {
    actions.push({ label: "⏱ Status", text: "What gate are we at and what happens next?" });
  }
  actions.push({ label: "📜 History", text: "Summarize what we've done so far in this sprint" });
  return actions;
}

export function SprintWorkspace({
  sprintId,
  initialState,
  initialDriver,
  initialPlatform,
}: {
  sprintId: string;
  initialState: string;
  initialDriver: string;
  initialPlatform: string;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sprintState, setSprintState] = useState(initialState);
  const [driver, setDriver] = useState(initialDriver);
  const [platform, setPlatform] = useState(initialPlatform);
  const [, setTick] = useState(0); // forces elapsed re-render during narration

  const historyRef = useRef<{ role: Role; content: string }[]>([]);
  const streamingRef = useRef(false);
  const pipelineStreamingRef = useRef(false);
  const lastChatSeqRef = useRef(-1);
  const lastStateRef = useRef(initialState);
  const esRef = useRef<EventSource | null>(null);
  const tickerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const bootedRef = useRef(false);
  const bootDoneRef = useRef(false);
  const autoShownRef = useRef<Set<number>>(new Set());
  const lastAssistantRef = useRef<string>("");

  const scrollDown = useCallback(() => {
    requestAnimationFrame(() => {
      const el = feedRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  // ── State polling ──────────────────────────────────────────────────────────
  const pollState = useCallback(async () => {
    try {
      const r = await fetch(`/api/sprints/${sprintId}/state`, { cache: "no-store" });
      if (!r.ok) return;
      const d = await r.json();
      const s = d.state || "";
      setSprintState(s);
      lastStateRef.current = s;
      if (d.driver) setDriver(d.driver);
      if (d.platform) setPlatform(d.platform);
    } catch {
      /* keep last known */
    }
  }, [sprintId]);

  // ── Live pipeline narration (EventSource on /events) ─────────────────────────
  const startNarration = useCallback(() => {
    if (pipelineStreamingRef.current) return;
    pipelineStreamingRef.current = true;

    const line0Holder: { lines: PipeLine[] } = { lines: [] };
    // Push a pipeline item and keep a stable reference to its lines array.
    setItems((prev) => [...prev, { kind: "pipeline", lines: line0Holder.lines, active: true }]);
    scrollDown();

    const updateItem = () =>
      setItems((prev) => {
        const c = [...prev];
        for (let i = c.length - 1; i >= 0; i--) {
          if (c[i].kind === "pipeline") {
            c[i] = { kind: "pipeline", lines: [...line0Holder.lines], active: true };
            break;
          }
        }
        return c;
      });

    if (tickerRef.current) clearInterval(tickerRef.current);
    tickerRef.current = setInterval(() => setTick((t) => t + 1), 1000);

    const es = new EventSource(`/api/sprints/${sprintId}/events`);
    esRef.current = es;
    let finalState: string | null = null;

    es.onmessage = (ev) => {
      let data: {
        type: string; state?: string; message?: string; eta_seconds?: number;
        item_index?: number; item_total?: number; item_label?: string;
      };
      try { data = JSON.parse(ev.data); } catch { return; }
      if (data.type === "status") {
        const lines = line0Holder.lines;
        const cur = lines[lines.length - 1];
        if (cur && (cur as PipeLine & { state?: string }).state === data.state) {
          cur.message = data.message || cur.message;
          cur.itemIndex = data.item_index;
          cur.itemTotal = data.item_total;
          cur.itemLabel = data.item_label;
          cur.itemChangedAt = Date.now();
        } else {
          lines.push({
            message: data.message || "", eta: data.eta_seconds || 0, startedAt: Date.now(),
            itemIndex: data.item_index, itemTotal: data.item_total, itemLabel: data.item_label,
            itemChangedAt: Date.now(),
            ...(data.state ? { state: data.state } : {}),
          } as PipeLine);
        }
        updateItem();
        scrollDown();
      } else if (data.type === "done") {
        finalState = data.state || null;
        es.close();
        finishNarration(finalState);
      }
    };
    es.onerror = () => {
      es.close();
      if (esRef.current === es) esRef.current = null;
      if (tickerRef.current) { clearInterval(tickerRef.current); tickerRef.current = null; }
      pipelineStreamingRef.current = false;
    };

    function finishNarration(fin: string | null) {
      if (tickerRef.current) { clearInterval(tickerRef.current); tickerRef.current = null; }
      // Mark the pipeline bubble complete (no active progress bar).
      setItems((prev) => {
        const c = [...prev];
        for (let i = c.length - 1; i >= 0; i--) {
          if (c[i].kind === "pipeline") {
            c[i] = { kind: "pipeline", lines: [...line0Holder.lines], active: false };
            break;
          }
        }
        return c;
      });
      pipelineStreamingRef.current = false;
      pollState();
      // On reaching a gate / completion, auto-surface the artifact so the user
      // sees what they're approving without asking — same "just works" behavior.
      if (typeof fin === "string" && fin.startsWith("awaiting_gate_")) {
        const g = parseInt(fin.replace("awaiting_gate_", ""));
        setTimeout(() => autoShowArtifact(g), 400);
      } else if (fin === "complete" && !autoShownRef.current.has(99)) {
        autoShownRef.current.add(99);
        const p = `[auto] The pipeline just completed. Fetch the run summary and available files, then show me what was delivered.`;
        setTimeout(() => { if (!streamingRef.current) doSend(p, true); }, 400);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sprintId, pollState, scrollDown]);

  const maybeStartNarration = useCallback(async () => {
    if (pipelineStreamingRef.current || streamingRef.current) return;
    try {
      const r = await fetch(`/api/sprints/${sprintId}/state`, { cache: "no-store" });
      if (!r.ok) return;
      const d = await r.json();
      if (pipelineStreamingRef.current || streamingRef.current) return;
      if (ACTIVE_PIPELINE_STATES.has(d.state)) startNarration();
    } catch { /* ignore */ }
  }, [sprintId, startNarration]);

  // ── Sending ──────────────────────────────────────────────────────────────────
  const doSend = useCallback(async (text: string, hidden = false) => {
    text = text.trim();
    if (!text || streamingRef.current) return;
    streamingRef.current = true;
    setStreaming(true);

    if (!hidden) setItems((p) => [...p, { kind: "msg", role: "user", content: text }]);
    historyRef.current.push({ role: "user", content: text });
    setItems((p) => [...p, { kind: "msg", role: "assistant", content: "", streaming: true }]);
    scrollDown();

    let full = "";
    const setBot = (t: string) =>
      setItems((prev) => {
        const c = [...prev];
        for (let i = c.length - 1; i >= 0; i--) {
          if (c[i].kind === "msg" && (c[i] as { role: Role }).role === "assistant") {
            c[i] = { kind: "msg", role: "assistant", content: t, streaming: true };
            break;
          }
        }
        return c;
      });
    const finishBot = () => {
      lastAssistantRef.current = full;
      setItems((prev) => {
        const c = [...prev];
        for (let i = c.length - 1; i >= 0; i--) {
          if (c[i].kind === "msg" && (c[i] as { role: Role }).role === "assistant") {
            c[i] = { kind: "msg", role: "assistant", content: full };
            break;
          }
        }
        return c;
      });
    };

    try {
      const resp = await fetch(`/api/sprints/${sprintId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: historyRef.current }),
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
        for (const part of parts) {
          if (!part.startsWith("data:")) continue;
          let evt: { type: string; text?: string; name?: string; message?: string };
          try { evt = JSON.parse(part.slice(5).trim()); } catch { continue; }
          if (evt.type === "text") {
            full += evt.text ?? "";
            setBot(full);
            scrollDown();
          } else if (evt.type === "tool_call") {
            setItems((p) => [...p, { kind: "tool", name: evt.name || "tool", done: false }]);
            scrollDown();
          } else if (evt.type === "tool_result") {
            setItems((prev) => {
              const c = [...prev];
              for (let i = c.length - 1; i >= 0; i--) {
                if (c[i].kind === "tool" && !(c[i] as { done: boolean }).done) {
                  c[i] = { ...(c[i] as Item & { kind: "tool" }), done: true };
                  break;
                }
              }
              return c;
            });
            pollState();
          } else if (evt.type === "error") {
            full += `\n⚠ ${evt.message || "Something went wrong."}`;
            setBot(full);
          }
        }
      }
    } catch {
      full = full || "⚠ Connection error — try again.";
      setBot(full);
    }
    finishBot();
    if (full) historyRef.current.push({ role: "assistant", content: full });
    streamingRef.current = false;
    setStreaming(false);
    pollState();
    // Re-baseline the chat cursor so proactive polling won't replay this turn.
    try {
      const r = await fetch(`/api/sprints/${sprintId}/chat`, { cache: "no-store" });
      if (r.ok) {
        const d = await r.json();
        const msgs = d.messages || [];
        if (msgs.length) lastChatSeqRef.current = msgs[msgs.length - 1].seq ?? lastChatSeqRef.current;
      }
    } catch { /* ignore */ }
    maybeStartNarration();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sprintId, pollState, scrollDown, maybeStartNarration]);

  // Auto-surface the artifact for an open gate so the user sees what they're
  // approving without asking. Fires once per gate; skips if the artifact is
  // already the latest thing on screen (i.e. only a bare teaser triggers it),
  // so reloads don't duplicate it or burn an extra call.
  const autoShowArtifact = useCallback((gate: number) => {
    if (!gate || autoShownRef.current.has(gate)) return;
    if (streamingRef.current || pipelineStreamingRef.current) return;
    autoShownRef.current.add(gate);
    const p = GATE_ARTIFACT_PROMPT[gate] || "Show me what I need to approve at this gate";
    doSend(`[auto] The sprint is now open at Gate ${gate}; every earlier gate has already been approved and the pipeline has advanced (approvals happen via the Approve button, not this chat, so don't assume a prior gate is unapproved). ${p}. If the artifact file looks empty, the stage may still be finishing — say that briefly instead of concluding a gate wasn't approved. Lay out exactly what I need to approve in plain English with the data shown, then end with "reply approve to continue, or tell me what to change."`, true);
  }, [doSend]);

  // Deterministic gate approval — calls the approve endpoint directly (no LLM
  // round-trip), so the button always works and gives instant feedback. The
  // pipeline resumes; narration + auto-show surface the next gate's artifact.
  const approveGate = useCallback(async (gate: number) => {
    if (streamingRef.current || pipelineStreamingRef.current) return;
    streamingRef.current = true;
    setStreaming(true);
    setItems((p) => [...p, { kind: "msg", role: "system", content: `Approving gate ${gate}…` }]);
    scrollDown();
    try {
      const r = await fetch("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sprintId, gateNum: gate }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        // 409 = state already moved on (double-click / already approved) — not fatal.
        const msg = r.status === 409 ? `Gate ${gate} already approved — continuing…` : `⚠ ${d.error || "Approve failed"}`;
        setItems((p) => [...p, { kind: "msg", role: "system", content: msg }]);
      } else {
        setItems((p) => [...p, { kind: "msg", role: "system", content: `✓ Gate ${gate} approved — ADAM is working on the next step…` }]);
      }
    } catch {
      setItems((p) => [...p, { kind: "msg", role: "system", content: "⚠ Approve failed — network error, try again." }]);
    }
    streamingRef.current = false;
    setStreaming(false);
    await pollState();
    // Resume produces the next stage: narrate it, then auto-show its artifact.
    maybeStartNarration();
  }, [sprintId, pollState, maybeStartNarration, scrollDown]);

  // ── Proactive chat-history polling (server writes gate notifications) ─────────
  const pollChat = useCallback(async () => {
    if (streamingRef.current) return;
    try {
      const r = await fetch(`/api/sprints/${sprintId}/chat`, { cache: "no-store" });
      if (!r.ok) return;
      const d = await r.json();
      const msgs: { seq?: number; role?: Role; text?: string }[] = d.messages || [];
      if (lastChatSeqRef.current < 0) {
        lastChatSeqRef.current = msgs.length ? (msgs[msgs.length - 1].seq ?? -1) : -1;
        return;
      }
      const fresh = msgs.filter((m) => typeof m.seq === "number" && m.seq > lastChatSeqRef.current);
      for (const m of fresh) {
        if (!m.role || !m.text) continue;
        setItems((p) => [...p, { kind: "msg", role: m.role as Role, content: m.text as string }]);
        historyRef.current.push({ role: m.role as Role, content: m.text });
        if (m.role === "assistant") lastAssistantRef.current = m.text;
        lastChatSeqRef.current = m.seq as number;
      }
      if (fresh.length) { pollState(); scrollDown(); }
    } catch { /* ignore */ }
  }, [sprintId, pollState, scrollDown]);

  // ── Boot ─────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (bootedRef.current) return;
    bootedRef.current = true;

    (async () => {
      await pollState();
      let prior: { seq?: number; role?: Role; text?: string }[] = [];
      try {
        const r = await fetch(`/api/sprints/${sprintId}/chat`, { cache: "no-store" });
        if (r.ok) prior = (await r.json()).messages || [];
      } catch { /* ignore */ }

      if (prior.length > 0) {
        const restored: Item[] = [];
        for (const m of prior) {
          if (!m.role || !m.text) continue;
          restored.push({ kind: "msg", role: m.role as Role, content: m.text });
          historyRef.current.push({ role: m.role as Role, content: m.text });
          if (m.role === "assistant") lastAssistantRef.current = m.text;
        }
        setItems(restored);
        lastChatSeqRef.current = prior.length ? (prior[prior.length - 1].seq ?? -1) : -1;
        scrollDown();
      }
      maybeStartNarration();
      bootDoneRef.current = true;
      // Auto-surface the open gate's artifact on load — but if the restored
      // transcript already ends in a substantive (non-teaser) reply, assume the
      // artifact is on screen and just seed the guard so we don't duplicate it.
      const g = gateFromState((lastStateRef.current || "").toLowerCase());
      if (g) {
        const lastText = prior.length ? (prior.filter((m) => m.role === "assistant").pop()?.text ?? "") : "";
        if (lastText && !isTeaser(lastText)) autoShownRef.current.add(g);
        else autoShowArtifact(g);
      }
    })();

    const stateInt = setInterval(pollState, 10000);
    const chatInt = setInterval(pollChat, 5000);
    return () => {
      clearInterval(stateInt);
      clearInterval(chatInt);
      if (tickerRef.current) clearInterval(tickerRef.current);
      if (esRef.current) { try { esRef.current.close(); } catch { /* */ } }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When the sprint advances to a new open gate while the page is open,
  // auto-surface that gate's artifact (guarded once-per-gate).
  useEffect(() => {
    if (!bootDoneRef.current) return;
    const g = gateFromState(sprintState.toLowerCase());
    if (g) autoShowArtifact(g);
  }, [sprintState, autoShowArtifact]);

  // ── Derived gate rail ──────────────────────────────────────────────────────
  const raw = sprintState.toLowerCase();
  const currentGate = gateFromState(raw);
  const isComplete = raw === "complete";
  const isError = raw === "error" || raw.includes("interrupted");
  const isRunning = ACTIVE_PIPELINE_STATES.has(raw);
  const quick = quickActionsFor(sprintId, sprintState);

  function gateStatus(n: number): "done" | "current" | "pending" | "error" {
    if (isError && currentGate === n) return "error";
    if (isComplete || (currentGate && n < currentGate)) return "done";
    if (currentGate === n || (isRunning && n === 2)) return "current";
    return "pending";
  }

  const send = () => { const t = input.trim(); if (t && !streamingRef.current) { setInput(""); doSend(t); } };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
      {/* Chat column */}
      <div className="flex h-[calc(100vh-13rem)] min-h-[520px] flex-col rounded-xl border bg-background">
        <div ref={feedRef} className="flex-1 space-y-5 overflow-y-auto p-5">
          {items.length === 0 && (
            <p className="text-sm text-muted-foreground">Connecting to ADAM…</p>
          )}
          {items.map((it, i) => {
            if (it.kind === "tool") {
              return (
                <div key={i} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-xs ${it.done ? "border-primary/30 bg-primary/5 text-primary" : "border-border bg-muted text-muted-foreground"}`}>
                  <span>⚙</span>{it.name}{!it.done && <span className="animate-pulse">…</span>}
                </div>
              );
            }
            if (it.kind === "pipeline") {
              return <PipelineBubble key={i} lines={it.lines} active={it.active} />;
            }
            if (it.role === "system") {
              return (
                <div key={i} className="text-center text-xs font-medium text-muted-foreground">{it.content}</div>
              );
            }
            if (it.role === "user") {
              return (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground">{it.content}</div>
                </div>
              );
            }
            return (
              <div key={i} className="flex gap-3">
                <div className="mt-0.5 flex h-7 w-7 flex-none items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">A</div>
                <div className="min-w-0 flex-1 text-sm leading-relaxed [&_p:first-child]:mt-0 [&_p]:my-2">
                  {it.content ? (
                    <MarkdownView>{it.content}</MarkdownView>
                  ) : it.streaming ? (
                    <span className="text-muted-foreground">thinking…</span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>

        {/* Quick-action bar */}
        <div className="flex flex-wrap gap-2 border-t px-4 pt-3">
          {quick.map((a, i) =>
            a.href || a.navHref ? (
              <a
                key={i}
                href={a.href || a.navHref}
                {...(a.href ? { download: "" } : {})}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${a.primary ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background hover:bg-muted"}`}
              >
                {a.label}
              </a>
            ) : (
              <button
                key={i}
                type="button"
                disabled={streaming}
                onClick={() => (a.approveGate != null ? approveGate(a.approveGate) : a.text && doSend(a.text))}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition disabled:opacity-40 ${a.primary ? "border-primary bg-primary text-primary-foreground hover:brightness-95" : "border-border bg-background hover:bg-muted"} ${a.pulse ? "ring-2 ring-primary/40 ring-offset-1" : ""}`}
              >
                {a.label}
              </button>
            ),
          )}
        </div>

        {/* Composer */}
        <div className="flex items-end gap-2 p-4">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Message ADAM…"
            rows={1}
            disabled={streaming}
            className="max-h-32 flex-1 resize-none rounded-xl border bg-background px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
          />
          <button
            type="button"
            onClick={send}
            disabled={streaming || !input.trim()}
            className="rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-40"
          >
            {streaming ? "…" : "Send"}
          </button>
        </div>
      </div>

      {/* Gates rail */}
      <aside className="flex h-fit flex-col rounded-xl border bg-background">
        <div className="border-b px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Pipeline Gates</div>
        <div className="p-2">
          {GATE_DEFS.map((g) => {
            const st = gateStatus(g.num);
            const icon =
              st === "done" ? "✓" : st === "error" ? "!" : String(g.num);
            const iconCls =
              st === "done" ? "bg-primary text-primary-foreground"
                : st === "current" ? "bg-primary text-primary-foreground ring-2 ring-primary/40"
                : st === "error" ? "bg-red-600 text-white"
                : "bg-muted text-muted-foreground";
            const labelCls =
              st === "done" ? "text-primary"
                : st === "current" ? "text-primary font-semibold"
                : st === "error" ? "text-red-700 font-semibold"
                : "text-muted-foreground";
            return (
              <div key={g.num} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 ${st === "current" ? "bg-primary/5" : ""}`}>
                <div className={`flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-semibold ${iconCls}`}>{icon}</div>
                <div className="min-w-0">
                  <div className={`text-sm ${labelCls}`}>{g.label}</div>
                  <div className="text-xs text-muted-foreground">{g.sub}</div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-auto space-y-1.5 border-t px-4 py-3 text-xs">
          <Meta label="State" value={sprintState || "—"} />
          <Meta label="Driver" value={driver || "—"} />
          <Meta label="Platform" value={platform || "—"} />
        </div>
      </aside>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-medium text-foreground">{value}</span>
    </div>
  );
}

function PipelineBubble({ lines, active }: { lines: PipeLine[]; active: boolean }) {
  const last = lines.length - 1;
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex h-7 w-7 flex-none items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">A</div>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="text-xs font-medium text-muted-foreground">ADAM · live pipeline</div>
        {lines.map((line, i) => {
          const isActive = active && i === last;
          if (!isActive) {
            return (
              <div key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="text-primary">✓</span>{line.message}
              </div>
            );
          }
          const elapsed = (Date.now() - line.startedAt) / 1000;
          let pct: number | null;
          let etaLabel: string;
          let over = false;
          if (line.itemTotal && line.itemTotal > 0) {
            pct = Math.min(100, ((line.itemIndex || 0) / line.itemTotal) * 100);
            const lbl = line.itemLabel ? ` · ${line.itemLabel}` : "";
            etaLabel = `${line.itemIndex || 0} / ${line.itemTotal}${lbl}`;
            const sinceUpdate = (Date.now() - (line.itemChangedAt || line.startedAt)) / 1000;
            if (sinceUpdate > 90 && (line.itemIndex || 0) < line.itemTotal) {
              etaLabel += ` — ⚠ no progress in ${fmtSec(sinceUpdate)}`;
              over = true;
            }
          } else if (line.eta > 0) {
            pct = Math.min(95, (elapsed / line.eta) * 100);
            const remaining = line.eta - elapsed;
            if (remaining > 0) etaLabel = `~${fmtSec(remaining)} remaining`;
            else { etaLabel = `taking longer than expected (${fmtSec(elapsed)})`; over = true; pct = 95; }
          } else {
            pct = null;
            etaLabel = `running for ${fmtSec(elapsed)}`;
          }
          return (
            <div key={i} className="space-y-1 text-sm">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 flex-none animate-pulse rounded-full bg-primary" />{line.message}
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full rounded-full bg-primary ${pct === null ? "w-1/3 animate-pulse" : ""}`}
                  style={pct === null ? {} : { width: `${pct}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>elapsed {fmtSec(elapsed)}</span>
                <span className={over ? "text-amber-600" : ""}>{etaLabel}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
