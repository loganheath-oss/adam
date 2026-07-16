import fs from "fs";
import path from "path";

// Same page list + order as the live tool's wiki. Content is the docs/wiki/*.md
// files, bundled into the app under content/wiki/.
export const WIKI_PAGES: Array<[string, string]> = [
  ["README", "Home"],
  ["01-what-is-adam", "What is ADAM"],
  ["02-architecture", "Architecture"],
  ["03-repo-map", "Repo map"],
  ["04-the-pipeline", "The pipeline"],
  ["05-figma-plugin", "Figma plugin"],
  ["06-the-web-app-and-chat", "Web app & chat"],
  ["07-using-adam", "Using ADAM"],
  ["08-deployment-and-ops", "Deployment & ops"],
  ["09-configuration-and-refs", "Configuration & refs"],
  ["10-constraints", "Constraints"],
  ["11-troubleshooting", "Troubleshooting"],
  ["12-faq", "FAQ"],
  ["13-glossary", "Glossary"],
  ["14-handoff", "Handoff"],
  ["15-decisions-log", "Decisions log"],
  ["16-fixing-errors", "Fixing errors"],
];

export function getWikiPage(slug: string): string | null {
  const safe = slug.replace(/[^a-z0-9-]/gi, "");
  try {
    return fs.readFileSync(path.join(process.cwd(), "content", "wiki", `${safe}.md`), "utf-8");
  } catch {
    return null;
  }
}
