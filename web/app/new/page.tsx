"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

// ── data (from the live order form) ──────────────────────────────────────────
const STYLES: [string, string][] = [
  ["Graphic with Text", "Illustrated graphic paired with text."],
  ["Split Screen", "Two or more photos on opposite sides paired with copy."],
  ["Us Vs Them", "Opposing views on opposite sides of layout."],
  ["Photo with Text (Upwork shell)", "Branded photography housed in Upwork border."],
  ["Lifestyle Photo (full bleed)", "Full bleed branded photography with text."],
  ["Testimonial", "User testimonial featuring brand elements such as stars or badges."],
  ["Social Media Profile", "Mockup of user social media profile."],
  ["Pie Chart", "Round graph element sliced into segments to show data."],
  ["Hybrid", "Lifestyle photography combined with branded UI elements."],
  ["Search Results", "Search bar UI showing desired results."],
  ["Search Bar with Talent Badge", "Search bar UI with branded badge elements."],
  ["Text Only", "Mostly text to convey message. May include branded background."],
  ["Chat Bubble", "Rounded chat bubble features key messaging with branded background."],
  ["Reminder", "Mobile app reminder features key messaging with branded background."],
  ["Device UI (Photo)", "Upwork UI shown on a device such as a laptop or cellphone."],
  ["Platform UI", "Upwork platform or UI highlight moment."],
  ["Meme", "Utilize a viral meme to convey key messaging."],
  ["Sticky Note", "Photo of sticky notes featuring key messaging."],
  ["Poll", "Poll chart shows variety of messaging touch points."],
  ["Tweet / Post Mockup", "Mocked up tweet or social media post."],
  ["Text with Button and Cursor", "Headline text paired with UI button and cursor pointer."],
  ["Talent Profile", "Platform talent profile(s) paired with key messaging."],
  ["Notification", "App notification features key messaging with branded background."],
  ["Bespoke", "A newly concepted design layout that must be created from scratch."],
];

type Res = { size: string; ratio: string };
const META_STATIC: Res[] = [
  { size: "1440 x 1800", ratio: "4:5" },
  { size: "1440 x 1440", ratio: "1:1" },
  { size: "1080 x 1920", ratio: "9:16" },
];

const DELIVERABLES = [
  ["images-copy", "Images & Copy", "Visual assets and written copy produced together"],
  ["images-only", "Images Only", "Visual assets without copy production"],
  ["copy-only", "Copy Only", "Written copy without image production"],
] as const;

// ── date helpers ─────────────────────────────────────────────────────────────
function addBusinessDays(from: Date, n: number) {
  const d = new Date(from);
  let added = 0;
  while (added < n) {
    d.setDate(d.getDate() + 1);
    const dow = d.getDay();
    if (dow !== 0 && dow !== 6) added++;
  }
  return d;
}
const iso = (d: Date) => d.toISOString().slice(0, 10);
const DOW = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// ── calendar ─────────────────────────────────────────────────────────────────
function Calendar({ value, onPick }: { value: string; onPick: (v: string) => void }) {
  const today = useMemo(() => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }, []);
  const minDate = useMemo(() => addBusinessDays(today, 5), [today]);
  const [view, setView] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));

  const year = view.getFullYear();
  const month = view.getMonth();
  const firstDow = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [...Array(firstDow).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];

  return (
    <div className="rounded-xl border border-[#E0E0E0] p-4">
      <div className="relative mb-3 flex items-center justify-center">
        <button
          type="button" aria-label="Previous month"
          onClick={() => setView(new Date(year, month - 1, 1))}
          className="absolute left-0 flex h-[30px] w-[30px] items-center justify-center rounded-lg border border-[#E0E0E0] text-[#5b6660] hover:bg-[#F7F8F6]"
        >‹</button>
        <span className="text-[15px]">{MONTHS[month]} {year}</span>
        <button
          type="button" aria-label="Next month"
          onClick={() => setView(new Date(year, month + 1, 1))}
          className="absolute right-0 flex h-[30px] w-[30px] items-center justify-center rounded-lg border border-[#E0E0E0] text-[#5b6660] hover:bg-[#F7F8F6]"
        >›</button>
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-center">
        {DOW.map((d) => <div key={d} className="py-1.5 text-[10px] tracking-wider text-[#9aa0a6]">{d}</div>)}
        {cells.map((day, i) => {
          if (day === null) return <div key={i} />;
          const date = new Date(year, month, day);
          const disabled = date < minDate;
          const selected = value === iso(date);
          return (
            <button
              key={i} type="button" disabled={disabled}
              onClick={() => onPick(iso(date))}
              className={[
                "rounded-[9px] py-2.5 text-sm",
                disabled ? "cursor-not-allowed text-[#D4D4D4]" : "cursor-pointer text-[#1d1d1b] hover:bg-[#F7F8F6]",
                selected ? "!bg-[#14A800] font-medium !text-white" : "",
              ].join(" ")}
            >{day}</button>
          );
        })}
      </div>
    </div>
  );
}

