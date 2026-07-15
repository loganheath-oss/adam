import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { AdminTabs } from "@/components/admin-tabs";
import { RoleToggle } from "@/components/role-toggle";
import { getRoles } from "@/lib/admin";

// Server component: the Roles tab. Manage who's admin vs member.
export const dynamic = "force-dynamic";

const CARD = "rounded-xl border bg-background p-5 shadow-sm";

function fmtTs(ts: string | null): string {
  if (!ts) return "—";
  const m = ts.match(/(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} · ${m[2]}` : ts;
}

function Header() {
  return (
    <>
      <header className="mb-2">
        <h1 className="text-4xl font-medium tracking-tight">Roles</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Two roles: <strong>admin</strong> (Ravi + Logan) and <strong>member</strong> (everyone at
          Upwork). Users appear here once they&apos;ve been seen in a run or chat.
        </p>
      </header>
      <AdminTabs current="roles" />
    </>
  );
}

export default async function RolesPage() {
  const data = await getRoles();

  if (!data) {
    return (
      <div>
        <Header />
        <div className={`${CARD} text-sm text-muted-foreground`}>Couldn&apos;t reach the backend.</div>
      </div>
    );
  }
  if (!data.enabled || data.error) {
    return (
      <div>
        <Header />
        <div className={`${CARD} text-sm text-muted-foreground`}>
          {data.error
            ? `Roles query failed: ${data.error}`
            : "Roles are off — DATABASE_URL isn't configured on the backend."}
        </div>
      </div>
    );
  }

  const counts = data.counts ?? {};
  const users = data.users ?? [];

  return (
    <div>
      <Header />

      <div className="mb-4 flex flex-wrap gap-2">
        <span className="rounded-full border px-3 py-1 text-xs tabular-nums text-muted-foreground">
          admin: <span className="font-semibold text-foreground">{counts.admin ?? 0}</span>
        </span>
        <span className="rounded-full border px-3 py-1 text-xs tabular-nums text-muted-foreground">
          member: <span className="font-semibold text-foreground">{counts.member ?? 0}</span>
        </span>
      </div>

      <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3 text-xs text-amber-900">
        Role <em>data</em> is managed here now. Per-route enforcement (gating the operational
        surface by role) activates once SSO provides a per-user identity — today `/admin/*` is
        gated by the shared API key. Seed admins on the backend via the{" "}
        <code className="rounded bg-amber-100 px-1">ADMIN_EMAILS</code> env var, or flip anyone below.
      </div>

      <div className="overflow-hidden rounded-xl border shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="font-mono text-xs uppercase tracking-wider">User</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Role</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Last seen</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.email}>
                <TableCell className="font-medium">{u.name || u.email}</TableCell>
                <TableCell>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.role === "admin" ? "bg-[#14A800]/15 text-[#108A00]" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {u.role}
                  </span>
                </TableCell>
                <TableCell className="whitespace-nowrap font-mono text-muted-foreground tabular-nums">
                  {fmtTs(u.last_seen_at)}
                </TableCell>
                <TableCell>
                  <RoleToggle email={u.email} role={u.role} />
                </TableCell>
              </TableRow>
            ))}
            {users.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-10 text-center text-muted-foreground">
                  No users yet — they appear here once they&apos;ve been seen in a run or chat.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
