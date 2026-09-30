// Replays the plugin's board-mode TEXT fills (plugin/code.js fillConceptBoard,
// per slot) against every template on one templates page of a saved Figma file,
// and reports which text layers receive copy.
//
// Two uses:
//   node scripts/verify_copy_fills.js plugin/code.js file.json "Meta Templates"
//       → per template, the Copy_* layers left holding template text
//   node scripts/verify_copy_fills.js plugin/code.js before.json "Meta Templates" --compare after.json
//       → every layer (by node id) that received copy BEFORE a rename and does
//         not AFTER it. Zero = the rename cost ADAM nothing on this page.
//
// Get a file:  see scripts/preview_naming_convention.js (and --write for the
// renamed copy). Not replayed: Poll bar geometry, Talent-Profile / Testimonial
// headshot overlays (image operations, not text).
const fs = require('fs');
const [,, codePath, filePath, pageName, ...opts] = process.argv;
const compareTo = opts.includes('--compare') ? opts[opts.indexOf('--compare') + 1] : '';
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
  const mm = new RegExp('var ' + name + '\\s*=').exec(src);
  const i = mm ? mm.index : -1;
  if (i < 0) throw new Error('var not found: ' + name);
  let d = 0, started = false;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{' || src[j] === '[') { d++; started = true; }
    else if (src[j] === '}' || src[j] === ']') { d--; if (started && d === 0) return src.slice(i, j + 2); }
  }
};
global.log = () => {};
global._noteDrift = () => {};
global._PLATFORM_BUMPERS = ['meta', 'reddit', 'linkedin', 'youtube', 'google', 'thirdparty'];
global.setTextLayer = async (n, t) => { if (!n || n.type !== 'TEXT' || !t) return false; n.characters = String(t); n.__filled = true; return true; };
(0, eval)([
  ...['REDDIT_LAYER_FILLS', 'STYLE_HEADLINE_LAYERS', 'STYLE_SUBHEAD_LAYERS', 'STYLES_THAT_SKIP_CTA',
      'DUAL_HEADLINE_LEFT', 'DUAL_HEADLINE_RIGHT'].map(grabVar),
  ...['_normName', '_stripPlatformBumper', '_bumperEq', '_bumperNormEq', '_findExactByName', '_findNormByName',
      'findLayerByName', '_findAllExactByName', '_findAllNormByName', 'findAllLayersByName', 'walkChildren',
      'splitPipe', 'setFirstTextByCandidates', 'fillListLayers', '_withTrailingSymbolLine', 'fillRedditLayers',
      'fillUsVsThemCopy', 'normalizeStyle'].map(grab),
].join('\n'));

// One row carrying every structured field, so each template can take whatever
// copy it has a layer for.
const ROW = {
  CTA: 'CTA', Headline_On_Creative: 'HEADLINE', Subhead_On_Creative: 'SUBHEAD',
  Us_Headline: 'US', Them_Headline: 'THEM', Us_Bullets: 'U1|U2|U3', Them_Bullets: 'T1|T2|T3',
  Us_Subhead: 'USWRAP', Them_Subhead: 'THEMWRAP',
  Left_Headline: 'LEFT', Right_Headline: 'RIGHT', Left_Bullets: 'L1|L2', Right_Bullets: 'R1|R2',
  Single_Headline: 'SINGLE', Single_Bullets: 'S1|S2|S3', Search_Results: 'SR1|SR2|SR3',
  Testimonial_Quote: 'QUOTE', Testimonial_Author: 'AUTHOR', Profile_Name: 'NAME', Profile_Title: 'TITLE',
  Profile_Left: 'PLEFT', Profile_Right: 'PRIGHT', Chat_Label: 'CHATLABEL', Chat_Message: 'CHATMSG',
  Button_Text: 'BUTTON', Pie_Labels: 'Q1|Q2|Q3|Q4', Pie_Center: 'CENTER', Chart_Pct: '',
};

function toNode(j, parent) {
  const n = { id: j.id, type: j.type, name: j.name, characters: j.characters || '', parent, children: [] };
  n.__orig = n.characters;
  n.children = (j.children || []).map(c => toNode(c, n));
  return n;
}
// Container slug → the Visual_Style the manifest actually carries (the plugin
// keys its fills on the manifest name, not the container).
const STYLE_ALIAS = { 'mockup': 'Tweet / Post Mockup', 'lifestyle photo full bleed': 'Lifestyle Photo' };
const styleOf = (containerName) => {
  const s = _stripPlatformBumper(containerName).replace(/^ad\s*type\s*[:_\-\s]*/i, '')
    .replace(/\/+$/, '').replace(/-/g, ' ').trim();
  return STYLE_ALIAS[s.toLowerCase()] || s;
};

