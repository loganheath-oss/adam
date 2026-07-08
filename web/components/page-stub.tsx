import { Card, CardContent } from "@/components/ui/card";

// A fully-styled placeholder so every nav link resolves and shares the chrome.
// A real page costs about this many lines on the system.
export function PageStub({ title, note }: { title: string; note: string }) {
  return (
    <>
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      <Card className="mt-6 max-w-xl">
        <CardContent className="pt-6">
          <p className="font-mono text-xs uppercase tracking-widest text-primary">
            Design-system reference
          </p>
          <p className="mt-2 text-muted-foreground">{note}</p>
        </CardContent>
      </Card>
    </>
  );
}
