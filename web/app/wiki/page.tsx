import { WikiLayout } from "@/components/wiki-layout";
import { getWikiPage } from "@/lib/wiki";

export default function WikiHome() {
  return <WikiLayout current="README" md={getWikiPage("README") ?? "# Wiki"} />;
}