// ── small primitives matching the real form ──────────────────────────────────
function FieldLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-[13px] font-medium text-[#1d1d1b]">{children}<span className="text-[#14A800]"> *</span></p>;
}
function StepFoot({ children }: { children: React.ReactNode }) {
  return <div className="mt-8 flex items-center justify-between border-t border-[#ECECEC] pt-6">{children}</div>;
}

export default function NewOrderPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [done, setDone] = useState<{ [k: number]: boolean }>({});

  // step 1
  const [driver, setDriver] = useState("");
  const [aud, setAud] = useState<Set<string>>(new Set());
  const [deliveryDate, setDeliveryDate] = useState("");
  // step 2
  const [deliverable, setDeliverable] = useState<string>("");
  const [platform, setPlatform] = useState<string>("");
  const [sizes, setSizes] = useState<string[]>(META_STATIC.map((r) => r.size));
  const [styles, setStyles] = useState<string[]>([]);
  const [styleSearch, setStyleSearch] = useState("");
  const [qty, setQty] = useState(1);
  // step 3
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const needsImages = deliverable !== "" && deliverable !== "copy-only";
  const step1ok = driver.trim() && aud.size > 0 && deliveryDate;
  const step2ok =
    deliverable !== "" &&
    (!needsImages || (platform && sizes.length > 0 && styles.length > 0));

  const targeting =
    aud.has("Prospecting") && aud.has("Retargeting") ? "Prospecting and Retargeting"
      : aud.has("Prospecting") ? "Prospecting" : aud.has("Retargeting") ? "Retargeting" : "";

  function go(n: number) { setStep(n); }
  function toggle(set: React.Dispatch<React.SetStateAction<string[]>>, list: string[], v: string) {
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }
  function toggleAud(a: string) {
    setAud((prev) => { const n = new Set(prev); n.has(a) ? n.delete(a) : n.add(a); return n; });
  }

  async function submit() {
    setError(""); setBusy(true);
    const resolutions = needsImages ? META_STATIC.filter((r) => sizes.includes(r.size)) : META_STATIC;
    const chosenStyles = needsImages ? styles : ["Text Only"];
    try {
      const res = await fetch("/api/submit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          driver, brief, targeting, deliverable,
          styles: chosenStyles,
          sizes: resolutions, quantity: qty, deliveryDate,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Submit failed");
      router.push(`/sprints/${data.sprint_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed"); setBusy(false);
    }
  }

  const stepTabs: [number, string, string][] = [[1, "Step 01", "Details"], [2, "Step 02", "Creative"], [3, "Step 03", "Review"]];
  const filteredStyles = STYLES.filter(([n, d]) =>
    !styleSearch || (n + d).toLowerCase().includes(styleSearch.toLowerCase()));

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mt-2 mb-8 text-[52px] font-semibold leading-[0.98] tracking-tight">
        Ad Creative<span className="block text-[#9aa0a6]">Request</span>
      </h1>

      <div className="overflow-hidden rounded-[20px] border border-[#ECECEC] bg-white shadow-[0_2px_4px_rgba(0,0,0,.04),0_10px_28px_rgba(0,0,0,.07)]">
        {/* step tabs */}
        <div className="grid grid-cols-3 border-b border-[#ECECEC]">
          {stepTabs.map(([n, num, label]) => {
            const active = step === n;
            const isDone = done[n];
            const disabled = (n === 2 && !step1ok) || (n === 3 && !(step1ok && step2ok));
            return (
              <button
                key={n} type="button" disabled={disabled}
                onClick={() => !disabled && go(n)}
                className={[
                  "flex items-center gap-3 border-b-2 px-6 py-5 text-left",
                  active ? "border-[#14A800]" : "border-transparent",
                  disabled ? "cursor-not-allowed" : "cursor-pointer",
                ].join(" ")}
              >
                <span className={[
                  "flex h-5 w-5 flex-none items-center justify-center rounded-full border-[1.5px] text-[11px] text-white",
                  isDone ? "border-[#14A800] bg-[#14A800]" : active ? "border-[#14A800]" : "border-[#E0E0E0]",
                ].join(" ")}>{isDone ? "✓" : ""}</span>
                <span>
                  <span className={["block text-[10px] uppercase tracking-[0.14em]", active ? "text-[#14A800]" : "text-[#9aa0a6]"].join(" ")}>{num}</span>
                  <span className={["text-[15px]", active ? "font-medium text-[#1d1d1b]" : "text-[#5b6660]"].join(" ")}>{label}</span>
                </span>
              </button>
            );
          })}
        </div>

        {/* STEP 1 */}
        {step === 1 && (
          <div className="p-8">
            <div className="grid gap-8 md:grid-cols-2">
              <div>
                <FieldLabel>Your Name</FieldLabel>
                <input
                  value={driver} onChange={(e) => setDriver(e.target.value)} placeholder="Full name"
                  className="w-full rounded-lg border border-[#E0E0E0] px-3.5 py-2.5 text-sm outline-none focus:border-[#14A800]"
                />
                <p className="mb-2 mt-6 text-[13px] font-medium text-[#1d1d1b]">Audience<span className="text-[#14A800]"> *</span></p>
                <div className="flex flex-wrap gap-3.5">
                  {["Prospecting", "Retargeting"].map((a) => {
                    const on = aud.has(a);
                    return (
                      <button
                        key={a} type="button" onClick={() => toggleAud(a)}
                        className={[
                          "flex items-center gap-2.5 rounded-full border px-4 py-2.5 text-sm",
                          on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] bg-white hover:bg-[#F7F8F6]",
                        ].join(" ")}
                      >
                        <span className={["h-4 w-4 flex-none rounded-full border-[1.5px]", on ? "border-[#14A800] bg-[#14A800] shadow-[inset_0_0_0_3px_#fff]" : "border-[#E0E0E0]"].join(" ")} />
                        {a}
                      </button>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-[#9aa0a6]">Select one or both</p>
              </div>
              <div>
                <div className="flex items-baseline justify-between">
                  <FieldLabel>Delivery Date</FieldLabel>
                  <span className="text-xs text-[#9aa0a6]">5 business days minimum</span>
                </div>
                <Calendar value={deliveryDate} onPick={setDeliveryDate} />
              </div>
            </div>
            <StepFoot>
              <span />
              <button
                type="button" disabled={!step1ok}
                onClick={() => { setDone((d) => ({ ...d, 1: true })); go(2); }}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-[#14A800] text-lg text-white disabled:cursor-not-allowed disabled:bg-[#E0E0E0]"
              >→</button>
            </StepFoot>
          </div>
        )}

        {/* STEP 2 */}
        {step === 2 && (
          <div className="p-8">
            <h3 className="mb-4 text-[15px] font-semibold">What are you requesting?</h3>
            <div className="grid gap-3.5 sm:grid-cols-3">
              {DELIVERABLES.map(([id, ttl, sub]) => {
                const on = deliverable === id;
                return (
                  <button
                    key={id} type="button"
                    onClick={() => { setDeliverable(id); if (id === "copy-only") setPlatform(""); }}
                    className={["rounded-xl border p-4 text-left", on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] hover:bg-[#F7F8F6]"].join(" ")}
                  >
                    <div className="text-sm font-semibold">{ttl}</div>
                    <div className="mt-1 text-xs text-[#5b6660]">{sub}</div>
                  </button>
                );
              })}
            </div>

            {needsImages && (
              <div className="mt-7">
                <div className="mb-3 flex items-baseline justify-between">
                  <h3 className="text-[15px] font-semibold">Platform</h3>
                  <span className="text-xs text-[#9aa0a6]">One platform per request</span>
                </div>
                <div className="grid gap-3.5 sm:grid-cols-3">
                  {["Meta"].map((p) => {
                    const on = platform === p;
                    return (
                      <button
                        key={p} type="button" onClick={() => setPlatform(p)}
                        className={["rounded-xl border p-4 text-left", on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] hover:bg-[#F7F8F6]"].join(" ")}
                      >
                        <div className="text-sm font-semibold">{p}</div>
                        <div className="mt-1 text-xs text-[#5b6660]">Static · 3 sizes</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {needsImages && platform && (
              <>
                <div className="mt-7">
                  <h3 className="mb-3 text-[15px] font-semibold">Ad Formats <span className="text-xs font-normal text-[#9aa0a6]">Meta · Static Feed</span></h3>
                  <div className="flex flex-wrap gap-3.5">
                    {META_STATIC.map((r) => {
                      const on = sizes.includes(r.size);
                      return (
                        <button
                          key={r.size} type="button" onClick={() => toggle(setSizes, sizes, r.size)}
                          className={["rounded-full border px-4 py-2 text-sm", on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] hover:bg-[#F7F8F6]"].join(" ")}
                        >{r.ratio} <span className="text-[#9aa0a6]">({r.size})</span></button>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-7">
                  <div className="mb-3 flex items-baseline justify-between">
                    <h3 className="text-[15px] font-semibold">Styles <span className="text-xs font-normal text-[#9aa0a6]">{styles.length} selected</span></h3>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-[#5b6660]">Qty / style</span>
                      <input type="number" min={1} max={10} value={qty}
                        onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                        className="w-14 rounded-lg border border-[#E0E0E0] px-2 py-1.5 text-center" />
                    </div>
                  </div>
                  <div className="mb-3 flex items-center gap-2 rounded-lg border border-[#E0E0E0] px-3 py-2 text-sm">
                    <span className="text-[#9aa0a6]">⌕</span>
                    <input value={styleSearch} onChange={(e) => setStyleSearch(e.target.value)} placeholder="Search styles…" className="w-full outline-none" />
                  </div>
                  <div className="grid max-h-72 grid-cols-1 gap-x-6 gap-y-2 overflow-y-auto sm:grid-cols-2">
                    {filteredStyles.map(([name, desc]) => {
                      const on = styles.includes(name);
                      return (
                        <button
                          key={name} type="button" onClick={() => toggle(setStyles, styles, name)}
                          className={["flex items-start gap-3 rounded-lg border p-3 text-left", on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#ECECEC] hover:bg-[#F7F8F6]"].join(" ")}
                        >
                          <span className={["mt-0.5 flex h-4 w-4 flex-none items-center justify-center rounded border text-[10px] text-white", on ? "border-[#14A800] bg-[#14A800]" : "border-[#E0E0E0]"].join(" ")}>{on ? "✓" : ""}</span>
                          <span>
                            <span className="block text-sm font-medium">{name}</span>
                            <span className="block text-xs text-[#9aa0a6]">{desc}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            <StepFoot>
              <button type="button" onClick={() => go(1)} className="rounded-full border border-[#E0E0E0] px-4 py-2 text-sm hover:bg-[#F7F8F6]">← Back</button>
              <button
                type="button" disabled={!step2ok}
                onClick={() => { setDone((d) => ({ ...d, 2: true })); go(3); }}
                className="rounded-full bg-[#14A800] px-5 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#E0E0E0]"
              >Review Request →</button>
            </StepFoot>
          </div>
        )}

        {/* STEP 3 */}
        {step === 3 && (
          <div className="p-8">
            <h3 className="text-[15px] font-semibold">Add your creative context</h3>
            <p className="mb-3 mt-1 text-xs text-[#9aa0a6]">The single biggest lever on output quality. The more direction you give, the sharper the work comes back.</p>
            <textarea
              value={brief} onChange={(e) => setBrief(e.target.value)} rows={5}
              placeholder="Include copy guidance, context, CTAs, destination URLs, tone, must-haves, things to avoid, reference links — anything that helps the team nail it."
              className="w-full rounded-lg border border-[#E0E0E0] p-3.5 text-sm outline-none focus:border-[#14A800]"
            />

            <h3 className="mb-3 mt-7 text-[15px] font-semibold">Your request</h3>
            <div className="rounded-xl border border-[#ECECEC] bg-[#F7F8F6] p-4 text-sm">
              {[
                ["Name", driver], ["Audience", targeting], ["Delivery", deliveryDate],
                ["Deliverable", { "images-copy": "Images & Copy", "images-only": "Images Only", "copy-only": "Copy Only" }[deliverable] || deliverable],
                ...(needsImages ? [["Platform", platform], ["Sizes", META_STATIC.filter((r) => sizes.includes(r.size)).map((r) => r.ratio).join(", ")], ["Styles", styles.join(", ")]] : []),
              ].map(([k, v]) => (
                <div key={k as string} className="flex justify-between gap-6 border-b border-[#ECECEC] py-1.5 last:border-0">
                  <span className="text-[#9aa0a6]">{k}</span>
                  <span className="text-right font-medium">{v || "—"}</span>
                </div>
              ))}
            </div>

            <StepFoot>
              <button type="button" onClick={() => go(2)} className="rounded-full border border-[#E0E0E0] px-4 py-2 text-sm hover:bg-[#F7F8F6]">← Back</button>
              <div className="flex items-center gap-4">
                {error && <span className="text-sm text-red-600">{error}</span>}
                <button
                  type="button" onClick={submit} disabled={busy}
                  className="rounded-full bg-[#14A800] px-6 py-2.5 text-sm font-medium text-white disabled:bg-[#E0E0E0]"
                >{busy ? "Submitting…" : "Submit Request"}</button>
              </div>
            </StepFoot>
          </div>
        )}
      </div>
    </div>
  );
}
