import Link from "next/link";

// Style-preview thumbnails (mirrored from upwork-adam) that fill the gallery.
const PREVIEWS = [
  "graphic-with-text", "split-screen", "us-vs-them", "photo-with-text-upwork-shell",
  "lifestyle-photo-full-bleed", "testimonial", "social-media-profile", "pie-chart",
  "hybrid", "search-results", "search-bar-with-talent-badge", "text-only",
  "chat-bubble", "reminder", "device-ui-photo", "platform-ui", "meme",
  "sticky-note", "poll", "tweet-post-mockup", "text-with-button-and-cursor", "talent-profile",
];

const GLOW =
  "radial-gradient(1000px 540px at 80% -10%, rgba(20,168,0,0.16), rgba(0,0,0,0) 60%)," +
  "radial-gradient(760px 480px at 4% 4%, rgba(132,236,199,0.10), rgba(0,0,0,0) 58%)," +
  "radial-gradient(900px 680px at 60% 118%, rgba(103,220,18,0.06), rgba(0,0,0,0) 62%)";

// One marquee row — the previews duplicated ×2 so translateX(-50%) loops seamlessly.
function MarqueeRow({ reverse }: { reverse?: boolean }) {
  return (
    <div className={`adam-marquee flex w-max gap-4 px-2${reverse ? " reverse" : ""}`}>
      {[...PREVIEWS, ...PREVIEWS].map((p, i) => (
        <div key={i} className="group h-40 w-40 flex-none overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/style-previews/${p}.jpg`}
            alt=""
            className="h-full w-full object-cover opacity-80 transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-[1.04] group-hover:opacity-100"
          />
        </div>
      ))}
    </div>
  );
}

// One entry card — his treatment: green-glow shadow, hover-lift, green highlight,
// and an arrow that nudges right on hover. `featured` gets the green-tinted fill.
function EntryCard({
  href, icon, title, desc, cta, featured,
}: { href: string; icon: React.ReactNode; title: string; desc: string; cta: string; featured?: boolean }) {
  return (
    <Link
      href={href}
      className={`group block rounded-3xl border p-8 backdrop-blur-md transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] hover:-translate-y-1 ${
        featured
          ? "border-primary/40 shadow-[0_0_0_1px_rgba(20,168,0,0.16),0_30px_80px_-30px_rgba(20,168,0,0.42)] hover:border-primary/60"
          : "border-white/10 hover:border-primary/50 hover:shadow-[0_0_0_1px_rgba(20,168,0,0.12),0_30px_80px_-30px_rgba(20,168,0,0.30)]"
      }`}
      style={{
        background: featured
          ? "linear-gradient(250.58deg, rgba(20,168,0,0.14) 0.7%, rgba(132,236,199,0.05) 98.41%)"
          : "linear-gradient(250.58deg, rgba(255,255,255,0.06) 0.7%, rgba(255,255,255,0.03) 98.41%)",
      }}
    >
      <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-white/[0.14] bg-white/[0.06] text-primary">{icon}</div>
      <h3 className="mt-6 text-xl font-medium text-white">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-white/60">{desc}</p>
      <span className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
        {cta} <span className="transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden>→</span>
      </span>
    </Link>
  );
}

const ICON = "h-5 w-5";
const PlusIcon = () => (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className={ICON}><path d="M12 5v14M5 12h14" /></svg>);
const ChatIcon = () => (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={ICON}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>);
const BookIcon = () => (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={ICON}><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></svg>);

// Full-bleed dark landing — matches upwork-adam.vercel.app: PP Neue Montreal,
// green-glow backdrop, big tight heading, pill CTAs, a full-width auto-scrolling
// creative marquee (top scrolls left, bottom right), and the four entry cards.
export default function Home() {
  return (
    <section className="relative left-1/2 -mt-12 -mb-12 w-screen -translate-x-1/2 overflow-hidden bg-[#181818] text-white">
      <div className="pointer-events-none absolute inset-0 z-0" style={{ backgroundImage: GLOW }} />
      <div className="relative z-10 pb-24 pt-24">
        {/* Hero (contained) */}
        <div className="mx-auto max-w-[1080px] px-6">
          <h1 className="max-w-4xl text-6xl font-medium leading-[0.98] tracking-[-0.02em] text-white sm:text-7xl lg:text-[80px]">
            Ad creative, produced
            <br />
            <span className="text-primary">end‑to‑end.</span>
          </h1>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-white/60">
            Submit a brief and ADAM produces copy and assembled creative across every size and
            visual style — on brand, on spec, ready to ship.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/new"
              className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition hover:brightness-95"
            >
              Start an order <span aria-hidden>→</span>
            </Link>
          </div>
        </div>

        {/* Creative marquee — full-bleed, two rows scrolling opposite ways.
            The horizontal mask fades both edges into the dark backdrop (his chiaroscuro). */}
        <div
          className="relative mt-16 space-y-4 overflow-hidden"
          style={{
            maskImage: "linear-gradient(90deg, transparent, black 10%, black 90%, transparent)",
            WebkitMaskImage: "linear-gradient(90deg, transparent, black 10%, black 90%, transparent)",
          }}
        >
          <MarqueeRow />
          <MarqueeRow reverse />
        </div>

        {/* Entry cards (contained) */}
        <div className="mx-auto mt-14 grid max-w-[1080px] gap-6 px-6 sm:grid-cols-2">
          <EntryCard featured href="/new" icon={<PlusIcon />} title="New order" cta="Open form"
            desc="Open the order form. The creative team is notified and assets arrive by your delivery date." />
          <EntryCard href="/agent" icon={<ChatIcon />} title="Ask ADAM" cta="Start a chat"
            desc="Ask how ADAM is built or how to use it — a read-only assistant grounded in the wiki." />
          <EntryCard href="/wiki" icon={<BookIcon />} title="How it works" cta="Open the wiki"
            desc="The knowledge base — architecture, pipeline, plugin, deployment, and the constraints." />
        </div>
      </div>
    </section>
  );
}
