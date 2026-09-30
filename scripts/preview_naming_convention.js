// Dry-runs the plugin's "Preview naming" (conventionPlan in plugin/code.js)
// against the LIVE Figma file, page by page, so the rename plan can be read
// and argued with before anyone presses Apply inside Figma. Changes nothing.
//
// Run:
//   railway run --service adam -- python3 -c "import os,urllib.request;r=urllib.request.Request('https://api.figma.com/v1/files/DoDwumxELkuAuKKSP5p00e',headers={'X-Figma-Token':os.environ['FIGMA_ACCESS_TOKEN']});open('/tmp/adam_file.json','wb').write(urllib.request.urlopen(r,timeout=280).read())"
//   node scripts/preview_naming_convention.js plugin/code.js /tmp/adam_file.json [--full] [--write renamed.json]
//
// --write applies the plan to a COPY of the JSON so the lookups can be re-run
// against the post-rename file (scripts/verify_template_resolution.py --file).
const fs = require('fs');
const [,, codePath, filePath, ...opts] = process.argv;
const flag = opts.includes('--full') ? '--full' : '';
const writeTo = opts.includes('--write') ? opts[opts.indexOf('--write') + 1] : '';
const src = fs.readFileSync(codePath, 'utf8');
function grab(name) {
  let i = src.indexOf('function ' + name + '(');
  let d = 0, started = false;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') { d++; started = true; }
    else if (src[j] === '}') { d--; if (started && d === 0) return src.slice(i, j + 1); }
  }
  throw new Error('not found: ' + name);
}
const line = (re) => { const m = src.match(re); if (!m) throw new Error('missing ' + re); return m[0]; };
(0, eval)([
  line(/var _PLATFORM_BUMPERS = \[[^\]]*\];/),
  line(/var CONVENTION_VARIANTS = \[[^\]]*\];/),
  line(/var CONVENTION_PREFIX = \{[\s\S]*?\};/),
  line(/var _CONVENTION_IMG = \{[\s\S]*?\};/),
  ...['_normName', '_stripPlatformBumper', '_conventionPlatform', '_conventionStyleSlug',
      '_conventionTemplateName', '_conventionTextName', 'conventionPlan'].map(grab),
].join('\n'));

function toNode(j, parent) {
  const b = j.absoluteBoundingBox || {};
  const n = { type: j.type, name: j.name, characters: j.characters || '', width: b.width, height: b.height, parent, json: j };
  if (j.children) n.children = j.children.map(c => toNode(c, n));
  return n;
}
const whole = JSON.parse(fs.readFileSync(filePath));
const doc = whole.document;
let total = 0, held = 0;
for (const pj of doc.children) {
  if (!/templates/i.test(pj.name) || /library/i.test(pj.name)) continue;
  const page = toNode(pj, null);
  const { prefix, plan } = conventionPlan(page);
  if (!prefix) continue;
  const by = (k, skip) => plan.filter(p => p.kind === k && !!p.skip === skip);
  const hold = plan.filter(p => p.skip);
  total += plan.length - hold.length; held += hold.length;
  console.log(`\n=== ${pj.name.trim()} (${prefix}) — rename ${plan.length - hold.length}, left for a decision ${hold.length}`);
  for (const k of ['container', 'template', 'text', 'image']) {
    const rows = by(k, false);
    if (!rows.length) continue;
    console.log(`  ${k}s: ${rows.length}`);
    const show = flag === '--full' ? rows : rows.slice(0, 6);
    for (const p of show) console.log(`    ${p.where ? p.where + ' › ' : ''}'${p.from}' → '${p.to}'${p.note || ''}`);
    if (rows.length > show.length) console.log(`    … ${rows.length - show.length} more`);
  }
  if (writeTo) for (const p of plan) if (!p.skip) p.node.json.name = p.to;
  for (const p of hold) console.log(`  HOLD ${p.where ? p.where + ' › ' : ''}'${p.from}' → '${p.to}': ${p.skip}`);
}
console.log(`\nTOTAL: rename ${total}, left for a decision ${held}`);
if (writeTo) { fs.writeFileSync(writeTo, JSON.stringify(whole)); console.log('renamed copy written to ' + writeTo); }
