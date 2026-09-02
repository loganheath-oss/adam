"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { STYLE_THUMBS } from "@/lib/style-thumbs";

// ── data (verbatim from the live order form) ─────────────────────────────────
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

// Key messaging themes Paid Acq can drop into the Brief (→ Additional_Info) so the
// current sprint's angle guides copy generation. Data-driven — add the next sprint's
// theme here and it re-appears as an insert chip; the chip row hides when empty.
// Emptied 2026-07-23 (Adrie): the leftover "Sprint 9" chip confused the intake; add a
// real, current sprint theme here only when one is meant to be live.
type MessagingTheme = { id: string; title: string; subtitle: string; content: string };

const KEY_MESSAGING_THEMES: MessagingTheme[] = [];

// A fill-in skeleton whose four sections map 1:1 to how ADAM breaks a brief down
// (theme / copy_directives / design_directives / resources — see _breakdown_brief in
// run_pipeline.py). Using these exact headers makes the breakdown near-deterministic, so
// Adrie's key messaging lands where she intends instead of being inferred. Quantity, ad
// sizes, and Prospecting/Retargeting are set by the form fields above — deliberately NOT
// here (the breakdown ignores structure decisions in the brief by design).
const BRIEF_TEMPLATE = `THEME
(One or two sentences — the single core message or angle every ad should lead with.)

COPY MUST-DOs
- (A required phrase, claim to feature, tone note, or do/don't. Remove this line if none.)

DESIGN DIRECTION
- (A visual, style, or ad-format cue for the image stage. Remove this line if none.)

RESOURCES
- (A reference link, doc, or example asset. Remove this line if none.)`;

type Resolution = { size: string; ratio: string; label?: string };
type Format = { carousel: boolean; resolutions: Resolution[] };
type PlatformDef = { desc: string; formats: Record<string, Format> };

const PLATFORMS: Record<string, PlatformDef> = {
  Meta: {
    desc: "3 formats · Static, Motion, Carousel",
    formats: {
      Static: { carousel: false, resolutions: [{ size: "1440 x 1800", ratio: "4:5" }, { size: "1440 x 1440", ratio: "1:1" }, { size: "1080 x 1920", ratio: "9:16" }] },
      Motion: { carousel: false, resolutions: [{ size: "1440 x 1800", ratio: "4:5" }, { size: "1440 x 1440", ratio: "1:1" }, { size: "1080 x 1920", ratio: "9:16" }] },
      Carousel: { carousel: true, resolutions: [{ size: "1080 x 1620", ratio: "2:3" }, { size: "1080 x 1080", ratio: "1:1" }] },
    },
  },
  LinkedIn: {
    desc: "3 formats · Single Image, Dynamic Spotlight, Carousel",
    formats: {
      "Single Image": { carousel: false, resolutions: [{ size: "1200 x 1200", ratio: "1:1" }] },
      "Dynamic Spotlight": { carousel: false, resolutions: [{ size: "100 x 100", ratio: "1:1", label: "Logo" }] },
      Carousel: { carousel: true, resolutions: [{ size: "1080 x 1080", ratio: "1:1" }] },
    },
  },
  Reddit: {
    desc: "1 format · Image Feed — 2 sizes",
    formats: { "Image Feed": { carousel: false, resolutions: [{ size: "1440 x 1080", ratio: "4:3" }, { size: "1080 x 1350", ratio: "4:5" }] } },
  },
  YouTube: {
    desc: "2 formats · Static Image, Carousel",
    formats: {
      Image: { carousel: false, resolutions: [{ size: "1200 x 1200", ratio: "1:1" }, { size: "1200 x 628", ratio: "~1.91:1" }, { size: "960 x 1200", ratio: "4:5", label: "Optional" }, { size: "1080 x 1920", ratio: "9:16", label: "Optional" }] },
      Carousel: { carousel: true, resolutions: [{ size: "1200 x 1200", ratio: "1:1" }, { size: "1200 x 628", ratio: "~1.91:1" }, { size: "960 x 1200", ratio: "4:5" }] },
    },
  },
  "3rd Party / Affiliate": {
    desc: "1 format · 4 display ad sizes",
    formats: { "Display Ads": { carousel: false, resolutions: [{ size: "1200 x 1200", ratio: "1:1" }, { size: "970 x 250", ratio: "~3.88:1" }, { size: "970 x 90", ratio: "~10.8:1" }, { size: "300 x 250", ratio: "6:5" }] } },
  },
  "Google / Bing": {
    desc: "3 formats · Display, Performance Max, SEM",
    formats: {
      Display: { carousel: false, resolutions: [{ size: "1200 x 1200", ratio: "1:1", label: "Square Logo" }, { size: "1200 x 628", ratio: "~1.91:1" }, { size: "960 x 1200", ratio: "4:5" }] },
      "Performance Max": { carousel: false, resolutions: [{ size: "1200 x 1200", ratio: "1:1", label: "Square Logo" }, { size: "1200 x 628", ratio: "~1.91:1" }, { size: "960 x 1200", ratio: "4:5" }, { size: "1200 x 300", ratio: "4:1", label: "Horizontal Logo" }] },
      SEM: { carousel: false, resolutions: [{ size: "1200 x 1200", ratio: "1:1" }, { size: "1200 x 628", ratio: "~1.91:1" }] },
    },
  },
};

