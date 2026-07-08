"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

const STYLES = [
  "Graphic with Text", "Split Screen", "Us Vs Them", "Photo with Text (Upwork shell)",
  "Lifestyle Photo (full bleed)", "Testimonial", "Social Media Profile", "Pie Chart",
  "Hybrid", "Search Results", "Search Bar with Talent Badge", "Text Only", "Chat Bubble",
  "Reminder", "Device UI (Photo)", "Platform UI", "Meme", "Sticky Note", "Poll",
  "Tweet / Post Mockup", "Text with Button and Cursor", "Talent Profile", "Notification", "Bespoke",
];

const SIZES = [
  { size: "1440 x 1440", ratio: "1:1" },
  { size: "1440 x 1800", ratio: "4:5" },
  { size: "1080 x 1920", ratio: "9:16" },
];

function defaultDeliveryDate() {
  const d = new Date();
  d.setDate(d.getDate() + 14);
  return d.toISOString().slice(0, 10);
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="mb-4 font-mono text-xs uppercase tracking-widest text-primary">{label}</div>
        {children}
      </CardContent>
    </Card>
  );
}

export default function NewOrderPage() {
  const router = useRouter();
  const [driver, setDriver] = useState("Next.js test");
  const [brief, setBrief] = useState(
    "Sprint 9: AI + Specialization. Specialized AI freelancers for small businesses. Lead with the outcome.",
  );
  const [prospecting, setProspecting] = useState(true);
  const [retargeting, setRetargeting] = useState(false);
  const [images, setImages] = useState(true);
  const [styles, setStyles] = useState<string[]>(["Talent Profile", "Testimonial"]);
  const [sizes, setSizes] = useState<string[]>(SIZES.map((s) => s.size));
  const [quantity, setQuantity] = useState(1);
  const [deliveryDate, setDeliveryDate] = useState(defaultDeliveryDate());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function toggle(list: string[], set: (v: string[]) => void, v: string) {
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }

  async function submit() {
    setError("");
    if (!prospecting && !retargeting) return setError("Pick at least one audience.");
    if (styles.length === 0) return setError("Pick at least one style.");
    if (sizes.length === 0) return setError("Pick at least one size.");

    setBusy(true);
    const targeting =
      prospecting && retargeting ? "Prospecting and Retargeting" : prospecting ? "Prospecting" : "Retargeting";
    const resolutions = SIZES.filter((s) => sizes.includes(s.size));
    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          driver, brief, targeting,
          deliverable: images ? "images-copy" : "copy-only",
          styles, sizes: resolutions, quantity, deliveryDate,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Submit failed");
      router.push(`/sprints/${data.sprint_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed");
      setBusy(false);
    }
  }

  return (
    <>
      <p className="font-mono text-xs uppercase tracking-widest text-primary">Run a test</p>
      <h1 className="mt-3 text-4xl font-extrabold tracking-tight">New Order</h1>
      <p className="mt-2 text-muted-foreground">Submit a real sprint to the pipeline.</p>

      <div className="mt-8 grid gap-4">
        <Section label="Details">
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="driver">Your name</Label>
              <Input id="driver" value={driver} onChange={(e) => setDriver(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="date">Delivery date</Label>
              <Input id="date" type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} />
            </div>
          </div>
          <div className="mt-5 grid gap-2">
            <Label htmlFor="brief">Brief</Label>
            <Textarea id="brief" rows={4} value={brief} onChange={(e) => setBrief(e.target.value)} />
          </div>
        </Section>

        <Section label="Audience & output">
          <div className="flex flex-wrap items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={prospecting} onCheckedChange={(v) => setProspecting(!!v)} /> Prospecting
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={retargeting} onCheckedChange={(v) => setRetargeting(!!v)} /> Retargeting
            </label>
            <span className="mx-2 h-5 w-px bg-border" />
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={images} onCheckedChange={(v) => setImages(!!v)} /> Generate images (uncheck for copy-only)
            </label>
            <div className="flex items-center gap-2 text-sm">
              <Label htmlFor="qty">Qty / style</Label>
              <Input
                id="qty" type="number" min={1} max={10} value={quantity}
                onChange={(e) => setQuantity(Math.max(1, Number(e.target.value) || 1))}
                className="w-16"
              />
            </div>
          </div>
        </Section>

        <Section label="Sizes">
          <div className="flex flex-wrap gap-5">
            {SIZES.map((s) => (
              <label key={s.size} className="flex items-center gap-2 text-sm">
                <Checkbox checked={sizes.includes(s.size)} onCheckedChange={() => toggle(sizes, setSizes, s.size)} />
                {s.ratio} <span className="text-muted-foreground">({s.size})</span>
              </label>
            ))}
          </div>
        </Section>

        <Section label={`Styles · ${styles.length} selected`}>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
            {STYLES.map((st) => (
              <label key={st} className="flex items-center gap-2 text-sm">
                <Checkbox checked={styles.includes(st)} onCheckedChange={() => toggle(styles, setStyles, st)} />
                <span className={styles.includes(st) ? "" : "text-muted-foreground"}>{st}</span>
              </label>
            ))}
          </div>
        </Section>

        <div className="flex items-center gap-4">
          <Button onClick={submit} disabled={busy} size="lg">
            {busy ? "Submitting…" : "Submit order"}
          </Button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </div>
    </>
  );
}
