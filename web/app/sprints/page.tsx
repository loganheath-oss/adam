import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/status-badge";
import { getSprints } from "@/lib/sprints";

// Server component: fetches live sprints from the FastAPI backend at request time.
export const dynamic = "force-dynamic";

export default async function SprintsPage() {
  const { sprints, live } = await getSprints();

  return (
    <>
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-medium tracking-tight">Sprint Runs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {sprints.length} sprints · click any row to view details
            {!live && <span className="ml-2 text-amber-600">· sample data</span>}
          </p>
        </div>
        <div className="flex gap-3">
          <Link href="/sprints" className={buttonVariants({ variant: "outline" })}>Refresh</Link>
          <Link href="/new" className={buttonVariants()}>New Order</Link>
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
            {sprints.map((s) => (
              <TableRow key={s.id} className="cursor-pointer">
                <TableCell className="font-mono text-muted-foreground tabular-nums">{s.updated}</TableCell>
                <TableCell className="font-mono font-semibold">
                  <Link href={`/sprints/${s.id}`} className="hover:text-primary hover:underline">{s.id}</Link>
                </TableCell>
                <TableCell>{s.driver}</TableCell>
                <TableCell>{s.platform}</TableCell>
                <TableCell><StatusBadge status={s.status} /></TableCell>
                <TableCell>
                  <div className="flex justify-end gap-2">
                    <Link href={`/sprints/${s.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                      {s.status === "complete" ? "View" : "Review"}
                    </Link>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {sprints.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                  No sprints yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
