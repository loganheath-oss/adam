// Replays plugin/code.js's board-mode TEXT fills against the LIVE Reddit
// templates and reports every Copy_* layer still holding template text.
//
// Why: Elise's Reddit templates name layers Copy_<Role> (Copy_Headline1/2,
// Copy_Title2, Copy_Body, Copy_List1-3, Copy_Left/Right/BodyCenter …). Board
// mode only knew the generic roles, so on 2026-09-30 62 Copy_* layers across
// the 20 Reddit styles kept stock or lorem text. This proves the mapping
// against the real file, since plugin code only runs inside Figma desktop.
//
// Run:
//   railway run --service adam -- python3 -c "import json,os,urllib.request;r=urllib.request.Request('https://api.figma.com/v1/files/DoDwumxELkuAuKKSP5p00e/nodes?ids=6507:4204',headers={'X-Figma-Token':os.environ['FIGMA_ACCESS_TOKEN']});open('/tmp/reddit_page.json','wb').write(urllib.request.urlopen(r,timeout=200).read())"
//   node scripts/verify_reddit_fills.js plugin/code.js /tmp/reddit_page.json
//
// Expected residue (by design): Meme's Copy_CTA (STYLES_THAT_SKIP_CTA — the pill
// is hidden), Notification's Copy_Reminder (a fixed "Reminder" label).
const fs = require('fs');
const [,, codePath, pagePath] = process.argv;
const src = fs.readFileSync(codePath, 'utf8');
function grab(name) {
  let i = src.indexOf('async function ' + name + '(');
  if (i < 0) i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('not found: ' + name);
  let d = 0, started = false;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') { d++; started = true; }
    else if (src[j] === '}') { d--; if (started && d === 0) return src.slice(i, j + 1); }
  }
}
const grabVar = (name) => {
  const i = src.indexOf('var ' + name + ' =');
  let d = 0, started = false;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{' || src[j] === '[') { d++; started = true; }
    else if (src[j] === '}' || src[j] === ']') { d--; if (started && d === 0) return src.slice(i, j + 2); }
  }
};
global.log = () => {};
global._noteDrift = () => {};
global._PLATFORM_BUMPERS = ['meta', 'reddit', 'linkedin', 'youtube', 'google', 'thirdparty'];
global.setTextLayer = async (n, t) => { if (!n || n.type !== 'TEXT' || !t) return false; n.characters = t; n.__filled = true; return true; };
const fns = ['_normName', '_stripPlatformBumper', '_bumperEq', '_bumperNormEq', '_findExactByName', '_findNormByName',
  'findLayerByName', '_findAllExactByName', '_findAllNormByName', 'findAllLayersByName', 'walkChildren', 'splitPipe',
  'setFirstTextByCandidates', 'fillListLayers', '_withTrailingSymbolLine', 'fillRedditLayers', 'fillUsVsThemCopy', 'normalizeStyle'];
const vars = ['REDDIT_LAYER_FILLS', 'STYLE_HEADLINE_LAYERS', 'STYLE_SUBHEAD_LAYERS', 'STYLES_THAT_SKIP_CTA'];
(0, eval)(vars.map(grabVar).join('\n') + '\n' + fns.map(grab).join('\n'));

const page = JSON.parse(fs.readFileSync(pagePath)).nodes['6507:4204'].document;
function toNode(j, parent) {
  const n = { type: j.type, name: j.name, characters: j.characters || '', parent, children: [] };
  n.__orig = n.characters;
  n.children = (j.children || []).map(c => toNode(c, n));
  return n;
}
const ROW = {
  Platform: 'Reddit', CTA: 'Post a project',
  Headline_On_Creative: 'HEADLINE', Subhead_On_Creative: 'SUBHEAD',
  Left_Headline: 'LEFTWORD', Right_Headline: 'RIGHTWORD', Single_Headline: 'UNDERLINE',
  Single_Bullets: 'ITEM1|ITEM2|ITEM3', Search_Results: 'SEARCHTERM',
  Them_Bullets: 'THEM1|THEM2|THEM3', Testimonial_Quote: 'QUOTE', Testimonial_Author: 'AUTHOR',
  Pie_Labels: 'Q1|Q2|Q3|Q4', Pie_Center: 'CENTER', Chart_Pct: '',
};
const STYLE = (c) => c.replace('Reddit_Adtype_', '').replace(/-/g, ' ').replace(/\bvs\b/i, 'vs');
let problems = 0;
(async () => {
  for (const c of page.children) {
    if (!c.name.startsWith('Reddit_Adtype_')) continue;
    const style = STYLE(c.name), key = normalizeStyle(style);
    for (const k of c.children || []) {
      if (!/\d{3,5}x\d{3,5}/.test(k.name)) continue;
      const clone = toNode(k, null);
      const row = Object.assign({ Visual_Style: style }, ROW);
      // generic board-mode fills, same order as fillConceptBoard
      await setFirstTextByCandidates(clone, ['Copy_Headline'].concat(STYLE_HEADLINE_LAYERS[key] || []).concat(['headline_text']), row.Headline_On_Creative);
      await setFirstTextByCandidates(clone, ['Copy_Subhead'].concat(STYLE_SUBHEAD_LAYERS[key] || []), row.Subhead_On_Creative);
      if (!STYLES_THAT_SKIP_CTA[key]) await setFirstTextByCandidates(clone, ['Copy_CTA', 'cta_text', 'CTA_Text', 'CTA', 'cta'], row.CTA);
      await setFirstTextByCandidates(clone, ['Copy_Testimonial'], row.Testimonial_Quote);
      await setFirstTextByCandidates(clone, ['Copy_Author'], row.Testimonial_Author);
      const pl = splitPipe(row.Pie_Labels), quad = ['Copy_TopLeft', 'Copy_TopRight', 'Copy_BottomLeft', 'Copy_BottomRight'];
      for (let q = 0; q < 4; q++) await setFirstTextByCandidates(clone, [quad[q]], pl[q]);
      if (key === 'us vs them') await fillUsVsThemCopy(clone, row);
      await fillRedditLayers(clone, key, row);
      const left = [];
      (function w(n) { if (n.type === 'TEXT' && /^Copy_/.test(n.name) && !n.__filled) left.push(`${n.name}="${n.__orig.replace(/\n/g, ' / ').slice(0, 24)}"`); n.children.forEach(w); })(clone);
      const venn = key === 'venn diagram' ? ' ' + JSON.stringify(findLayerByName(clone, 'Copy_Left').characters) : '';
      if (left.length) problems += left.length;
      console.log(`${left.length ? '✗' : '✓'} ${style.padEnd(20)} ${k.name.padEnd(15)} ${left.length ? 'UNFILLED: ' + left.join(', ') : 'all Copy_* filled'}${venn}`);
    }
  }
  console.log('\nunfilled Copy_* layers:', problems);
})();
