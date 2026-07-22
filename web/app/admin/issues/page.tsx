import { redirect } from "next/navigation";

// Issues moved out of the admin dashboard into everyone-accessible "Get Help"
// (Ravi, 2026-07-21). Old links redirect there.
export default function IssuesRedirect() {
  redirect("/help");
}
