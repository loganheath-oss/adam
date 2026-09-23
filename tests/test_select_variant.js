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

process.exit(fails ? 1 : 0);
