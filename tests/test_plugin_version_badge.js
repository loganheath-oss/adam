// Every ADAM plugin must show its version on its main panel (Logan,
// 2026-09-30 — a designer spent the day on a month-old copy and nobody could
// tell). Loads each plugin's real ui.html script against a stub DOM, delivers
// the version message the plugin's code.js sends, and checks the badge.
// Assembly also asks ADAM which version is current and flags a stale copy.
const fs = require('fs');
let fails = 0;
const ok = (label, cond, detail = '') => {
  console.log((cond ? '  PASS ' : '  FAIL ') + label + (cond ? '' : ' — ' + detail));
  if (!cond) fails++;
};

function runPanel(uiPath, { latest } = {}) {
  const html = fs.readFileSync(uiPath, 'utf8');
  const script = (html.match(/<script>([\s\S]*?)<\/script>/g) || [])
    .map(s => s.replace(/<\/?script>/g, '')).join('\n');
  const els = {};
  const el = (id) => els[id] || (els[id] = new Proxy({ id, textContent: '', className: '', value: '', style: {}, children: [] }, {
    get(t, k) {
      if (k in t) return t[k];
      if (k === 'addEventListener' || k === 'appendChild' || k === 'removeChild' || k === 'setAttribute' ||
          k === 'focus' || k === 'select' || k === 'click' || k === 'querySelector' || k === 'querySelectorAll')
        return () => (k === 'querySelectorAll' ? [] : el(id + '.' + String(k)));
      if (k === 'classList') return { add() {}, remove() {}, toggle() {}, contains() { return false; } };
      return undefined;
    },
    set(t, k, v) { t[k] = v; return true; },
  }));
  const sent = [];
  const pending = [];
  const sandbox = {
    document: { getElementById: el, createElement: (t) => el('new-' + t + Math.random()), querySelector: () => el('q'),
                querySelectorAll: () => [], addEventListener() {}, body: el('body') },
    parent: { postMessage: (m) => sent.push(m.pluginMessage) },
    window: {},
    fetch: (url) => { const p = Promise.resolve({ ok: true, json: () => Promise.resolve({ version: latest }) }); pending.push(p); return p; },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    setTimeout, console, alert() {}, confirm: () => false,
  };
  sandbox.window = sandbox;
  // Two panels assign a bare `onmessage =` (an implicit global): clear it first
  // so one panel's handler can never answer for the next.
  delete globalThis.onmessage;
  const fn = new Function(...Object.keys(sandbox), script + '\n;return window.onmessage || (typeof onmessage !== "undefined" ? onmessage : null);');
  const handler = fn(...Object.values(sandbox));
  return { els, sent, handler, pending, sandbox };
}

(async () => {
  const panels = [
    ['plugin/ui.html', 'plugin/code.js', true],
    ['plugin/library_tagger/ui.html', 'plugin/library_tagger/code.js', false],
    ['plugin/tag_manager/ui.html', 'plugin/tag_manager/code.js', false],
  ];
  for (const [ui, code, checksLatest] of panels) {
    const src = fs.readFileSync(code, 'utf8');
    const ver = (src.match(/var PLUGIN_VERSION = "([^"]+)"/) || [])[1];
    ok(`${code}: declares PLUGIN_VERSION`, !!ver);
    ok(`${code}: sends it to the panel on start and on request`,
       /figma\.ui\.postMessage\(\{ type: "plugin-version", version: PLUGIN_VERSION \}\)/.test(src) && /msg\.type === "get-version"/.test(src));
    ok(`${ui}: version badge sits in the main heading`, /<h1>[^<]*<span id="plugin-version"/.test(fs.readFileSync(ui, 'utf8')));

    const p = runPanel(ui, { latest: ver });
    ok(`${ui}: panel asks for the version once loaded`, p.sent.some(m => m && m.type === 'get-version'));
    const h = p.handler || p.sandbox.window.onmessage;
    h({ data: { pluginMessage: { type: 'plugin-version', version: ver } } });
    await Promise.all(p.pending); await new Promise(r => setTimeout(r, 0));
    ok(`${ui}: badge reads v${ver}`, p.els['plugin-version'] && p.els['plugin-version'].textContent === 'v' + ver,
       p.els['plugin-version'] && p.els['plugin-version'].textContent);
    if (checksLatest) {
      ok(`${ui}: current copy says ✓ Latest`, /Latest/.test(p.els['version-status'].textContent), p.els['version-status'].textContent);
      const q = runPanel(ui, { latest: '2099.01.01' });
      (q.handler || q.sandbox.window.onmessage)({ data: { pluginMessage: { type: 'plugin-version', version: ver } } });
      await Promise.all(q.pending); await new Promise(r => setTimeout(r, 0));
      ok(`${ui}: an old copy is flagged with where to get the new one`,
         /Out of date — v2099\.01\.01 .*\/plugin/.test(q.els['version-status'].textContent) && /stale/.test(q.els['plugin-version'].className),
         q.els['version-status'].textContent);
    }
  }
  process.exit(fails ? 1 : 0);
})();