const DELIVERABLES = [
  ["images-copy", "Images & Copy", "Visual assets and written copy produced together"],
  ["images-only", "Images Only", "Visual assets without copy production"],
  ["copy-only", "Copy Only", "Written copy without image production"],
] as const;

// ── date helpers ─────────────────────────────────────────────────────────────
function addBusinessDays(from: Date, n: number) {
  const d = new Date(from);
  let added = 0;
  while (added < n) { d.setDate(d.getDate() + 1); const dow = d.getDay(); if (dow !== 0 && dow !== 6) added++; }
  return d;
}
const iso = (d: Date) => d.toISOString().slice(0, 10);
const DOW = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function Calendar({ value, onPick }: { value: string; onPick: (v: string) => void }) {
  const today = useMemo(() => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }, []);
  const minDate = useMemo(() => addBusinessDays(today, 5), [today]);
  const [view, setView] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const year = view.getFullYear(); const month = view.getMonth();
  const firstDow = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [...Array(firstDow).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
  return (
    <div className="rounded-xl border border-[#E0E0E0] p-4">
      <div className="relative mb-3 flex items-center justify-center">
        <button type="button" aria-label="Previous month" onClick={() => setView(new Date(year, month - 1, 1))} className="absolute left-0 flex h-8 w-8 items-center justify-center text-lg text-[#5b6660] hover:text-[#1d1d1b]">‹</button>
        <span className="text-[15px]">{MONTHS[month]} {year}</span>
        <button type="button" aria-label="Next month" onClick={() => setView(new Date(year, month + 1, 1))} className="absolute right-0 flex h-8 w-8 items-center justify-center text-lg text-[#5b6660] hover:text-[#1d1d1b]">›</button>
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-center">
        {DOW.map((d) => <div key={d} className="py-1.5 text-[10px] tracking-wider text-[#9aa0a6]">{d}</div>)}
        {cells.map((day, i) => {
          if (day === null) return <div key={i} />;
          const date = new Date(year, month, day);
          const dow = date.getDay();
          const disabled = date < minDate || dow === 0 || dow === 6; const selected = value === iso(date);
          return (
            <button key={i} type="button" disabled={disabled} onClick={() => onPick(iso(date))} className={["rounded-[9px] py-2.5 text-sm", disabled ? "cursor-not-allowed text-[#D4D4D4]" : "cursor-pointer text-[#1d1d1b] hover:bg-[#F7F8F6]", selected ? "!bg-[#14A800] font-medium !text-white" : ""].join(" ")}>{day}</button>
          );
        })}
      </div>
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-[13px] font-medium text-[#1d1d1b]">{children}<span className="text-[#14A800]"> *</span></p>;
}

type StyleRow = { style: string; qty: number };
type Batch = { styles: StyleRow[]; res: boolean[]; slides: number };

export default function NewOrderPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [done, setDone] = useState<{ [k: number]: boolean }>({});
  const [driver, setDriver] = useState("");
  // Default to BOTH audiences selected (matches Ravi's reference — the common case is
  // Prospecting + Retargeting; the operator can deselect one).
  const [aud, setAud] = useState<Set<string>>(new Set(["Prospecting", "Retargeting"]));
  const [deliveryDate, setDeliveryDate] = useState("");
  const [deliverable, setDeliverable] = useState("");
  const [platform, setPlatform] = useState("");
  const [batches, setBatches] = useState<Record<string, Batch>>({});
  const [picker, setPicker] = useState<{ fmt: string; row: number } | null>(null);
  const [search, setSearch] = useState("");
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const needsImages = deliverable !== "" && deliverable !== "copy-only";
  const step1ok = driver.trim() && aud.size > 0 && deliveryDate;
  const anyStyleChosen = Object.values(batches).some((b) => b.styles.some((s) => s.style));
  const step2ok = deliverable !== "" && (!needsImages || (!!platform && Object.keys(batches).length > 0 && anyStyleChosen));
  const targeting = aud.has("Prospecting") && aud.has("Retargeting") ? "Prospecting and Retargeting" : aud.has("Prospecting") ? "Prospecting" : aud.has("Retargeting") ? "Retargeting" : "";

  function toggleAud(a: string) { setAud((p) => { const n = new Set(p); n.has(a) ? n.delete(a) : n.add(a); return n; }); }
  function pickPlatform(p: string) { setPlatform(p); setBatches({}); }
  function toggleFormat(fmt: string) {
    setBatches((prev) => {
      const next = { ...prev };
      if (next[fmt]) delete next[fmt];
      else next[fmt] = { styles: [{ style: "", qty: 1 }], res: PLATFORMS[platform].formats[fmt].resolutions.map(() => true), slides: 3 };
      return next;
    });
  }
  function updateBatch(fmt: string, fn: (b: Batch) => Batch) { setBatches((prev) => ({ ...prev, [fmt]: fn(prev[fmt]) })); }
  function chooseStyle(name: string) {
    if (picker) updateBatch(picker.fmt, (b) => { const s = [...b.styles]; s[picker.row] = { ...s[picker.row], style: name }; return { ...b, styles: s }; });
    setPicker(null); setSearch("");
  }

  async function submit() {
    // Empty-brief guard BEFORE the busy flag: with the confirm inside the busy
    // section, pressing Cancel returned early with busy=true and the form sat
    // on "Submitting…" forever (Adrie's changelog item 5, Aug 2026).
    if (!brief.trim() && !window.confirm(
      "No brief provided.\n\nADAM will write copy from the standing reference docs only — no sprint theme, no key messaging.\n\nSubmit without a brief?"
    )) return;
    setError(""); setBusy(true);
    const orderBatches = needsImages
      ? Object.entries(batches).map(([fmt, b]) => {
          const fd = PLATFORMS[platform].formats[fmt];
          const styles = b.styles.filter((s) => s.style);
          const resolutions = fd.resolutions.filter((_, i) => b.res[i]);
          return {
            platform, format: fmt, quantity: styles.reduce((n, s) => n + s.qty, 0),
            styles, visual_styles: styles.map((s) => s.style),
            style_quantities: styles.reduce<Record<string, number>>((a, s) => { a[s.style] = (a[s.style] || 0) + s.qty; return a; }, {}),
            resolutions, carousel: fd.carousel, carousel_slides: fd.carousel ? b.slides : null,
          };
        }).filter((b) => b.visual_styles.length)
      : [];
    const order = { delivery_date: deliveryDate, driver, targeting, deliverable, platform: platform || null, batches: orderBatches, brief };
    try {
      const res = await fetch("/api/submit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(order) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Submit failed");
      router.push(`/sprints/${data.sprint_id}/handoff`);
    } catch (e) { setError(e instanceof Error ? e.message : "Submit failed"); setBusy(false); }
  }

  const stepTabs: [number, string][] = [[1, "Details"], [2, "Creative"], [3, "Review"]];
  const filtered = STYLES.filter(([n, d]) => !search || (n + d).toLowerCase().includes(search.toLowerCase()));

  const totalAssets = needsImages
    ? Object.entries(batches).reduce((sum, [fmt, b]) => {
        const sizeCount = PLATFORMS[platform].formats[fmt].resolutions.filter((_, i) => b.res[i]).length;
        return sum + b.styles.filter((s) => s.style).reduce((n, s) => n + s.qty * sizeCount, 0);
      }, 0)
    : 0;
  const creativeCount = Object.values(batches).reduce((n, b) => n + b.styles.filter((s) => s.style).length, 0);
  const summaryRows: [string, string][] = [
    ["Requested by", driver],
    ["Audience", targeting],
    ["Delivery date", deliveryDate],
    ["Deliverable", { "images-copy": "Images & Copy", "images-only": "Images Only", "copy-only": "Copy Only" }[deliverable] || deliverable],
    ...(platform ? [["Platform", platform] as [string, string]] : []),
  ];

  return (
    <div>
      <div className="mb-8 mt-2 flex items-end justify-between">
        <h1 className="text-4xl font-medium tracking-tight text-[#0a0a0a]">New Order</h1>
        <span className="text-sm text-muted-foreground">Step {step} of 3</span>
      </div>

      <div className="overflow-hidden rounded-[20px] border border-[#ECECEC] bg-white elevate-2">
        <div className="grid grid-cols-3 divide-x divide-[#F0F0F0] border-b border-[#ECECEC]">
          {stepTabs.map(([n, label]) => {
            const active = step === n; const isDone = done[n];
            const disabled = (n === 2 && !step1ok) || (n === 3 && !(step1ok && step2ok));
            return (
              <button key={n} type="button" disabled={disabled} onClick={() => !disabled && setStep(n)} className={["flex items-center justify-center gap-2.5 border-b-2 px-6 py-5 text-center", active ? "border-b-[#14A800]" : "border-b-transparent", disabled ? "cursor-not-allowed" : "cursor-pointer"].join(" ")}>
                <span className={["flex h-6 w-6 flex-none items-center justify-center rounded-full text-[12px] font-medium", isDone ? "bg-[#14A800] text-white" : active ? "border-2 border-[#14A800] text-[#14A800]" : "border border-[#E0E0E0] text-[#9aa0a6]"].join(" ")}>{isDone ? "✓" : n}</span>
                <span className={["text-[15px]", active ? "font-medium text-[#1d1d1b]" : "text-[#5b6660]"].join(" ")}>{label}</span>
              </button>
            );
          })}
        </div>

        <div key={step} className="animate-in fade-in-0 slide-in-from-bottom-1 duration-300">
        {step === 1 && (
          <div className="p-8">
            <div className="grid gap-8 md:grid-cols-2">
              <div>
                <FieldLabel>Requested by</FieldLabel>
                <input value={driver} onChange={(e) => setDriver(e.target.value)} placeholder="Your name" className="w-full rounded-lg border border-[#E0E0E0] px-3.5 py-2.5 text-sm outline-none focus:border-[#14A800]" />
                <p className="mb-2 mt-6 text-[13px] font-medium text-[#1d1d1b]">Audience<span className="text-[#14A800]"> *</span></p>
                <div className="flex flex-wrap gap-3.5">
                  {["Prospecting", "Retargeting"].map((a) => {
                    const on = aud.has(a);
                    return (
                      <button key={a} type="button" onClick={() => toggleAud(a)} className={["flex items-center gap-2.5 rounded-full border px-4 py-2.5 text-sm", on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] bg-white hover:bg-[#F7F8F6]"].join(" ")}>
                        <span className={["flex h-4 w-4 flex-none items-center justify-center rounded-full text-[9px] text-white", on ? "bg-[#14A800]" : "border-[1.5px] border-[#E0E0E0]"].join(" ")}>{on ? "✓" : ""}</span>{a}
                      </button>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-[#9aa0a6]">Select one or both</p>
              </div>
              <div>
                <FieldLabel>Delivery date</FieldLabel>
                <Calendar value={deliveryDate} onPick={setDeliveryDate} />
                <p className="mt-3 text-center text-xs text-[#9aa0a6]">Weekdays only, 5 business days out minimum.</p>
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="p-8">
            <h3 className="mb-4 text-[15px] font-semibold">What are you requesting?</h3>
            <div className="grid gap-3.5 sm:grid-cols-3">
              {DELIVERABLES.map(([id, ttl, sub]) => {
                const on = deliverable === id;
                return (
                  <button key={id} type="button" onClick={() => { setDeliverable(id); if (id === "copy-only") { setPlatform(""); setBatches({}); } }} className={["rounded-xl border p-4 text-left", on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] hover:bg-[#F7F8F6]"].join(" ")}>
                    <div className="text-sm font-semibold">{ttl}</div><div className="mt-1 text-xs text-[#5b6660]">{sub}</div>
                  </button>
                );
              })}
            </div>

            {needsImages && (
              <div className="mt-7">
                <div className="mb-3 flex items-baseline justify-between"><h3 className="text-[15px] font-semibold">Platform</h3><span className="text-xs text-[#9aa0a6]">One platform per request</span></div>
                <div className="grid gap-3.5 sm:grid-cols-3">
                  {Object.entries(PLATFORMS).map(([p, pd]) => {
                    const on = platform === p;
                    return (
                      <button key={p} type="button" onClick={() => pickPlatform(p)} className={["rounded-xl border p-4 text-left", on ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] hover:bg-[#F7F8F6]"].join(" ")}>
                        <div className="text-sm font-semibold">{p}</div><div className="mt-1 text-xs text-[#5b6660]">{pd.desc}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {needsImages && platform && (
              <div className="mt-7">
                <div className="mb-3 flex items-baseline justify-between"><h3 className="text-[15px] font-semibold">Ad Formats</h3><span className="text-xs text-[#9aa0a6]">{platform}</span></div>
                <div className="space-y-3">
                  {Object.entries(PLATFORMS[platform].formats).map(([fmt, fd]) => {
                    const b = batches[fmt]; const on = !!b;
                    return (
                      <div key={fmt} className={["rounded-xl border", on ? "border-[#14A800]" : "border-[#E0E0E0]"].join(" ")}>
                        <button type="button" onClick={() => toggleFormat(fmt)} className="flex w-full items-center gap-3 p-4 text-left">
                          <span className={["flex h-5 w-5 flex-none items-center justify-center rounded border text-[11px] text-white", on ? "border-[#14A800] bg-[#14A800]" : "border-[#E0E0E0]"].join(" ")}>{on ? "✓" : ""}</span>
                          <span><span className="block text-sm font-medium">{fmt}</span><span className="block text-xs text-[#9aa0a6]">{fd.resolutions.map((r) => `${r.ratio} · ${r.size}`).join("   ·   ")}</span></span>
                        </button>
                        {on && (
                          <div className="space-y-4 border-t border-[#ECECEC] bg-[#FafcFa] p-4">
                            <div>
                              <p className="mb-2 text-[13px] font-medium">Visual Style<span className="text-[#14A800]"> *</span></p>
                              <div className="space-y-2">
                                {b.styles.map((sr, i) => (
                                  <div key={i} className="flex items-center gap-2">
                                    <button type="button" onClick={() => setPicker({ fmt, row: i })} className={["flex flex-1 items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm", sr.style ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] bg-white hover:bg-[#F7F8F6]"].join(" ")}>
                                      {sr.style && STYLE_THUMBS[sr.style] ? (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img src={STYLE_THUMBS[sr.style]} alt="" className="h-6 w-6 flex-none rounded object-cover" />
                                      ) : (
                                        <span className="text-[#9aa0a6]">▣</span>
                                      )}
                                      <span className={sr.style ? "font-medium" : "text-[#9aa0a6]"}>{sr.style || "Choose a visual style"}</span>
                                      <span className="ml-auto text-xs text-[#14A800]">Browse</span>
                                    </button>
                                    <input type="number" min={1} value={sr.qty} onChange={(e) => updateBatch(fmt, (bb) => { const s = [...bb.styles]; s[i] = { ...s[i], qty: Math.max(1, Number(e.target.value) || 1) }; return { ...bb, styles: s }; })} className="w-14 rounded-lg border border-[#E0E0E0] px-2 py-2 text-center text-sm" />
                                    {b.styles.length > 1 && (<button type="button" onClick={() => updateBatch(fmt, (bb) => ({ ...bb, styles: bb.styles.filter((_, j) => j !== i) }))} className="px-1 text-[#9aa0a6] hover:text-[#1d1d1b]">✕</button>)}
                                  </div>
                                ))}
                              </div>
                              <button type="button" onClick={() => updateBatch(fmt, (bb) => ({ ...bb, styles: [...bb.styles, { style: "", qty: 1 }] }))} className="mt-2 text-sm text-[#14A800]">+ Add Style</button>
                            </div>
                            {fd.carousel && (
                              <div className="flex items-center gap-3">
                                <p className="text-[13px] font-medium">Images per carousel<span className="text-[#14A800]"> *</span></p>
                                <input type="number" min={2} max={10} value={b.slides} onChange={(e) => updateBatch(fmt, (bb) => ({ ...bb, slides: Math.min(10, Math.max(2, Number(e.target.value) || 2)) }))} className="w-16 rounded-lg border border-[#E0E0E0] px-2 py-1.5 text-center text-sm" />
                                <span className="text-xs text-[#9aa0a6]">2 – 10 images per carousel</span>
                              </div>
                            )}
                            <div>
                              <p className="mb-1 text-[13px] font-medium">Resolutions</p>
                              <p className="mb-2 text-xs text-[#9aa0a6]">Uncheck any size to exclude it from this batch</p>
                              <div className="flex flex-wrap gap-2">
                                {fd.resolutions.map((r, i) => {
                                  const checked = b.res[i];
                                  return (
                                    <button key={i} type="button" onClick={() => updateBatch(fmt, (bb) => { const res = [...bb.res]; res[i] = !res[i]; return { ...bb, res }; })} className={["flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm", checked ? "border-[#14A800] bg-[#F4FAF1]" : "border-[#E0E0E0] text-[#9aa0a6]"].join(" ")}>
                                      <span className={["flex h-4 w-4 items-center justify-center rounded border text-[9px] text-white", checked ? "border-[#14A800] bg-[#14A800]" : "border-[#E0E0E0]"].join(" ")}>{checked ? "✓" : ""}</span>
                                      {r.ratio} <span className="text-[#9aa0a6]">{r.size}</span>{r.label && <span className="text-[#9aa0a6]">· {r.label}</span>}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

          </div>
        )}

        {step === 3 && (
          <div className="p-8">
            <div className="mb-1 flex items-center gap-2">
              <h3 className="text-[15px] font-semibold">Brief</h3>
              <span className="rounded-full bg-[#F0F0F0] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#9aa0a6]">Optional</span>
            </div>
            <p className="mb-3 text-xs text-[#9aa0a6]">Add campaign context, a key message, or must-includes — or leave it blank and submit. Insert the template below to structure it so ADAM routes each part where you intend.</p>
            <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={brief.includes("THEME") ? 12 : 4} placeholder="Campaign context, key message, must-includes…" className="w-full rounded-lg border border-[#E0E0E0] p-3.5 text-sm outline-none focus:border-[#14A800]" />

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() =>
                  setBrief((b) => (b.includes("THEME") ? b : b.trim() ? `${b.trim()}\n\n${BRIEF_TEMPLATE}` : BRIEF_TEMPLATE))
                }
                disabled={brief.includes("THEME")}
                className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                  brief.includes("THEME")
                    ? "cursor-default border-[#14A800] bg-[#14A800]/10 text-[#108A00]"
                    : "border-[#E0E0E0] bg-white hover:border-[#14A800] hover:text-[#108A00]"
                }`}
              >
                {brief.includes("THEME") ? "✓ Template inserted" : "+ Insert brief template"}
              </button>
              <span className="text-xs text-[#9aa0a6]">Theme · Copy must-dos · Design direction · Resources — the four things ADAM reads.</span>
            </div>


            {KEY_MESSAGING_THEMES.length > 0 && (
              <div className="mt-3 rounded-lg border border-[#ECECEC] bg-[#FAFBFA] p-3.5">
                <p className="mb-2 text-xs font-medium text-[#5f6368]">
                  Key messaging themes{" "}
                  <span className="font-normal text-[#9aa0a6]">— insert a current sprint theme to guide the copy</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  {KEY_MESSAGING_THEMES.map((t) => {
                    const used = brief.includes(t.content);
                    return (
                      <button
                        key={t.id}
                        type="button"
                        title={t.subtitle}
                        onClick={() =>
                          setBrief((b) => (used ? b : b.trim() ? `${b.trim()}\n\n${t.content}` : t.content))
                        }
                        className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                          used
                            ? "border-[#14A800] bg-[#14A800]/10 text-[#108A00]"
                            : "border-[#E0E0E0] bg-white hover:border-[#14A800] hover:text-[#108A00]"
                        }`}
                      >
                        {used ? "✓ " : "+ "}
                        {t.title}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <h3 className="mb-2 mt-8 text-[15px] font-semibold">Order summary</h3>
            <div className="grid gap-x-12 sm:grid-cols-2">
              {summaryRows.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-6 border-b border-[#ECECEC] py-2.5 text-sm">
                  <span className="text-[#9aa0a6]">{k}</span><span className="text-right font-medium">{v || "—"}</span>
                </div>
              ))}
            </div>

            {needsImages && (
              <>
                <div className="mb-3 mt-8 flex items-baseline justify-between">
                  <h3 className="text-[15px] font-semibold">Your creatives</h3>
                  <span className="text-xs text-[#9aa0a6]">{creativeCount} item{creativeCount !== 1 ? "s" : ""}</span>
                </div>
                <div className="space-y-3">
                  {Object.entries(batches).flatMap(([fmt, b]) => {
                    const fd = PLATFORMS[platform].formats[fmt];
                    const sizes = fd.resolutions.filter((_, i) => b.res[i]);
                    return b.styles.map((sr, i) => (sr.style ? (
                      <div key={fmt + "-" + i} className="flex items-start gap-4 rounded-xl border border-[#ECECEC] p-3">
                        {STYLE_THUMBS[sr.style] ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={STYLE_THUMBS[sr.style]} alt="" className="h-20 w-20 flex-none rounded-lg object-cover" />
                        ) : (
                          <div className="h-20 w-20 flex-none rounded-lg bg-[#F4FAF1]" />
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium">{sr.style}</div>
                          <div className="text-xs text-[#9aa0a6]">{platform} · {fmt}</div>
                          <div className="mt-3 flex items-center gap-2">
                            <span className="text-[11px] uppercase tracking-wide text-[#9aa0a6]">Qty</span>
                            <div className="flex items-center rounded-full border border-[#E0E0E0]">
                              <button type="button" onClick={() => updateBatch(fmt, (bb) => { const s = [...bb.styles]; s[i] = { ...s[i], qty: Math.max(1, s[i].qty - 1) }; return { ...bb, styles: s }; })} className="flex h-7 w-7 items-center justify-center text-[#5b6660] hover:text-[#1d1d1b]">−</button>
                              <span className="w-8 text-center text-sm tabular-nums">{sr.qty}</span>
                              <button type="button" onClick={() => updateBatch(fmt, (bb) => { const s = [...bb.styles]; s[i] = { ...s[i], qty: s[i].qty + 1 }; return { ...bb, styles: s }; })} className="flex h-7 w-7 items-center justify-center text-[#5b6660] hover:text-[#1d1d1b]">+</button>
                            </div>
                          </div>
                          <div className="mt-3 flex flex-wrap items-center gap-1.5">
                            <span className="mr-1 text-[11px] uppercase tracking-wide text-[#9aa0a6]">Sizes</span>
                            {sizes.map((r) => (
                              <span key={r.size} className="rounded-md bg-[#14A800] px-2 py-1 text-[11px] font-medium text-white">{r.size}</span>
                            ))}
                          </div>
                        </div>
                        <button type="button" aria-label="Remove" onClick={() => updateBatch(fmt, (bb) => ({ ...bb, styles: bb.styles.filter((_, j) => j !== i) }))} className="text-[#c4c4c4] hover:text-red-500">🗑</button>
                      </div>
                    ) : null));
                  })}
                </div>
                <div className="mt-3 flex items-center justify-between rounded-xl bg-[#F7F8F6] px-4 py-3">
                  <span className="text-sm text-[#5b6660]">Total assets to produce</span>
                  <span className="text-xl font-semibold tabular-nums">{totalAssets}</span>
                </div>
                {creativeCount > 6 && (
                  /* August testing (Adrie): runs are better and more consistent at
                     ~5 ads per order; quality suffered at 12. Guidance, not a cap. */
                  <div className="mt-2 rounded-xl bg-[#FEF9C3] px-4 py-3 text-sm text-[#854d0e]">
                    Heads-up: runs are most consistent at about 5 ads per order. Larger
                    orders work, but copy quality has dipped past ~6 styles — consider
                    splitting this into two smaller sprints.
                  </div>
                )}
              </>
            )}
            {deliverable === "copy-only" && <div className="mt-4 rounded-xl bg-[#F7F8F6] px-4 py-3 text-sm text-[#5b6660]">Copy only — no image batches.</div>}
          </div>
        )}
        </div>
      </div>

      {/* Footer floats below the card (matches the reference design). */}
      <div className="mt-6 flex items-center justify-between">
        {step > 1 ? (
          <button type="button" onClick={() => setStep(step - 1)} className="rounded-full border border-[#E0E0E0] px-4 py-2 text-sm hover:bg-[#F7F8F6]">← Back</button>
        ) : <span />}
        {step === 1 && (
          <button type="button" disabled={!step1ok} onClick={() => { setDone((d) => ({ ...d, 1: true })); setStep(2); }} className="rounded-full bg-[#14A800] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#108A00] disabled:cursor-not-allowed disabled:opacity-60">Continue →</button>
        )}
        {step === 2 && (
          <button type="button" disabled={!step2ok} onClick={() => { setDone((d) => ({ ...d, 2: true })); setStep(3); }} className="rounded-full bg-[#14A800] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#108A00] disabled:cursor-not-allowed disabled:opacity-60">Review Request →</button>
        )}
        {step === 3 && (
          <div className="flex items-center gap-4">
            {error && <span className="text-sm text-red-600">{error}</span>}
            <button type="button" onClick={submit} disabled={busy} className="rounded-full bg-[#14A800] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#108A00] disabled:opacity-60">{busy ? "Submitting…" : "Submit order →"}</button>
          </div>
        )}
      </div>

      {picker && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-6" onClick={(e) => { if (e.target === e.currentTarget) setPicker(null); }}>
          <div className="mt-12 w-full max-w-5xl rounded-2xl bg-white shadow-xl">
            <div className="relative border-b border-[#ECECEC] p-5">
              <div className="font-mono text-xs uppercase tracking-widest text-[#14A800]">Visual Style</div>
              <h2 className="mt-1 text-xl font-semibold">Choose a style</h2>
              <p className="mt-1 text-sm text-[#9aa0a6]">Pick the look for this batch — you can add more styles after.</p>
              <button type="button" onClick={() => setPicker(null)} className="absolute right-4 top-4 text-[#9aa0a6] hover:text-[#1d1d1b]">✕</button>
            </div>
            <div className="p-5">
              <div className="mb-4 flex items-center gap-2 rounded-lg border border-[#E0E0E0] px-3 py-2 text-sm">
                <span className="text-[#9aa0a6]">⌕</span>
                <input autoFocus value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search styles…" className="w-full outline-none" />
              </div>
              <div className="grid max-h-[55vh] grid-cols-2 gap-4 overflow-y-auto sm:grid-cols-4">
                {filtered.map(([name, desc]) => (
                  <button key={name} type="button" onClick={() => chooseStyle(name)} className="group flex flex-col overflow-hidden rounded-xl border border-[#ECECEC] text-left transition hover:border-[#14A800] hover:shadow-[0_8px_24px_-12px_rgba(20,168,0,0.35)]">
                    <div className="flex aspect-square w-full items-center justify-center overflow-hidden bg-[#F2F4F0] p-2.5">
                      {STYLE_THUMBS[name] ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={STYLE_THUMBS[name]} alt={name} loading="lazy" className="max-h-full max-w-full rounded object-contain shadow-[0_1px_4px_rgba(0,0,0,0.08)]" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center rounded text-2xl font-semibold text-[#0C7A00] opacity-50" style={{ background: "linear-gradient(135deg,#E9F899,#C4F4C0 55%,#9ED79B)" }}>{name.replace(/[^A-Za-z]/, "").charAt(0)}</div>
                      )}
                    </div>
                    <div className="p-3">
                      <div className="text-sm font-medium leading-snug">{name}</div>
                      <div className="mt-0.5 text-xs text-[#9aa0a6]">{desc}</div>
                    </div>
                  </button>
                ))}
                {filtered.length === 0 && <p className="col-span-full py-6 text-center text-sm text-[#9aa0a6]">No styles match your search.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
