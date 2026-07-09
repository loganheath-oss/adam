import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// State encoded in color + shape, from one place. Add a status here and every
// table that renders it updates.
export function StatusBadge({ status }: { status: string }) {
  const base = "font-mono text-xs font-normal";
  if (status === "complete") {
    return <Badge className={cn(base, "bg-green-50 text-green-700 hover:bg-green-50")}>Complete</Badge>;
  }
  if (status.startsWith("awaiting_gate")) {
    return (
      <Badge className={cn(base, "bg-amber-50 text-amber-700 hover:bg-amber-50")}>
        {status.replace(/_/g, " ")}
      </Badge>
    );
  }
  return <Badge variant="secondary" className={base}>{status}</Badge>;
}
