// Harness: load selectVariant + countCopyLayers out of plugin/code.js and drive
// them with fake Figma nodes. The plugin cannot be run outside Figma desktop, so
// this replays the chosen functions against the shapes the file actually holds.
const fs = require('fs');
const src = fs.readFileSync('plugin/code.js', 'utf8');
function grab(name) {
  // Keep the `async` keyword: slicing from 'function foo(' drops it and the
  // body's `await` then becomes a SyntaxError.
  let i = src.indexOf('async function ' + name + '(');
  if (i < 0) i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('not found: ' + name);
  let d = 0, started = false;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') { d++; started = true; }
    else if (src[j] === '}') { d--; if (started && d === 0) return src.slice(i, j + 1); }
  }
}
const logs = [];
const ctx = { log: t => logs.push(t) };
eval(grab('countCopyLayers') + '\n' + grab('_hasImageSlot') + '\n' + grab('selectVariant')
     .replace(/\blog\(/g, 'ctx.log('));

const T = (name, n, extra = {}) => ({
  type: 'FRAME', name,
  children: Array.from({length: n}, (_, i) => ({type: 'TEXT', name: 'Copy_F' + i, children: []})),
  ...extra,
});
let fails = 0;
const ok = (label, cond, detail='') => {
  console.log((cond ? '  PASS ' : '  FAIL ') + label + (cond ? '' : ' — ' + detail));
  if (!cond) fails++;
};

// 1. Elise's case: two identically named same-size frames, one real one empty.
logs.length = 0;
let got = selectVariant([T('1080x1350', 0), T('1080x1350', 5)], {});
ok('duplicate frames: picks the one WITH Copy_ layers', got && countCopyLayers(got) === 5,
   'picked ' + countCopyLayers(got) + ' layers');
ok('duplicate frames: reports the duplicate', logs.some(l => /duplicate frames/.test(l)), JSON.stringify(logs));

// 2. Order must not matter — the old bug was first-found-wins.
got = selectVariant([T('1080x1350', 7), T('1080x1350', 0)], {});
ok('duplicate frames: order-independent', got && countCopyLayers(got) === 7);

// 3. Equal content must NOT trigger the tie-break (no false "duplicate" noise).
logs.length = 0;
got = selectVariant([T('a', 3), T('b', 3)], {});
ok('equal content: falls through to the name-based choice', got.name === 'a');
ok('equal content: stays silent', !logs.some(l => /duplicate frames/.test(l)), JSON.stringify(logs));

// 4. A deliberate name choice must still win over raw layer count.
got = selectVariant([T('Template_X_Dark', 2), T('Template_X_Light', 9)], {prefer: 'dark'});
ok('name preference still wins: Dark chosen despite fewer layers', got.name === 'Template_X_Dark');

// 5. Alt/CTA preference preserved.
got = selectVariant([T('Template_X', 4), T('Template_X_Alt', 9)], {wantCTA: true});
ok('CTA preference preserved: non-Alt chosen', got.name === 'Template_X');

// 6. Nested Copy_ layers are counted (they live inside groups in real templates).
const nested = {type:'FRAME', name:'n', children:[{type:'FRAME', name:'g', children:[
  {type:'TEXT', name:'Copy_Headline', children:[]}, {type:'TEXT', name:'Other', children:[]}]}]};
ok('counts nested Copy_ layers', countCopyLayers(nested) === 1, String(countCopyLayers(nested)));
ok('ignores non-Copy text layers', countCopyLayers({type:'FRAME',name:'x',children:[
  {type:'TEXT',name:'Label',children:[]}]}) === 0);

// 7. Platform bumper (Elise, 2026-09-23: rename the Meta frames to carry a
// "meta_" front bumper so they match Reddit's convention). Every template
// lookup anchors its prefix test at position 0, so the bumper would hide every
// Meta template at once. Match must survive the rename WITHOUT loosening into
// a substring search.
eval(grab('_stripPlatformBumper') + '\n' + grab('_normName') + '\n'
     + grab('_findAllByPrefixExact') + '\n' + grab('_findAllByPrefixNorm'));
const _PLATFORM_BUMPERS = ['meta', 'reddit', 'linkedin', 'youtube', 'google', 'thirdparty'];

const N = (name, kids = []) => ({type: 'FRAME', name, children: kids});
const hits = (root, prefix) => _findAllByPrefixExact(root, prefix).map(n => n.name);

// The names as they are today, and as they'd be after the rename.
let tree = N('page', [
  N('Template_Text-Only_Dark_1440x1440'),
  N('Meta_Template_Text-Only_Dark_1080x1920'),
  N('Meta - Template_Text-Only_Light_1440x1800'),
  N('Reddit_Template_Text-Only_Dark_1080x1350'),
]);
ok('bumper: un-renamed frame still matches', hits(tree, 'Template_Text-Only').includes('Template_Text-Only_Dark_1440x1440'));
ok('bumper: Meta_ prefixed frame matches', hits(tree, 'Template_Text-Only').includes('Meta_Template_Text-Only_Dark_1080x1920'));
ok('bumper: "Meta - " prefixed frame matches', hits(tree, 'Template_Text-Only').includes('Meta - Template_Text-Only_Light_1440x1800'));
ok('bumper: all four resolve', hits(tree, 'Template_Text-Only').length === 4, JSON.stringify(hits(tree, 'Template_Text-Only')));

// Must NOT become a substring search: a bumper is one leading platform token,
// nothing else. These are the false positives the change could have bought.
let neg = N('page', [
  N('Testing_Template_Text-Only_1440x1440'),   // not a platform token
  N('Archive-Template_Text-Only_1440x1440'),   // not a platform token
  N('Copy of Template_Text-Only_1440x1440'),   // no separator token at all
  N('Board_Meta_Template_Text-Only_1440x1440'),// bumper not in FIRST position
]);
ok('bumper: does not match a non-platform prefix', hits(neg, 'Template_Text-Only').length === 0,
   JSON.stringify(hits(neg, 'Template_Text-Only')));

// A bare platform frame must not be dragged in by the stripping.
ok('bumper: Adtype_ containers match under a bumper too',
   hits(N('p', [N('Meta_Adtype_Sticky-Note_Single')]), 'Adtype_Sticky-Note').length === 1);
ok('bumper: strip leaves a non-platform name untouched',
   _stripPlatformBumper('Template_Text-Only_1440x1440') === 'Template_Text-Only_1440x1440');
ok('bumper: strip removes only the platform token',
   _stripPlatformBumper('Meta_Template_Text-Only') === 'Template_Text-Only');

// The normalized fallback has to survive the bumper as well. _normName only
// folds case and whitespace (it does NOT collapse _ vs -), so the drift it
// catches is a casing/trailing-space slip — which must still resolve once the
// frame also carries a bumper.
const nhits = (root, p) => _findAllByPrefixNorm(root, _normName(p)).map(n => n.name);
const drifted = 'Meta_template_text-only_1440x1440 ';
ok('bumper: normalized fallback matches through the bumper',
   nhits(N('p', [N(drifted)]), 'Template_Text-Only').length === 1,
   JSON.stringify(nhits(N('p', [N(drifted)]), 'Template_Text-Only')));
ok('bumper: that name is genuinely unreachable without the strip',
   _normName(drifted).indexOf(_normName('Template_Text-Only')) !== 0);

// 8. Adrie, working session 2026-09-23: "if we have generated images on a page
// from a run, will those mess with new incoming information? Will the plugin
// look at those at all because they're on the same page?" Logan: "I don't think
// so, but I'm going to be looking into this." Never answered.
//
// The answer is that assembly renames every frame it emits away from the
// Template_/Adtype_ prefixes the lookup searches for, so last run's output is
// invisible to the next run's template search. That is load-bearing and was
// never asserted — and the bumper strip above widens what matches, so it needs
// to hold under the new rule too.
const OUTPUT_NAMES = [
  'ASSEMBLED_concept-1_freelance-speed',   // code.js:2914
  'ASSEMBLED_ad_7',                        // code.js:2939 (legacy path)
  'STYLED_concept-2_1440x1800',            // code.js:2306
  'Sprint · 2026-09-27 Reddit',            // code.js:2880
  'CuratedHeadshot_dana',                  // code.js:1171
];
const priorRun = N('page', OUTPUT_NAMES.map(n => N(n)));
for (const prefix of ['Template', 'Template_', 'Adtype', 'Adtype_']) {
  ok(`prior run: output is invisible to a "${prefix}" search`,
     hits(priorRun, prefix).length === 0, JSON.stringify(hits(priorRun, prefix)));
}
ok('prior run: the bumper strip does not expose output names',
   OUTPUT_NAMES.every(n => _stripPlatformBumper(n) === n),
   JSON.stringify(OUTPUT_NAMES.map(n => [n, _stripPlatformBumper(n)]).filter(([a, b]) => a !== b)));

// And the real library on the same page must still be found alongside it.
const mixed = N('page', OUTPUT_NAMES.map(n => N(n)).concat([
  N('Template_Text-Only_Dark_1440x1440'), N('Meta_Template_Text-Only_Dark_1080x1920')]));
ok('prior run: real templates on the same page still resolve',
   hits(mixed, 'Template_Text-Only').length === 2, JSON.stringify(hits(mixed, 'Template_Text-Only')));

// 9. Exact-name lookup must survive the rename too. findContainerByName ->
// findLayerByName -> _findExactByName is a separate path from the prefix
// matchers above, and it broke differently: read live from the Meta Templates
// page 2026-09-27, the real container is "Meta_Adtype_Text-Only" at depth 1
// while an ANNOTATION frame inside its own Rules panel is still named
// "Adtype_Text-Only" at depth 3. Exact matching resolved 19 of 22 styles to the
// rules card. These walks are pre-order, so once the bumper is tolerated the
// depth-1 container is reached first and wins.
eval(grab('_bumperEq') + '\n' + grab('_bumperNormEq') + '\n'
     + grab('_findExactByName') + '\n' + grab('_findNormByName'));
const findLayerByName = (n, name) => _findExactByName(n, name) || _findNormByName(n, _normName(name));

// Real shape, real names, taken from the live file.
const container = (nm, inner) => N(nm, [N('Rules', [N(inner)]), N(inner + '_1440x1440')]);
const metaPage = N('Meta Templates', [
  container('Meta_Adtype_Text-Only', 'Adtype_Text-Only'),
  container('Meta_Adtype_Graphic-With-Text/', 'Adtype_Graphic-With-Text'),  // trailing slash, live
  container('Meta_Adtype_Bespoke/', 'Adtype_Bespoke'),                      // trailing slash, live
  container('Meta_Adtype_Sticky-Note', 'Adtype_Sticky-Note'),
]);
for (const [want, expect] of [
  ['Adtype_Text-Only', 'Meta_Adtype_Text-Only'],
  ['Adtype_Graphic-With-Text', 'Meta_Adtype_Graphic-With-Text/'],
  ['Adtype_Bespoke', 'Meta_Adtype_Bespoke/'],
  ['Adtype_Sticky-Note', 'Meta_Adtype_Sticky-Note'],
]) {
  const hit = findLayerByName(metaPage, want);
  ok(`exact lookup: "${want}" resolves to the container, not its Rules card`,
     hit && hit.name === expect, hit ? `got '${hit.name}'` : 'no match');
}

// An un-renamed file must behave exactly as before.
const legacyPage = N('Meta Templates', [container('Adtype_Text-Only', 'Adtype_Text-Only_inner')]);
ok('exact lookup: un-renamed container still resolves',
   findLayerByName(legacyPage, 'Adtype_Text-Only').name === 'Adtype_Text-Only');

// And the strip must not make unrelated names collide.
ok('exact lookup: a non-platform prefix is not stripped',
   findLayerByName(N('p', [N('Testing_Adtype_Text-Only')]), 'Adtype_Text-Only') === null);

// (exit moved to the async block below)

// 10. Layer names Elise actually shipped. Read from the live file 2026-09-28:
// the Reddit page has 4x Copy_Headline1 + 4x Copy_Headline2 and ZERO
// Copy_Headline-Left/-Right, and 4x Copy_List1..3. Her 2026-09-23 fix for the
// missing copy layers was therefore invisible to the plugin — she told Adrie it
// was done and the tool still could not fill it.
const gv = n => { const m = src.match(new RegExp('var ' + n + '\\s*=\\s*(\\[[^\\]]*\\])')); return JSON.parse(m[1].replace(/'/g,'"')); };
const L = gv('DUAL_HEADLINE_LEFT'), R = gv('DUAL_HEADLINE_RIGHT');
ok('dual headline: accepts Elise\'s Copy_Headline1/2', L.includes('Copy_Headline1') && R.includes('Copy_Headline2'), JSON.stringify([L,R]));
ok('dual headline: convention name still tried FIRST', L[0] === 'Copy_Headline-Left' && R[0] === 'Copy_Headline-Right', JSON.stringify([L,R]));

// fillListLayers: fills Copy_List1..3, and reports false when there are none so
// the caller falls back to the joined Copy_Body every other template uses.
const T2 = (name, extra={}) => ({type:'TEXT', name, characters:'', children:[], fontName:{family:'X',style:'Y'}, ...extra});
global.figma = { loadFontAsync: async () => {} };
global.log = t => logs.push(t);   // fillListLayers logs its fill count
// findLayerByName / _findExactByName / _findNormByName are already defined by
// block 9 above — re-declaring them here is a SyntaxError.
eval(grab('fitTextLayer') + '\n' + grab('setTextLayer') + '\n' + grab('fillListLayers') + '\n'
     + grab('walkChildren') + '\n' + grab('splitPipe') + '\n' + grab('fillUsVsThemCopy') + '\n'
     + grab('_withTrailingSymbolLine') + '\n' + grab('fillRedditLayers') + '\n' + grab('findAllLayersByName')
     + '\n' + grab('_findAllExactByName') + '\n' + grab('_findAllNormByName') + '\n' + grab('setFirstTextByCandidates'));
eval(src.match(/var REDDIT_LAYER_FILLS = \{[\s\S]*?\n\};/)[0].replace('var ', 'global.') + '\n' + src.match(/var STYLES_THAT_SKIP_CTA = \{[\s\S]*?\n\};/)[0].replace('var ', 'global.'));
(async () => {
  const withLists = N('tpl', [T2('Copy_List1'), T2('Copy_List2'), T2('Copy_List3')]);
  const okFill = await fillListLayers(withLists, ['Fast', 'Rated', 'Ready']);
  ok('list layers: returns true and fills all three', okFill === true &&
     withLists.children.map(c => c.characters).join('|') === 'Fast|Rated|Ready',
     JSON.stringify(withLists.children.map(c => c.characters)));
  const noLists = N('tpl', [T2('Copy_Body')]);
  ok('list layers: returns false when absent, so Copy_Body fallback runs',
     (await fillListLayers(noLists, ['a','b'])) === false);

  // 11. COPY NEVER SHRINKS (Logan, 2026-09-30). History: every copy-panel line
  // was shrunk to a 22px floor (Elise, 2026-09-29: "in the template it's 48 but
  // over yonder any of these is 22"). Geometry is the live masters: a fixed
  // 620px auto-height value box inside a clipping Notes frame.
  const fitSrc = ['_adBoundary', 'fitTextLayer', '_growCopyPanel', '_growBoardToFit', 'findDirectChildByName'].map(grab).join('\n');
  const fitEnv = src.match(/var _WRAP_HINTS[^\n]*\nvar _FIT_MARGIN[^\n]*/)[0];
  const fx = new Function('log', fitEnv + '\n' + fitSrc + '\nreturn {fitTextLayer, _growCopyPanel, _growBoardToFit};')(t => logs.push(t));

  // Fake text node whose box behaves like Figma's: a fixed-width box keeps its
  // width and grows DOWN; an auto-width one grows RIGHT.
  const textNode = ({x, y, w, chars, fs, mode, name = 'Copy_Value', parent}) => {
    const n = {type: 'TEXT', name, fontSize: fs, textAutoResize: mode, parent};
    Object.defineProperty(n, 'absoluteBoundingBox', {get() {
      const lineW = chars * n.fontSize * 0.5;
      if (n.textAutoResize === 'WIDTH_AND_HEIGHT') return {x, y, width: lineW, height: n.fontSize * 1.2};
      const lines = Math.max(1, Math.ceil(lineW / w));
      return {x, y, width: w, height: lines * n.fontSize * 1.2};
    }});
    return n;
  };
  // A Notes panel whose height can grow (Figma resize), absolute == local here.
  const notesPanel = (h) => {
    const nf = {type: 'FRAME', name: 'Notes', clipsContent: true, width: 694, height: h, parent: null, children: [],
                resize(w2, h2) { this.width = w2; this.height = h2; }};
    Object.defineProperty(nf, 'absoluteBoundingBox', {get() { return {x: 344, y: 0, width: nf.width, height: nf.height}; }});
    return nf;
  };

  // Meta: long primary text at 40px in the fixed 984px panel.
  let panelM = notesPanel(984);
  let t = textNode({x: 381, y: 300, w: 620, chars: 600, fs: 40, mode: 'HEIGHT', parent: panelM});
  panelM.children.push(t);
  logs.length = 0; fx.fitTextLayer(t);
  ok('copy panel: long Meta copy KEEPS its 40px (never shrinks)', t.fontSize === 40, 'got ' + t.fontSize);
  ok('copy panel: no overflow warning inside a panel (the panel grows instead)', !logs.some(l => /⚠/.test(l)), JSON.stringify(logs));
  fx._growCopyPanel(panelM);
  const tb = t.absoluteBoundingBox;
  ok('copy panel: the panel grew to show every line', panelM.height >= tb.y + tb.height, `panel ${panelM.height} vs text bottom ${tb.y + tb.height}`);
  // Reddit: short copy at 48px, panel untouched.
  let panelR = notesPanel(5000);
  t = textNode({x: 381, y: 300, w: 620, chars: 100, fs: 48, mode: 'HEIGHT', parent: panelR});
  panelR.children.push(t);
  fx.fitTextLayer(t); fx._growCopyPanel(panelR);
  ok('copy panel: Reddit copy stays 48px and a panel that fits is not resized', t.fontSize === 48 && panelR.height === 5000);

  // Inside an ad: never shrinks; real overflow is flagged for a designer.
  const ad = {type: 'FRAME', name: 'STYLED_concept-1_1080x1080', clipsContent: true, width: 1080, parent: null,
              absoluteBoundingBox: {x: 0, y: 0, width: 1080, height: 1080}};
  t = textNode({x: 100, y: 100, w: 0, chars: 40, fs: 60, mode: 'WIDTH_AND_HEIGHT', name: 'Profile_Name', parent: ad});
  logs.length = 0; fx.fitTextLayer(t);
  ok('ad label: overflowing text keeps its 60px', t.fontSize === 60, 'fs=' + t.fontSize);
  ok('ad label: the overflow is noted for a designer but does NOT count as ⚠ (no DEGRADED)',
     logs.some(l => /note: 'Profile_Name' runs past/.test(l)) && !logs.some(l => /⚠/.test(l)), JSON.stringify(logs));
  ok('no shrink code left in the plugin', !/fontSize\s*=\s*fs|_shrinkUntil|_FIT_MIN_FS/.test(src));

  // Board grows only when a grown panel runs past it.
  const board = (h, childBottom) => {
    const b = {type: 'FRAME', width: 3000, height: h, layoutMode: 'HORIZONTAL', counterAxisSizingMode: 'FIXED', paddingBottom: 0,
               children: [{visible: true, absoluteBoundingBox: {x: 0, y: 0, width: 10, height: childBottom}}]};
    Object.defineProperty(b, 'absoluteBoundingBox', {get() { return {x: 0, y: 0, width: 3000, height: b.height}; }});
    return b;
  };
  let bd = board(2528, 2400); fx._growBoardToFit(bd);
  ok('board: a board whose panel fits is left as it was', bd.counterAxisSizingMode === 'FIXED');
  bd = board(2528, 2900); fx._growBoardToFit(bd);
  ok('board: a board whose panel outgrew it switches to hug its content', bd.counterAxisSizingMode === 'AUTO');

  // 12. Size-only template names (Elise's rename, live on the Meta page since
  // 2026-09-29). Variant words that remain: Dark_, Alt_, Alt1_/Alt2_.
  const V = (name, {slot = true, copy = 2} = {}) => ({type: 'FRAME', name, children: [
    ...(slot ? [{type: 'RECTANGLE', name: 'Image_Placeholder', children: []}] : []),
    ...Array.from({length: copy}, (_, i) => ({type: 'TEXT', name: 'Copy_F' + i, children: []})),
  ]});
  const tonePair = [V('Dark_1440x1440'), V('1440x1440')];
  ok('size-only names: prefer light picks the UNMARKED frame, not Dark',
     selectVariant(tonePair, {prefer: 'light'}).name === '1440x1440',
     selectVariant(tonePair, {prefer: 'light'}).name);
  ok('size-only names: prefer dark still picks Dark',
     selectVariant(tonePair, {prefer: 'dark'}).name === 'Dark_1440x1440');
  ok('old names: an explicit Light frame still wins for light',
     selectVariant([V('Template_X_Dark_1440x1440'), V('Template_X_Light_1440x1440')], {prefer: 'light'}).name
       === 'Template_X_Light_1440x1440');

  // The live Testimonial container: base + Alt2 hold a photo, Alt1 is text-only.
  const testimonial = [V('1440x1440'), V('Alt1_Light_1440x1440', {slot: false}),
    V('Alt1_Dark_1440x1440', {slot: false}), V('Alt2_Light_1440x1440'), V('Alt2_Dark_1440x1440')];
  for (const prefer of ['light', 'dark']) {
    const withPhoto = selectVariant(testimonial, {hasPhoto: true, prefer});
    ok(`testimonial with a photo (${prefer}): lands on a frame that can hold it`,
       _hasImageSlot(withPhoto), withPhoto.name);
    const noPhoto = selectVariant(testimonial, {hasPhoto: false, prefer});
    ok(`testimonial without a photo (${prefer}): lands on text-only Alt1`,
       /^Alt1_/.test(noPhoto.name), noPhoto.name);
  }
  ok('photo preference: no-op when every candidate has a slot',
     selectVariant([V('Dark_1440x1440'), V('1440x1440')], {hasPhoto: false, prefer: 'light'}).name === '1440x1440');
  ok('image slot: matches every spelling in the file',
     ['Image_Placeholder', 'image_placeholder', 'Image-Placeholder', 'Left-Image-Placeholder']
       .every(nm => _hasImageSlot({type: 'FRAME', name: 'f', children: [{type: 'RECTANGLE', name: nm}]})));

  // 13. Us vs Them wrap-up lines (Elise's run 2026-09-30: 5-6 "replaced residual
  // lorem-ipsum" ⚠ per board). Shape is the live Meta 1440x1800: two columns
  // with IDENTICAL layer names, told apart only by their container.
  const LT = (name) => ({type: 'TEXT', name, characters: 'Lorem ipsum', children: [],
                         fontName: {family: 'X', style: 'Y'}});
  const col = (nm, marker) => {
    const c = N(nm, [LT('Copy_Headline'),
      N(marker === '❌' ? 'Right Bullets' : 'Left Bullets',
        [LT('Copy_Bullet1'), LT('Copy_Bullet2'), LT('Copy_Bullet3'), {type: 'TEXT', name: marker, characters: marker, children: []}]),
      LT('Copy_Subhead')]);
    c.children.forEach(k => { k.parent = c; (k.children || []).forEach(g => g.parent = k); });
    return c;
  };
  const uvt = N('1440x1800', [col('Right_Copy_Them', '❌'), col('Left_Copy_Us', '✅')]);
  uvt.children.forEach(k => k.parent = uvt);
  await fillUsVsThemCopy(uvt, {
    Us_Headline: 'Upwork way', Them_Headline: 'Old way',
    Us_Bullets: 'Proposals in hours|Rated pros|Pay per milestone',
    Them_Bullets: 'Weeks of sourcing|Unknown fit|Big retainers',
    Us_Subhead: 'Hire this week — not next quarter', Them_Subhead: 'Slow, pricey, and a gamble'});
  const texts = []; (function w(n){ if (n.type === 'TEXT') texts.push(n); (n.children||[]).forEach(w); })(uvt);
  const lorem = texts.filter(t => /lorem/i.test(t.characters));
  ok('us vs them: no lorem ipsum left (headlines, bullets AND wrap-ups)', lorem.length === 0,
     lorem.map(t => t.name).join(', '));
  const [them, us] = uvt.children;
  const val = (c, nm) => (function f(n){ if (n.name === nm) return n.characters; for (const k of n.children||[]) { const r = f(k); if (r) return r; } })(c);
  ok('us vs them: wrap-ups land on the right side',
     val(us, 'Copy_Subhead') === 'Hire this week — not next quarter' && val(them, 'Copy_Subhead') === 'Slow, pricey, and a gamble',
     `us='${val(us, 'Copy_Subhead')}' them='${val(them, 'Copy_Subhead')}'`);
  ok('us vs them: headlines land on the right side by container',
     val(us, 'Copy_Headline') === 'Upwork way' && val(them, 'Copy_Headline') === 'Old way',
     `us='${val(us, 'Copy_Headline')}' them='${val(them, 'Copy_Headline')}'`);

  // 14. Reddit layer map (live Reddit page, 2026-09-30). Each case is a real
  // template's Copy_* names with its stock text; every one must take the copy.
  const R = (kids) => { const t = N('tpl', kids); (function p(n){ (n.children||[]).forEach(k => { k.parent = n; p(k); }); })(t); return t; };
  const TX = (name, characters) => ({type: 'TEXT', name, characters, children: [], fontName: {family: 'X', style: 'Y'}});
  const row = {Platform: 'Reddit', CTA: 'Post a project', Headline_On_Creative: 'HL', Subhead_On_Creative: 'SUB',
               Left_Headline: 'Speed', Right_Headline: 'Cost', Single_Headline: 'UNDER',
               Single_Bullets: 'A|B|C', Search_Results: 'TERM'};
  const chars = (t, nm) => { const out = []; (function w(n){ if (n.name === nm) out.push(n.characters); (n.children||[]).forEach(w); })(t); return out; };
  let rt = R([TX('Copy_Headline2', 'Job filled'), TX('Copy_Headline1', 'Job posted')]);
  await fillRedditLayers(rt, 'graphic with text', row);
  ok('reddit GWT: Headline1/Headline2 take the two on-creative lines',
     chars(rt, 'Copy_Headline1')[0] === 'HL' && chars(rt, 'Copy_Headline2')[0] === 'SUB');
  rt = R([TX('Copy_Title2', 'data experts')]); await fillRedditLayers(rt, 'search', row);
  ok('reddit Search: Copy_Title2 takes the headline', chars(rt, 'Copy_Title2')[0] === 'HL');
  for (const st of ['note', 'twitter', 'notification']) {
    rt = R([TX('Copy_Body', 'stock')]); await fillRedditLayers(rt, st, row);
    ok(`reddit ${st}: Copy_Body takes the headline`, chars(rt, 'Copy_Body')[0] === 'HL');
  }
  rt = R([TX('Copy_Left', 'Lorem\n💰'), TX('Copy_Right', 'Lorem\n🐻'), TX('Copy_BodyCenter', 'x'), TX('Copy_Subhead', 'y')]);
  await fillRedditLayers(rt, 'venn diagram', row);
  ok('reddit Venn: words replaced, emoji line kept',
     chars(rt, 'Copy_Left')[0] === 'Speed\n💰' && chars(rt, 'Copy_Right')[0] === 'Cost\n🐻', JSON.stringify([chars(rt,'Copy_Left'), chars(rt,'Copy_Right')]));
  ok('reddit Venn: overlap line and underline in the right slots',
     chars(rt, 'Copy_BodyCenter')[0] === 'SUB' && chars(rt, 'Copy_Subhead')[0] === 'UNDER');
  rt = R([TX('Copy_Title2', 'Chatbot Developer'), TX('Copy_Title2', 'Pay Hourly'), TX('Copy_Title2', 'Flat-rate'), TX('Copy_Title2', 'Project-based')]);
  await fillRedditLayers(rt, 'search and checkbox', row);
  ok('reddit Search & Checkbox Alt: search term then the three items', chars(rt, 'Copy_Title2').join('|') === 'TERM|A|B|C', chars(rt, 'Copy_Title2').join('|'));
  ok('every Copy_CTA is filled in board mode, not just the first (Us vs Them, Carousel)',
     /findAllLayersByName\(styledClone, "Copy_CTA"\)/.test(src));
  ok('pie centre accepts Copy_Center first', /\["Copy_Center", "Center_Callout_Text"/.test(src));

  // 15. Naming convention tool (Preview / Apply naming). Cases are real names
  // from the unconverted platform pages and the Meta page, 2026-09-30.
  eval(['_conventionPlatform', '_conventionStyleSlug', '_conventionTemplateName',
             '_conventionTextName', 'conventionPlan'].map(grab).join('\n') + '\n'
            + src.match(/var CONVENTION_VARIANTS = \[[^\]]*\];/)[0].replace('var ', 'global.') + '\n'
            + src.match(/var CONVENTION_PREFIX = \{[\s\S]*?\};/)[0].replace('var ', 'global.') + '\n'
            + src.match(/var _CONVENTION_IMG = \{[\s\S]*?\};/)[0].replace('var ', 'global.'));
  const F = (name, w, h, kids = []) => ({type: 'FRAME', name, width: w, height: h, children: kids});
  const TXT = (name, characters = 'x') => ({type: 'TEXT', name, characters, children: []});
  const pg = {type: 'PAGE', name: '    -> Linkedin Templates', children: [
    F('AdType_Us-Vs-Them', 5000, 2000, [F('Rules', 1500, 1300), F('Template_Us-Vs-Them_1440x1440', 1440, 1440, [TXT('cta_text'), TXT('Copy_CTA')])]),
    F('Adtype: Meme', 5000, 2000, [F('Template_Meme_Light_1440x1440', 1440, 1440), F('Template_Meme_Dark_1440x1880', 1440, 1800, [{type: 'RECTANGLE', name: 'right_image_placeholder'}])]),
    F('Adtype_Pie-Chart', 5000, 2000, [F('Adtype_Pie-Chart__1440x1800', 1440, 1800, [TXT('TextOnly_Subhead_Text', 'Lorem Subhead')])]),
    F('Adtype_Carousel', 9000, 2000, [F('1440x1440 - Carousel', 4723, 1792), F('1440x1440 - Carousel Photo', 6030, 1598)]),
    F('Adtype_Testimonial', 9000, 2000, [F('Template_Testimonial-Photo_1440x1440', 1440, 1440),
      F('Template_Testimonial-Text-Only_Light_1440x1440', 1440, 1440), F('Template_Testimonial-Text-Only_Dark_1440x1440', 1440, 1440),
      F('Template_Testimonial-Text-and-Photo_Light_1440x1440', 1440, 1440)]),
    F('Adtype_Mockup', 5000, 2000, [F('Template_Mockup_1440x1440', 1440, 1440, [TXT('Notification_Headline_Text', 'Upwork @Upwork')])]),
  ]};
  const plan = conventionPlan(pg).plan;
  const to = (from) => (plan.find(p => p.from === from) || {}).to;
  ok('naming: container gets the platform prefix', to('AdType_Us-Vs-Them') === 'Linkedin_Adtype_Us-Vs-Them' && to('Adtype: Meme') === 'Linkedin_Adtype_Meme');
  ok('naming: Light is unmarked, Dark is kept', to('Template_Meme_Light_1440x1440') === '1440x1440');
  ok('naming: a size typo is corrected from the frame', to('Template_Meme_Dark_1440x1880') === 'Dark_1440x1800');
  ok('naming: carousel keeps its name size (frame holds several cards)', to('1440x1440 - Carousel') === '1440x1440' && to('1440x1440 - Carousel Photo') === 'Photo_1440x1440');
  ok('naming: Testimonial families follow the Meta mapping',
     to('Template_Testimonial-Photo_1440x1440') === '1440x1440' && to('Template_Testimonial-Text-Only_Light_1440x1440') === 'Alt1_1440x1440'
     && to('Template_Testimonial-Text-Only_Dark_1440x1440') === 'Alt1_Dark_1440x1440' && to('Template_Testimonial-Text-and-Photo_Light_1440x1440') === 'Alt2_1440x1440',
     JSON.stringify(plan.filter(p => /Testimonial-/.test(p.from)).map(p => p.to)));
  ok('naming: pie centre becomes Copy_Center, not Copy_Subhead', to('TextOnly_Subhead_Text') === 'Copy_Center');
  ok('naming: legacy CTA joins the existing Copy_CTA (several per template is normal)', to('cta_text') === 'Copy_CTA' && !plan.find(p => p.from === 'cta_text').skip);
  ok('naming: fixed handle is left alone', !plan.some(p => p.from === 'Notification_Headline_Text'));
  ok('naming: image slot spelling', to('right_image_placeholder') === 'Right-Image-Placeholder');
  // Apply, then plan again: nothing left to do.
  plan.forEach(p => { if (!p.skip) p.node.name = p.to; });
  ok('naming: a second run renames nothing', conventionPlan(pg).plan.length === 0, JSON.stringify(conventionPlan(pg).plan.map(p => p.from + '→' + p.to)));
  ok('naming: an unconverted counter stays out of Copy_', _conventionTextName({name: 'TextOnly_Subhead_Text', characters: '1,530'}, 'App-Notification') === null);

  process.exit(fails ? 1 : 0);
})();
