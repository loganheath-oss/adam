import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";

function FeatureCard({
  kicker,
  title,
  desc,
  href,
}: {
  kicker: string;
  title: string;
  desc: string;
  href: string;
}) {
  return (
    <Link href={href}>
      <Card className="transition-shadow hover:shadow-md">
        <CardContent className="pt-6">
          <p className="font-mono text-xs uppercase tracking-widest text-primary">{kicker}</p>
          <h3 className="mt-3 text-lg font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{desc}</p>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function Home() {
  return (
    <>
      <p className="font-mono text-xs uppercase tracking-widest text-primary">
        Ad creative, on demand
      </p>
      <h1 className="mt-3 text-5xl font-extrabold tracking-tight text-balance">
        Start a new ad order,
        <br />
        <span className="text-muted-foreground">or pick up a sprint.</span>
      </h1>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <FeatureCard
          kicker="Create"
          title="New Order"
          desc="Brief, audience, styles, sizes — submit and ADAM builds it."
          href="/new"
        />
        <FeatureCard
          kicker="Track"
          title="Sprint Runs"
          desc="Every run, its status, and one-click into the gates."
          href="/sprints"
        />
      </div>
    </>
  );
}
