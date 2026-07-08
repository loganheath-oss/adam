import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/status-badge";
import { SPRINTS } from "@/lib/data";

export default function SprintsPage() {
  return (
    <>
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Sprint Runs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {SPRINTS.length} sprints · click any row to view details
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline">Refresh</Button>
          <Button>New Order</Button>
        </div>
      </header>

      <div className="overflow-hidden rounded-xl border shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="font-mono text-xs uppercase tracking-wider">Updated</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Sprint ID</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Driver</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Platform</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {SPRINTS.map((s) => (
              <TableRow key={s.id} className="cursor-pointer">
                <TableCell className="font-mono text-muted-foreground tabular-nums">{s.updated}</TableCell>
                <TableCell className="font-mono font-semibold">{s.id}</TableCell>
                <TableCell>{s.driver}</TableCell>
                <TableCell>{s.platform}</TableCell>
                <TableCell><StatusBadge status={s.status} /></TableCell>
                <TableCell>
                  <div className="flex justify-end gap-2">
                    {s.status !== "complete" && (
                      <Button variant="outline" size="sm">Review</Button>
                    )}
                    <Button variant="outline" size="sm">Chat</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
