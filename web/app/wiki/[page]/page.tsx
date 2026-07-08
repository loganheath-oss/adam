import { WikiLayout } from "@/components/wiki-layout";
import { WIKI_PAGES, getWikiPage } from "@/lib/wiki";

export function generateStaticParams() {
  return WIKI_PAGES.filter(([slug]) => slug !== "README").map(([slug]) => ({ page: slug }));
}

export default async function WikiPage({ params }: { params: Promise<{ page: string }> }) {
  const { page } = await params;
  const md = getWikiPage(page);
  return <WikiLayout current={page} md={md ?? `# Page not found\n\n\`${page}\` isn’t in the wiki.`} />;
}
