// Harness: load selectVariant + countCopyLayers out of plugin/code.js and drive
// them with fake Figma nodes. The plugin cannot be run outside Figma desktop, so
// this replays the chosen functions against the shapes the file actually holds.
const fs = require('fs');
const src = fs.readFileSync('plugin/code.js', 'utf8');
function grab(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('not found: ' + name);
  let d = 0, started = false;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') { d++; started = true; }
    else if (src[j] === '}') { d--; if (started && d === 0) return src.slice(i, j + 1); }
  }
}
const logs = [];
const ctx = { log: t => logs.push(t) };
eval(grab('countCopyLayers') + '\n' + grab('selectVariant')
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

process.exit(fails ? 1 : 0);