async function run(file) {
  const doc = JSON.parse(fs.readFileSync(file)).document;
  const pj = doc.children.find(p => p.name.trim().replace(/^->\s*/, '') === pageName.replace(/^->\s*/, ''));
  if (!pj) throw new Error('page not found: ' + pageName);
  const reddit = /reddit/i.test(pj.name);
  const filled = new Set(), report = [];
  for (const cj of pj.children || []) {
    if (!/ad\s*type/i.test(cj.name)) continue;
    const style = styleOf(cj.name), key = normalizeStyle(style);
    for (const kj of cj.children || []) {
      if (/^rules/i.test(kj.name) || !['FRAME', 'COMPONENT', 'COMPONENT_SET'].includes(kj.type)) continue;
      const clone = toNode(kj, null);
      const row = Object.assign({ Visual_Style: style, Platform: reddit ? 'Reddit' : 'Meta' }, ROW);
      // ── same order as fillConceptBoard's per-slot fill ──
      await setFirstTextByCandidates(clone, ['Copy_Headline'].concat(key === 'reminder' || key === 'tweet / post mockup' ? ['Copy_Body'] : []).concat(STYLE_HEADLINE_LAYERS[key] || []).concat(['headline_text']), row.Headline_On_Creative);
      await setFirstTextByCandidates(clone, ['Copy_Subhead'].concat(STYLE_SUBHEAD_LAYERS[key] || []), row.Subhead_On_Creative);
      if (!STYLES_THAT_SKIP_CTA[key]) {
        await setFirstTextByCandidates(clone, ['Copy_CTA', 'cta_text', 'CTA_Text', 'CTA', 'cta'], row.CTA);
        for (const c of findAllLayersByName(clone, 'Copy_CTA').slice(1)) await setTextLayer(c, row.CTA);
      }
      if (key === 'sticky note') {
        await setFirstTextByCandidates(clone, ['Copy_Headline'], row.Single_Headline);
        if (!(await fillListLayers(clone, splitPipe(row.Single_Bullets)))) await setFirstTextByCandidates(clone, ['Copy_Body'], splitPipe(row.Single_Bullets).join('\n'));
        await setFirstTextByCandidates(clone, DUAL_HEADLINE_LEFT.concat(['Left_Headline_Text']), row.Left_Headline);
        await setFirstTextByCandidates(clone, DUAL_HEADLINE_RIGHT.concat(['right_headline_text', 'Right_Headline_Text']), row.Right_Headline);
        const lb = splitPipe(row.Left_Bullets), rb = splitPipe(row.Right_Bullets);
        await setFirstTextByCandidates(clone, ['Copy_Left-Bullet1', 'Left_Bullet_Text1', 'Left_Bullet_Text_1'], lb[0]);
        await setFirstTextByCandidates(clone, ['Copy_Left-Bullet2', 'Left_Bullet_Text2', 'Left_Bullet_Text_2'], lb[1]);
        await setFirstTextByCandidates(clone, ['Copy_Right-Bullet1', 'Right_Bullet_Text1', 'Right_Bullet_Text_1'], rb[0]);
        await setFirstTextByCandidates(clone, ['Copy_Right-Bullet2', 'Right_Bullet_Text2', 'Right_Bullet_Text_2'], rb[1]);
      }
      await setFirstTextByCandidates(clone, ['Copy_Testimonial'], row.Testimonial_Quote);
      await setFirstTextByCandidates(clone, ['Copy_Author'], row.Testimonial_Author);
      const sr = splitPipe(row.Search_Results);
      for (let i = 0; i < 3; i++) await setFirstTextByCandidates(clone, ['Copy_Title' + (i + 1)], sr[i]);
      await setFirstTextByCandidates(clone, ['Copy_Name'], row.Profile_Name);
      await setFirstTextByCandidates(clone, ['Copy_Title'], row.Profile_Title);
      await setFirstTextByCandidates(clone, ['Copy_Left-Column'], row.Profile_Left);
      await setFirstTextByCandidates(clone, ['Copy_Right-Column'], row.Profile_Right);
      await setFirstTextByCandidates(clone, ['Copy_Chat-Bubble-1'], row.Chat_Label);
      await setFirstTextByCandidates(clone, ['Copy_Chat-Bubble-2'], row.Chat_Message);
      await setFirstTextByCandidates(clone, ['Copy_Button'], row.Button_Text);
      const pl = splitPipe(row.Pie_Labels), quad = ['Copy_TopLeft', 'Copy_TopRight', 'Copy_BottomLeft', 'Copy_BottomRight'];
      for (let q = 0; q < 4; q++) await setFirstTextByCandidates(clone, [quad[q]], pl[q]);
      // Pie centre: fillPieChartValue writes the % when there is one.
      if (key === 'pie chart') await setFirstTextByCandidates(clone, ['Copy_Center', 'Center_Callout_Text', 'chart_center_text', 'TextOnly_Subhead_Text', 'headline_text'], '73%');
      if (key === 'us vs them') await fillUsVsThemCopy(clone, row);
      if (reddit) await fillRedditLayers(clone, key, row);
      const left = [];
      (function w(n) {
        if (n.type === 'TEXT') {
          if (n.__filled) filled.add(n.id);
          else if (/^Copy_/.test(n.name)) left.push(`${n.name}="${n.__orig.replace(/\n/g, ' / ').slice(0, 20)}"`);
        }
        n.children.forEach(w);
      })(clone);
      report.push({ tpl: `${cj.name} › ${kj.name}`, left });
    }
  }
  return { filled, report };
}

(async () => {
  const a = await run(filePath);
  if (!compareTo) {
    let n = 0;
    for (const r of a.report) { if (r.left.length) { n += r.left.length; console.log(`✗ ${r.tpl}: ${r.left.join(', ')}`); } }
    console.log(`\n${pageName}: ${a.filled.size} layers take copy; ${n} Copy_* layers keep template text`);
    return;
  }
  const b = await run(compareTo);
  const lost = [...a.filled].filter(id => !b.filled.has(id));
  const gained = [...b.filled].filter(id => !a.filled.has(id));
  console.log(`${pageName}: before ${a.filled.size} layers take copy, after ${b.filled.size} — ` +
              `lost ${lost.length}, gained ${gained.length}`);
  if (lost.length) console.log('LOST (filled before, not after):', lost.join(', '));
  process.exitCode = lost.length ? 1 : 0;
})();
