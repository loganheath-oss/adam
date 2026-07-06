// Upwork Pipeline Assembly — Figma Plugin (v4)
// =================================================
// Reads a manifest CSV and assembles styled ads inside Figma.
//
// Modes (auto-detected from the captured "template"):
//   - "styled_per_row" — captured frame contains Template_* descendants.
//     For each manifest row, finds the matching styled ad template by
//     visual_style + dimensions, clones it, fills image_placeholder
//     and the style-specific headline/CTA text. Best for the new
//     multi-style world (Apr 30+).
//   - "concept_board"  — captured frame has Frame 13 + Frame 14.
//     One board per concept_tag with Copy Version 1 filled, Copy
//     Version 2 hidden, 3 image frames matched by dimension.
//   - "legacy"         — fallback: clone per row, fill image_placeholder,
//     headline_text, body_text, cta_text by exact name.
//
// All styled-template lookup is name-based:
//   visual_style "Lifestyle Photo"      → searches for Template_LifestylePhoto_<W>x<H>
//   visual_style "Photo with Text"      → searches for Template_PhotoWithText_<W>x<H>
//   visual_style "Testimonial"          → searches for Template_TestimonialA_* or _TestimonialB_*
//   visual_style "Sticky Note"          → searches for Template_StickyNote_* (falls back to TestimonialA placeholder)
// The first matching frame or COMPONENT_SET wins. COMPONENT_SETs use
// their first child variant.

figma.showUI(__html__, { width: 460, height: 640 });

var capturedTemplateId = null;
var capturedDestinationId = null;

var LEGACY_LAYER_NAMES = {
  image:    "image_placeholder",
  headline: "headline_text",
  body:     "body_text",
  cta:      "cta_text",
};

// Visual style → template name prefix(es). First match wins; subsequent
// entries are fallbacks for styles whose primary template doesn't exist yet.
var STYLE_TEMPLATE_PREFIXES = {
  "lifestyle photo": ["Template_LifestylePhoto"],
  "photo with text": ["Template_PhotoWithText"],
  "testimonial":     ["Template_TestimonialC", "Template_TestimonialB", "Template_TestimonialA"],
  "sticky note":     ["Template_StickyNote", "Template_TestimonialA"],
  "text with button": ["Template_TextWithButton"],
  // Notification: variant frames are misnamed Template_ChatBubble_* in the
  // current file. Container scoping (STYLE_ADTYPE_CONTAINERS) keeps this from
  // colliding with the real Chat Bubble adtype.
  "notification":    ["Template_Notification", "Template_ChatBubble"],
  "chat bubble":     ["Template_ChatBubble"],
  // Text Only frames are named Template_TestimonialC_* (Brandon re-used the
  // TestimonialC base). Container scoping isolates them from Testimonial.
  "text only":       ["Template_TestimonialC"],
  // Split Screen has clean unique naming.
  "split screen":    ["Template_SplitScreen"],
  // Reminder lives in its own template — clean naming.
  "reminder":        ["Template_Reminder"],
  // Meme frames ALSO named Template_SplitScreen_* (Brandon reused the
  // SplitScreen skeleton). Container scoping (STYLE_ADTYPE_CONTAINERS)
  // keeps Meme from colliding with the real Split Screen adtype.
  "meme":            ["Template_SplitScreen"],
  // ── New styles (2026-06-22): rebuilt on reused base skeletons; the Adtype
  // container (STYLE_ADTYPE_CONTAINERS) disambiguates the shared prefixes.
  "poll":            ["Template_SplitScreen"],
  "us vs them":      ["Template_TestimonialC"],
  "platform ui":     ["Template_ChatBubble"],
  "search results":  ["Template_ChatBubble", "Template_TestimonialC"],
  "device ui":       ["Template_TestimonialC"],
  "hybrid":          ["Template_PhotoWithTextB", "Template_PhotoWithText"],
  "pie chart":       ["Template_TestimonialC"],
  "social media profile": ["Template_TestimonialC"],
  "talent profile":  ["Template_TestimonialC"],
  // Mockup is a multi-row notification mock on the Reminder base. Its 6 body
  // layers all share the name Notification_Headline_Text, so only the primary
  // one fills (via the reminder branch); per-row copy needs distinct layer
  // names in Figma.
  "tweet / post mockup":          ["Template_Reminder"],
  // Aliases handled by normalize()
};

// Visual style → preferred Adtype container name. The plugin searches inside
// this container FIRST so style-specific templates win over name collisions
// (e.g., Brandon's Sticky Note template is named "Template_TestimonialA"
// internally but lives inside "Adtype: Sticky Note").
var STYLE_ADTYPE_CONTAINERS = {
  "lifestyle photo": ["Adtype: Lifestyle Photo (Full Bleed)", "Adtype: Lifestyle Photo"],
  "photo with text": ["Adtype: Photo with Text"],
  "testimonial":     ["Adtype: Testimonial Variants", "Adtype: Testimonial"],
  "sticky note":     ["Adtype: Sticky Note"],
  "text with button": ["Adtype: Text with Button"],
  "notification":    ["Adtype: Notification"],
  "chat bubble":     ["Adtype: Chat Bubble"],
  "text only":       ["Adtype: Text Only"],
  "split screen":    ["Adtype: Split Screen"],
  "reminder":        ["Adtype: Reminder"],
  "meme":            ["Adtype: Meme"],
  // New styles (2026-06-22) — container scoping is what isolates these, since
  // several share the Template_TestimonialC / Template_ChatBubble bases.
  "poll":            ["Adtype: Poll"],
  "us vs them":      ["AdType: UsVsThem"],
  "platform ui":     ["AdType_PlatformUI"],
  "search results":  ["AdType_SearchResults"],
  "device ui":       ["Upwork - Mobile Homepage"],
  "hybrid":          ["AdType: Hybrid"],
  "pie chart":       ["AdType: PieChart"],
  "social media profile": ["AdType: SocialMediaProfile"],
  "talent profile":  ["AdType: TalentProfile"],
  "tweet / post mockup":          ["Adtype: Mockup"],
};

// When a template is a COMPONENT_SET, prefer variants whose name contains one
// of these substrings (in priority order). Falls through to children[0] when
// no preferred variant is found. Per-style so each ad type can pick the right
// look without affecting others.
var STYLE_VARIANT_PREFERENCES = {
  "lifestyle photo": ["Light Mode", "Default", "White Text"],
  "photo with text": ["Light Mode", "Default"],
  "testimonial":     ["Light Mode", "Default"],
  "sticky note":     ["Light Mode", "Default"],
  "text with button": ["Light Mode", "Default"],
  "notification":    ["Light Mode", "Default"],
  "chat bubble":     ["Light Mode", "Default"],
};

// Per-style headline layer name preferences (in lookup order).
var STYLE_HEADLINE_LAYERS = {
  "lifestyle photo": ["LifestylePhoto_Headline_Text", "headline_text"],
  "photo with text": ["PhotoWithText_Headline_Text", "headline_text"],
  "testimonial":     ["Notification_Headline_Text", "headline_text", "Testimonial_Headline_Text"],
  "sticky note":     ["Left_Headline_Text", "headline_text"],
  // Text with Button: the button label IS the only text. The CTA layer doubles
  // as the headline (this style has no separate body or CTA copy).
  "text with button": ["cta_text", "TextWithButton_Headline_Text", "headline_text"],
  "notification":    ["Notification_Headline_Text", "headline_text"],
  "chat bubble":     ["ChatBubble_Headline_Text", "headline_text"],
  "text only":       ["TextOnly_headline_text", "headline_text"],
  "split screen":    ["SplitScreen_Headline_Text", "headline_text"],
  // Meme reuses SplitScreen_Headline_Text because Brandon cloned the SplitScreen
  // skeleton. The caption is the meme's punchline (e.g. "POV: Me waking up...").
  "meme":            ["SplitScreen_Headline_Text", "headline_text"],
  // Reminder is handled by a special branch in assembleStyledPerRow (see
  // `if (key === "reminder")`) because its two body-area text layers share
  // the name Notification_Headline_Text. This entry exists only as a
  // documentation / fallback safety net — the special branch returns before
  // the generic STYLE_HEADLINE_LAYERS flow runs.
  "reminder":        ["Notification_Headline_Text", "headline_text"],
  // New styles (2026-06-22) — exact headline layer names from the live file.
  "poll":            ["SplitScreen_Headline_Text", "headline_text"],
  "us vs them":      ["UsVsThem_headline_text", "headline_text"],
  "platform ui":     ["TextOnly_headline_text", "headline_text"],
  "search results":  ["TextOnly_headline_text", "headline_text"],
  "device ui":       ["TextOnly_headline_text", "headline_text"],
  "hybrid":          ["PhotoWithText_Headline_Text", "headline_text"],
  // Social Media Profile: the ad message lives in "Subhead-Text" (no separate
  // headline layer). Talent Profile has no message layer yet — only its CTA
  // fills; the profile content is static mock until a copy layer is added.
  "social media profile": ["Subhead-Text", "headline_text"],
  "talent profile":  ["headline_text"],
};

var STYLE_BULLET_LAYERS = {
  "sticky note": ["right_headline_text", "Right_Headline_Text"],
  // Us vs Them: six comparison bullets (3 "us" + 3 "them") + the "them" headline.
  // Generic flow fills the primary headline + cta; full bullet fill is follow-up.
  "us vs them": ["UsVsThem_Bullet1", "UsVsThem_Bullet2", "UsVsThem_Bullet3",
                 "UsVsThem_Bullet4", "UsVsThem_Bullet5", "UsVsThem_Bullet6"],
};

// Per-style secondary copy layer (subhead / stat line) — filled with the short
// copy after the headline + CTA. Exact layer names from the live file.
var STYLE_SUBHEAD_LAYERS = {
  "photo with text": ["PhotoWithText_SubHeadline_Text"],
  "hybrid":          ["PhotoWithText_SubHeadline_Text"],
  "poll":            ["Stat Block Text"],
};

// Styles where the manifest's library photo should NOT overwrite template
// imagery. Testimonial keeps its own headshot + green gradient; Text with
// Button has no real image (the "image fills" are decorative gradients).
var STYLES_THAT_SKIP_IMAGE = {
  "testimonial":      true,
  "text with button": true,
  "chat bubble":      true,
  // Text Only and Reminder are gradient/notification graphics with no photo slot.
  "text only":        true,
  "reminder":         true,
  // Meme templates ship with the meme image baked in (layer name is the
  // specific meme handle, e.g. "this-is-fine 1"). Pipeline never supplies
  // an image for Meme — adding a new meme requires a new template family.
  "meme":             true,
  // New styles (2026-06-22) that are graphic/UI only (no photo slot to fill).
  // Hybrid is NOT here — it has a real image_placeholder.
  "us vs them":       true,
  "platform ui":      true,
  "search results":   true,
  "device ui":        true,
  // Poll HAS a real Image-Placeholder (full-bleed photo behind the card) — it
  // must receive a library photo so polls don't all repeat the template image.
  // Pie Chart is a vector/gradient graphic — no photo; the slice is drawn by
  // fillPieChartValue() from the manifest's Chart_Pct.
  "pie chart":        true,
  // Profile mocks ship with their own avatar/UI; no library photo slot.
  "social media profile": true,
  "talent profile":   true,
  // Mockup is a notification graphic — no photo slot.
  "tweet / post mockup":           true,
  // Bespoke = blank text-only starter (headline + subhead + CTA, no image) per
  // the product spec; leave its image placeholders empty for the designer.
  "bespoke":                       true,
  // Illustration / Graphic-with-Text use a built-in Illustration_Card graphic;
  // a generated illustration is a pipeline concern (PNG→Figma) not yet wired,
  // so don't overwrite with a library photo.
  "illustration":                  true,
  "graphic with text":             true,
};

// Styles whose template has MORE THAN ONE image placeholder. Today's filler
// picks one canonical target; these need per-style handling. Currently flagged
// for diagnostics only — actual dual-fill logic is TODO and tracked in registry.
var STYLES_WITH_DUAL_IMAGE = {
  "split screen": ["left_image_placeholder", "right_image_placeholder"],
};

// Styles where the CTA write should be skipped.
//   - Text with Button: cta_text doubles as the headline target
//   - Chat Bubble: cta_text is a category-label pill ("Small Business Wins"),
//     not a CTA — Brandon edits it manually per concept
var STYLES_THAT_SKIP_CTA = {
  "text with button": true,
  // Meme: the cta_text layer exists but its parent Cta Pill frame is hidden
  // in Brandon's design. Writing a CTA would be a no-op visually anyway —
  // skip to avoid clobbering the template's intentional hidden state.
  "meme":             true,
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function log(text) {
  figma.ui.postMessage({ type: "log", text: text });
}
function err(text) {
  figma.ui.postMessage({ type: "error", text: text });
}

function walkChildren(node, cb) {
  if (!("children" in node)) return;
  for (var i = 0; i < node.children.length; i++) {
    cb(node.children[i]);
    walkChildren(node.children[i], cb);
  }
}

function findLayerByName(node, name) {
  if (node.name === name) return node;
  if ("children" in node) {
    for (var i = 0; i < node.children.length; i++) {
      var found = findLayerByName(node.children[i], name);
      if (found) return found;
    }
  }
  return null;
}

function findAllLayersByName(node, name) {
  var results = [];
  if (node.name === name) results.push(node);
  if ("children" in node) {
    for (var i = 0; i < node.children.length; i++) {
      var sub = findAllLayersByName(node.children[i], name);
      for (var j = 0; j < sub.length; j++) results.push(sub[j]);
    }
  }
  return results;
}

function findAllByPrefix(node, prefix) {
  var results = [];
  if (node.name && node.name.indexOf(prefix) === 0) results.push(node);
  if ("children" in node) {
    for (var i = 0; i < node.children.length; i++) {
      var sub = findAllByPrefix(node.children[i], prefix);
      for (var j = 0; j < sub.length; j++) results.push(sub[j]);
    }
  }
  return results;
}

function findDirectChildByName(node, name) {
  if (!("children" in node)) return null;
  for (var i = 0; i < node.children.length; i++) {
    if (node.children[i].name === name) return node.children[i];
  }
  return null;
}

// Walks the subtree and detaches every INSTANCE so all descendants become
// regular FRAMEs (or text/rectangles). After this, Brandon can edit any layer
// freely — no "main component" lock, no override restrictions.
function detachAllInstances(node) {
  if (!node) return node;
  if (node.type === "INSTANCE" && typeof node.detachInstance === "function") {
    try {
      node = node.detachInstance();
    } catch (e) {
      // Some instances can't be detached (e.g., from external libraries) — leave them.
    }
  }
  if (node && "children" in node) {
    var children = node.children.slice(); // copy because detachInstance may mutate
    for (var i = 0; i < children.length; i++) {
      detachAllInstances(children[i]);
    }
  }
  return node;
}

function normalizeStyle(s) {
  if (!s) return "";
  return s.toLowerCase()
          .replace(/\s*\(.*?\)\s*/g, "") // strip "(full bleed)" etc
          .trim();
}

function parseResolutionToWH(s) {
  if (!s) return null;
  var m = String(s).replace(/×/g, "x").match(/(\d+)\s*x\s*(\d+)/i);
  if (!m) return null;
  return [parseInt(m[1], 10), parseInt(m[2], 10)];
}

function nodeWH(n) {
  if (!n || !("absoluteBoundingBox" in n) && !("width" in n)) return null;
  if ("width" in n && "height" in n) return [Math.round(n.width), Math.round(n.height)];
  return null;
}

// ── CSV ──────────────────────────────────────────────────────────────────────

function parseCSV(text) {
  var lines = text.split(/\r?\n/).filter(function (l) { return l.trim().length > 0; });
  if (lines.length < 2) throw new Error("CSV has no data rows");
  var headers = parseCSVLine(lines[0]);
  var rows = [];
  for (var i = 1; i < lines.length; i++) {
    var cells = parseCSVLine(lines[i]);
    var row = {};
    for (var j = 0; j < headers.length; j++) {
      row[headers[j].trim()] = (cells[j] || "").trim();
    }
    rows.push(row);
  }
  return rows;
}

function parseCSVLine(line) {
  var cells = [];
  var current = "";
  var inQuotes = false;
  for (var i = 0; i < line.length; i++) {
    var c = line[i];
    if (c === '"' && line[i + 1] === '"') {
      current += '"';
      i++;
    } else if (c === '"') {
      inQuotes = !inQuotes;
    } else if (c === "," && !inQuotes) {
      cells.push(current);
      current = "";
    } else {
      current += c;
    }
  }
  cells.push(current);
  return cells;
}

// ── Capture template ─────────────────────────────────────────────────────────

function detectTemplateMode(t) {
  // Priority: styled_per_row > concept_board > legacy
  var hasTemplateChildren = findAllByPrefix(t, "Template_").filter(function (n) {
    return n.id !== t.id; // exclude self
  }).length > 0;
  if (hasTemplateChildren) return "styled_per_row";

  var f13 = findLayerByName(t, "Frame 13");
  var f14 = findLayerByName(t, "Frame 14");
  if (f13 && f14) return "concept_board";

  return "legacy";
}

// Auto-discover the best document-wide search root for templates, so assembly
// works from ANY page with no manual "Capture Template" step and no need to
// pick which templates to use. Prefers the page named like a template library;
// otherwise the single page that has Template_* frames; otherwise the whole
// document (figma.root) so the finder can scope by Adtype container across pages.
function findTemplatesRoot() {
  var pages = figma.root.children;
  var withTemplates = [];
  for (var i = 0; i < pages.length; i++) {
    if (findAllByPrefix(pages[i], "Template_").length > 0) withTemplates.push(pages[i]);
  }
  for (var j = 0; j < withTemplates.length; j++) {
    if (/template/i.test(withTemplates[j].name)) return withTemplates[j];
  }
  if (withTemplates.length === 1) return withTemplates[0];
  return figma.root; // spread across pages (or none here) — search the whole file
}

function captureTemplate() {
  var sel = figma.currentPage.selection;
  if (sel.length === 0) {
    err("Nothing selected. Select an Adtype container, concept board, or template, then click Capture.");
    return;
  }
  if (sel.length > 1) {
    err("Multiple items selected. Select exactly one.");
    return;
  }
  var t = sel[0];
  if (t.type !== "FRAME" && t.type !== "COMPONENT" && t.type !== "INSTANCE" && t.type !== "SECTION") {
    if (t.parent && (t.parent.type === "FRAME" || t.parent.type === "COMPONENT" || t.parent.type === "INSTANCE" || t.parent.type === "SECTION")) {
      log("Selected " + t.type + " — climbing to parent: " + t.parent.name);
      t = t.parent;
    } else {
      err("Captured node must be a FRAME, COMPONENT, INSTANCE, or SECTION — got " + sel[0].type);
      return;
    }
  }
  capturedTemplateId = t.id;
  var mode = detectTemplateMode(t);
  log("Captured: " + t.name + " (" + t.type + ", mode=" + mode + ")");

  if (mode === "styled_per_row") {
    var templates = findAllByPrefix(t, "Template_");
    log("  Template_* descendants: " + templates.length);
    var sizes = {};
    for (var i = 0; i < templates.length; i++) {
      var wh = nodeWH(templates[i]);
      if (wh) {
        var key = wh[0] + "x" + wh[1];
        sizes[key] = (sizes[key] || 0) + 1;
      }
    }
    var sizeStrs = [];
    for (var k in sizes) sizeStrs.push(k + " (×" + sizes[k] + ")");
    log("  Sizes available: " + sizeStrs.join(", "));
  } else if (mode === "concept_board") {
    log("  Concept-board mode (Frame 13 + Frame 14 detected)");
  } else {
    log("  Legacy mode (single image_placeholder per clone)");
  }

  figma.ui.postMessage({ type: "template-captured", name: t.name + " [" + mode + "]" });
}

function captureDestination() {
  var sel = figma.currentPage.selection;
  if (sel.length === 0) {
    capturedDestinationId = null;
    log("Destination cleared. Output goes to viewport center.");
    figma.ui.postMessage({ type: "destination-captured", name: "(none)" });
    return;
  }
  if (sel.length > 1) {
    err("Multiple items selected. Select exactly one destination.");
    return;
  }
  var d = sel[0];
  if (d.type !== "FRAME" && d.type !== "SECTION" && d.type !== "GROUP" && d.type !== "COMPONENT") {
    err("Destination must be a FRAME, SECTION, GROUP, or COMPONENT.");
    return;
  }
  capturedDestinationId = d.id;
  log("Destination captured: " + d.name);
  figma.ui.postMessage({ type: "destination-captured", name: d.name });
}

// ── Image fill ──────────────────────────────────────────────────────────────

function findSourceImageFill(libraryNode) {
  if ("fills" in libraryNode && Array.isArray(libraryNode.fills)) {
    for (var i = 0; i < libraryNode.fills.length; i++) {
      if (libraryNode.fills[i].type === "IMAGE") return libraryNode.fills[i];
    }
  }
  var found = null;
  walkChildren(libraryNode, function (n) {
    if (found) return;
    if ("fills" in n && Array.isArray(n.fills)) {
      for (var i = 0; i < n.fills.length; i++) {
        if (n.fills[i].type === "IMAGE") { found = n.fills[i]; return; }
      }
    }
  });
  return found;
}

function applyImageFillToLayer(layer, sourceFill) {
  if (!("fills" in layer)) return false;
  var newFills = [];
  var existing = Array.isArray(layer.fills) ? layer.fills : [];
  var replaced = false;
  for (var f = 0; f < existing.length; f++) {
    if (existing[f].type === "IMAGE" && !replaced) {
      var copy = Object.assign({}, sourceFill);
      copy.scaleMode = existing[f].scaleMode || sourceFill.scaleMode || "FILL";
      newFills.push(copy);
      replaced = true;
    } else {
      newFills.push(existing[f]);
    }
  }
  if (!replaced) {
    var fillCopy = Object.assign({}, sourceFill);
    fillCopy.scaleMode = sourceFill.scaleMode || "FILL";
    newFills.push(fillCopy);
  }
  layer.fills = newFills;
  return true;
}

// Fill a single named placeholder layer inside `clone` with the image fill
// from a library node. Used by dual-image styles (Split Screen) where the
// canonical "largest target" heuristic of applyLibraryImageToClone is wrong
// because the template has two equally-valid slots.
async function fillNamedPlaceholderFromLibrary(clone, placeholderName, libraryNodeId, label) {
  if (!libraryNodeId) {
    log("    ⚠ " + label + " missing library node id");
    return false;
  }
  var libraryNode = await figma.getNodeByIdAsync(libraryNodeId);
  if (!libraryNode) {
    log("    ✗ " + label + " library node " + libraryNodeId + " not found");
    return false;
  }
  var sourceFill = findSourceImageFill(libraryNode);
  if (!sourceFill) {
    log("    ✗ " + label + " library node has no IMAGE fill");
    return false;
  }
  var target = findLayerByName(clone, placeholderName);
  if (!target) {
    log("    ✗ " + label + " placeholder '" + placeholderName + "' not found in clone");
    return false;
  }
  if (!("fills" in target)) {
    log("    ✗ " + label + " placeholder '" + placeholderName + "' has no fills property");
    return false;
  }
  return applyImageFillToLayer(target, sourceFill);
}

// Dual-image styles (currently Split Screen): fill the left and right
// placeholders independently from two library photos. Returns true if BOTH
// placeholders were filled.
async function applyDualLibraryImagesToClone(clone, leftNodeId, rightNodeId, leftPlaceholder, rightPlaceholder) {
  var leftOk = await fillNamedPlaceholderFromLibrary(clone, leftPlaceholder, leftNodeId, "LEFT");
  var rightOk = await fillNamedPlaceholderFromLibrary(clone, rightPlaceholder, rightNodeId, "RIGHT");
  return leftOk && rightOk;
}

async function applyLibraryImageToClone(clone, libraryNodeId) {
  if (!libraryNodeId) {
    log("    ⚠ row missing figma_node_id");
    return false;
  }
  var libraryNode = await figma.getNodeByIdAsync(libraryNodeId);
  if (!libraryNode) {
    log("    ✗ Library node " + libraryNodeId + " not found in file");
    return false;
  }
  var sourceFill = findSourceImageFill(libraryNode);
  if (!sourceFill) {
    log("    ✗ Library node '" + libraryNode.name + "' (" + libraryNodeId + ") has no IMAGE fill anywhere");
    return false;
  }

  // Identify the canonical image target in the clone. Priority:
  //   1. The largest layer that already has an IMAGE fill (the visible default photo)
  //   2. If no layer has an IMAGE fill, the largest image_placeholder by name
  // Filling only ONE target avoids the duplicate-photo issue when templates
  // have multiple nested image-bearing layers.
  var withImageFill = [];
  var placeholders = [];
  var seenIds = {};
  // Templates often contain decorative gradient rectangles (PrimaryGlimmer_Full
  // etc.) that have IMAGE fills but are 5-10x the template size — they're
  // hidden background textures, not photo targets. Filter anything bigger than
  // 3x the clone's footprint so they can't win the largest-target race.
  var maxW = ("width" in clone) ? clone.width * 3 : Infinity;
  var maxH = ("height" in clone) ? clone.height * 3 : Infinity;
  function isPlaceholderName(nm) {
    // Match Image-Placeholder / Image_Placeholder / Left-/Right- variants,
    // regardless of hyphen vs underscore vs case.
    var s = (nm || "").toLowerCase().replace(/[_\s]+/g, "-");
    return s === "image-placeholder" || s === "left-image-placeholder" || s === "right-image-placeholder";
  }
  function consider(n) {
    if (!n || seenIds[n.id]) return;
    if (n.visible === false) return;
    if (!("fills" in n)) return;
    if (!("width" in n) || !("height" in n)) return;
    seenIds[n.id] = true;
    var nameLower = (n.name || "").toLowerCase();
    if (/glimmer/.test(nameLower)) return;         // decorative gradient — never a photo target
    if (n.width > maxW || n.height > maxH) return; // decorative oversized fill
    var hasImage = Array.isArray(n.fills) && n.fills.some(function (f) { return f.type === "IMAGE"; });
    if (hasImage) withImageFill.push(n);
    if (isPlaceholderName(n.name)) placeholders.push(n);
  }
  walkChildren(clone, consider);
  // Prefer a NAMED image placeholder (the intended photo slot) over the largest
  // layer that merely has an image fill — this stops the photo landing on a
  // decorative background when both exist (e.g. Poll's glimmer vs Image-Placeholder).
  var pool, poolType;
  if (placeholders.length > 0) { pool = placeholders; poolType = "named image-placeholder"; }
  else { pool = withImageFill; poolType = "with-existing-image-fill"; }
  pool.sort(function (a, b) { return (b.width * b.height) - (a.width * a.height); });
  var targets = pool.length > 0 ? [pool[0]] : [];
  if (targets.length > 0) {
    log("    Image target: '" + targets[0].name + "' (" + Math.round(targets[0].width) + "x" + Math.round(targets[0].height) + ", picked from " + pool.length + " " + poolType + " candidate(s))");
  }

  if (targets.length === 0) {
    // Last resort: largest visible RECTANGLE / FRAME inside the clone
    var bigCandidates = [];
    walkChildren(clone, function (n) {
      if ((n.type === "RECTANGLE" || n.type === "FRAME") && n.visible !== false) {
        if ("width" in n && n.width > 200 && n.height > 200) bigCandidates.push(n);
      }
    });
    if (bigCandidates.length > 0) {
      bigCandidates.sort(function (a, b) { return (b.width * b.height) - (a.width * a.height); });
      targets.push(bigCandidates[0]);
      log("    Last-resort: filling largest visible rect '" + bigCandidates[0].name + "' (" + Math.round(bigCandidates[0].width) + "x" + Math.round(bigCandidates[0].height) + ")");
    }
  }

  if (targets.length === 0) {
    var childCount = ("children" in clone) ? clone.children.length : 0;
    log("    ✗ No image target found in clone (clone has " + childCount + " direct children, type=" + clone.type + ")");
    return false;
  }

  var ok = false;
  for (var i = 0; i < targets.length; i++) {
    if (!("fills" in targets[i])) {
      log("    ⚠ target '" + targets[i].name + "' has no fills property (type=" + targets[i].type + ")");
      continue;
    }
    if (applyImageFillToLayer(targets[i], sourceFill)) ok = true;
  }
  return ok;
}

// ── Text ────────────────────────────────────────────────────────────────────

async function setTextLayer(node, text) {
  if (!node || node.type !== "TEXT" || !text) return false;
  try {
    await figma.loadFontAsync(node.fontName);
    node.characters = text;
    return true;
  } catch (e) {
    log("    ⚠ Could not update '" + node.name + "': " + e.message);
    return false;
  }
}

async function setFirstTextByCandidates(clone, candidateNames, text) {
  if (!text) return false;
  for (var i = 0; i < candidateNames.length; i++) {
    var node = findLayerByName(clone, candidateNames[i]);
    if (node && node.type === "TEXT") {
      return await setTextLayer(node, text);
    }
  }
  return false;
}

// Fill the first TEXT descendant inside a named container (component/frame).
// Used when a label like the CTA is wrapped in a "CTA" component rather than a
// bare text layer, so a plain name lookup can't reach it.
async function setTextInContainer(clone, containerName, text) {
  if (!text) return false;
  var container = findLayerByName(clone, containerName);
  if (!container || !container.children) return false;
  var textNode = null;
  walkChildren(container, function (n) {
    if (!textNode && n.type === "TEXT") textNode = n;
  });
  if (textNode) return await setTextLayer(textNode, text);
  return false;
}

// Safety net so NO lorem ipsum ever ships. Styles whose specific layers aren't
// mapped yet (Poll options, etc.) can leave placeholder text behind; replace any
// TEXT node still holding "lorem ipsum" with the row's real copy, cycling fields
// so multiple placeholder layers don't all get the same line. Logs loudly so a
// proper per-field mapping still gets done.
async function clearResidualLoremIpsum(clone, row) {
  var pool = [];
  // NOTE: the Meta Primary Text (short/long) is deliberately EXCLUDED from this
  // fallback pool. This net also runs on the ad creative, and primary text must
  // never be printed on the image (it belongs only in the left panels). Unmapped
  // lorem falls back to on-creative/headline/structured copy instead.
  var fields = [row.Headline_On_Creative, row.Subhead_On_Creative, row.Headline, row.headline,
                row.Description, row.description,
                // structured-style copy, so these styles' unmapped layers still
                // get real text instead of lorem
                row.Us_Headline, row.Them_Headline, row.CTA, row.cta,
                row.Poll_Question, row.Testimonial_Author,
                row.Chat_Label, row.Chat_Message,
                row.Profile_Name, row.Profile_Title, row.Profile_Left, row.Profile_Right];
  for (var i = 0; i < fields.length; i++) {
    if (fields[i] && String(fields[i]).trim()) pool.push(String(fields[i]).trim());
  }
  var listFields = [row.Us_Bullets, row.Them_Bullets, row.Search_Results,
                    row.Pie_Labels, row.Left_Bullets, row.Right_Bullets];
  for (var j = 0; j < listFields.length; j++) {
    var parts = splitPipe(listFields[j]);
    for (var p = 0; p < parts.length; p++) if (parts[p]) pool.push(parts[p]);
  }
  // NEVER leave lorem on a board. If the row carries no usable copy at all, fall
  // back to a brand-safe line rather than shipping placeholder text.
  if (!pool.length) pool.push("Find top talent on Upwork");
  var targets = [];
  walkChildren(clone, function (n) {
    if (n.type === "TEXT" && /lorem\s+ipsum/i.test(n.characters || "")) targets.push(n);
  });
  var filled = 0;
  for (var t = 0; t < targets.length; t++) {
    if (await setTextLayer(targets[t], pool[t % pool.length])) filled++;
  }
  if (filled) log("  ⚠ replaced " + filled + " residual lorem-ipsum layer(s) with real copy (needs proper per-field mapping)");
  return filled;
}

// Brandon's Sticky Note template has a 4-quadrant layout: Left_Headline_Text,
// Left_Bullet_Text1/2, right_headline_text, Right_Bullet_Text1/2. The pipeline's
// copy generation today produces only one headline + one body per concept —
// which fills the left side cleanly but leaves the right side as Lorem Ipsum.
// This helper splits the body into bullet-sized fragments and mirrors the
// content across both columns so the assembled note doesn't show placeholder
// text. Once Adrie tightens copy gen for sticky-note specifically, we can
// drop this fabrication and use real per-quadrant copy from the manifest.
function splitIntoBullets(body) {
  if (!body) return ["", ""];
  // Split on sentence boundaries; fall back to commas; fall back to halving.
  var parts = body.split(/(?<=[.!?])\s+/).map(function (p) { return p.trim(); }).filter(Boolean);
  if (parts.length >= 2) return [parts[0], parts.slice(1).join(" ")];
  parts = body.split(/,\s*/).map(function (p) { return p.trim(); }).filter(Boolean);
  if (parts.length >= 2) return [parts[0], parts.slice(1).join(", ")];
  // Halve by word count.
  var words = body.split(/\s+/);
  var mid = Math.ceil(words.length / 2);
  return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
}

async function fillStickyNoteCopy(clone, headline, bodyShort, bodyLong) {
  var bullets = splitIntoBullets(bodyShort || "");
  var leftBullet1 = bullets[0] || "";
  var leftBullet2 = bullets[1] || "";

  // Right column gets fragments from the long body (or the short, mirrored).
  var rightBullets = splitIntoBullets(bodyLong || bodyShort || "");
  var rightBullet1 = rightBullets[0] || "";
  var rightBullet2 = rightBullets[1] || "";

  await setFirstTextByCandidates(clone, ["Left_Headline_Text"], headline);
  await setFirstTextByCandidates(clone, ["Left_Bullet_Text1", "Left_Bullet_Text_1"], leftBullet1);
  await setFirstTextByCandidates(clone, ["Left_Bullet_Text2", "Left_Bullet_Text_2"], leftBullet2);
  await setFirstTextByCandidates(clone, ["right_headline_text", "Right_Headline_Text"], headline);
  await setFirstTextByCandidates(clone, ["Right_Bullet_Text1", "Right_Bullet_Text_1"], rightBullet1);
  await setFirstTextByCandidates(clone, ["Right_Bullet_Text2", "Right_Bullet_Text_2"], rightBullet2);
}

// Pie Chart: draw the data slice + fill the center callout. `pct` is 0-100.
// Figma ELLIPSE nodes expose arcData {startingAngle, endingAngle, innerRadius};
// setting endingAngle to pct/100 of a full turn renders the filled wedge. The
// "value" arc is the top colored ("Dark Gradient"/"value"/"slice") ellipse; the
// background ellipse(s) stay full circles. Center text = "<pct>%".
// (Answers Elise's Figma comment #8: "reflect a % from a data set".)
async function fillPieChartValue(clone, pct) {
  var p = Number(pct);
  if (!isFinite(p)) return false;
  p = Math.max(0, Math.min(100, p));
  var TWO_PI = Math.PI * 2;
  var START = -Math.PI / 2; // 12 o'clock

  // Center callout = the percentage.
  await setFirstTextByCandidates(
    clone,
    ["Center_Callout_Text", "chart_center_text", "TextOnly_Subhead_Text", "headline_text"],
    String(Math.round(p)) + "%"
  );

  // Collect every ellipse in the clone.
  var ellipses = [];
  (function collect(n) {
    if (n.type === "ELLIPSE") ellipses.push(n);
    var ch = n.children;
    if (ch) for (var i = 0; i < ch.length; i++) collect(ch[i]);
  })(clone);
  if (!ellipses.length) return false;

  // Prefer an explicitly-named value arc; else the first colored ("dark") arc;
  // else the first ellipse. (A future template rename to "Chart_Value_Arc"
  // makes this unambiguous.)
  var valueArc = null;
  for (var i = 0; i < ellipses.length; i++) {
    var nm = (ellipses[i].name || "").toLowerCase();
    if (nm.indexOf("value") >= 0 || nm.indexOf("slice") >= 0 || nm.indexOf("chart_value") >= 0) { valueArc = ellipses[i]; break; }
  }
  if (!valueArc) {
    for (var j = 0; j < ellipses.length; j++) {
      if ((ellipses[j].name || "").toLowerCase().indexOf("dark") >= 0) { valueArc = ellipses[j]; break; }
    }
  }
  if (!valueArc) valueArc = ellipses[0];

  try {
    var inner = (valueArc.arcData && typeof valueArc.arcData.innerRadius === "number")
      ? valueArc.arcData.innerRadius : 0;
    valueArc.arcData = { startingAngle: START, endingAngle: START + (p / 100) * TWO_PI, innerRadius: inner };
    return true;
  } catch (e) {
    log("  ⚠ pie chart arc set failed: " + e);
    return false;
  }
}

// Poll: a question + two horizontal bars. Each bar (Stat-Percent-A / -B) shows a
// percentage as text AND a fill rectangle whose width encodes that percentage.
// The template ships with 60%/90% placeholders; we set both the % text and the
// fill width from the generated poll values, and fill the standalone question.
async function fillPollCopy(clone, row) {
  var statBlock = findLayerByName(clone, "Stat Block");
  if (!statBlock || !statBlock.children) { log("  ⚠ poll: no 'Stat Block' frame"); return false; }

  var question = row.Poll_Question || row.poll_question ||
                 row.Primary_Text_Short || row.body_short || "";
  var pctA = parseInt(row.Poll_Pct_A || row.poll_pct_a, 10);
  var pctB = parseInt(row.Poll_Pct_B || row.poll_pct_b, 10);
  // Answer labels so each bar MEANS something (e.g. "Yes  81%"). Optional.
  var optA = row.Poll_Option_A || row.poll_option_a || "";
  var optB = row.Poll_Option_B || row.poll_option_b || "";

  // Question = the "Stat Block Text" that is a DIRECT child of Stat Block
  // (the % ones live inside the Stat-Percent-* frames, so they're excluded).
  if (question) {
    for (var i = 0; i < statBlock.children.length; i++) {
      var c = statBlock.children[i];
      if (c.type === "TEXT" && c.name === "Stat Block Text") {
        await setTextLayer(c, question);
        break;
      }
    }
  }

  async function fillBar(barName, pct, label) {
    if (!isFinite(pct)) return;
    pct = Math.max(0, Math.min(100, pct));
    var bar = findLayerByName(clone, barName);
    if (!bar) return;
    var txt = null, fill = null;
    (function walk(n) {
      if (!txt && n.type === "TEXT" && n.name === "Stat Block Text") txt = n;
      if (!fill && n.type === "RECTANGLE" && /-fill$/i.test(n.name || "")) fill = n;
      var ch = n.children; if (ch) for (var i = 0; i < ch.length; i++) walk(ch[i]);
    })(bar);
    // Show "Yes  81%" when an answer label is supplied, else just "81%".
    if (txt) await setTextLayer(txt, (label ? String(label).trim() + "   " : "") + Math.round(pct) + "%");
    if (fill && "resize" in fill) {
      // Size the fill to pct% of the bar's RENDERED width. bar.width can report
      // LOCAL (unscaled) units (observed 100 while it renders 1000), so use the
      // absolute bounds for the track and convert the target back into the
      // fill's own local units via its local/absolute ratio.
      var frameAbs = (bar.absoluteBoundingBox && bar.absoluteBoundingBox.width)
        ? bar.absoluteBoundingBox.width : (bar.width || 1000);
      var ratio = (fill.absoluteBoundingBox && fill.absoluteBoundingBox.width)
        ? (fill.width / fill.absoluteBoundingBox.width) : 1;
      var target = Math.max(1, Math.round((pct / 100) * frameAbs * ratio));
      try { fill.resize(target, fill.height); }
      catch (e) { log("  ⚠ poll bar resize (" + barName + "): " + e); }
    }
  }
  await fillBar("Stat-Percent-A", pctA, optA);
  await fillBar("Stat-Percent-B", pctB, optB);
  log("  ✓ poll filled (question + bars " + (optA || "A") + "=" + pctA + "% " + (optB || "B") + "=" + pctB + "%)");
  return true;
}

function splitPipe(s) {
  return String(s || "").split("|").map(function (x) { return x.trim(); }).filter(Boolean);
}

// Us vs Them: a side-by-side comparison. Fill the two side headlines and the
// three bullets per side (us → Bullet1-3, them → Bullet4-6).
async function fillUsVsThemCopy(clone, row) {
  var usHead = row.Us_Headline || row.us_headline || row.Headline || row.headline || "";
  var themHead = row.Them_Headline || row.them_headline || "";
  var usB = splitPipe(row.Us_Bullets || row.us_bullets);
  var themB = splitPipe(row.Them_Bullets || row.them_bullets);

  // The two columns use inconsistent layer names across sizes (Copy_Headline /
  // Copy_Bullet duplicated on some, legacy UsVsThem_* on the 1440x1440). Instead
  // of matching names, identify each side by the ✅ (us) / ❌ (them) marker that
  // sits in the same container — robust to naming and size. Fall back to document
  // order (them column first) only if a layer has no nearby marker.
  function markerSide(node) {
    var p = node.parent;
    if (p && "children" in p) {
      var hasUs = false, hasThem = false;
      for (var i = 0; i < p.children.length; i++) {
        var c = p.children[i], t = (c.name || "") + (c.characters || "");
        if (t.indexOf("✅") >= 0) hasUs = true;      // ✅
        if (t.indexOf("❌") >= 0) hasThem = true;    // ❌
      }
      if (hasThem && !hasUs) return "them";
      if (hasUs && !hasThem) return "us";
    }
    return null;
  }
  var heads = [], bullets = [];
  walkChildren(clone, function (n) {
    if (n.type !== "TEXT") return;
    var nm = n.name || "";
    if (/headline/i.test(nm) && !/subhead/i.test(nm)) heads.push(n);
    else if (/bullet/i.test(nm)) bullets.push(n);
  });

  // Headlines rarely have a marker beside them → default to order (them, us).
  var usHeads = heads.filter(function (n) { return markerSide(n) === "us"; });
  var themHeads = heads.filter(function (n) { return markerSide(n) === "them"; });
  if (!usHeads.length && !themHeads.length && heads.length >= 2) { themHeads = [heads[0]]; usHeads = [heads[1]]; }
  if (themHead && themHeads[0]) await setTextLayer(themHeads[0], themHead);
  if (usHead && usHeads[0]) await setTextLayer(usHeads[0], usHead);

  // Bullets: group by marker side, fill in order within each side.
  var usBul = bullets.filter(function (n) { return markerSide(n) === "us"; });
  var themBul = bullets.filter(function (n) { return markerSide(n) === "them"; });
  if (!usBul.length && !themBul.length && bullets.length) {           // no markers → split by order
    var half = Math.floor(bullets.length / 2);
    themBul = bullets.slice(0, half); usBul = bullets.slice(half);
  }
  for (var a = 0; a < themBul.length && a < themB.length; a++) if (themB[a]) await setTextLayer(themBul[a], themB[a]);
  for (var b = 0; b < usBul.length && b < usB.length; b++) if (usB[b]) await setTextLayer(usBul[b], usB[b]);
  log("  ✓ us-vs-them filled (us bullets=" + usBul.length + ", them bullets=" + themBul.length + " by marker)");
  return true;
}

// ── Styled-per-row mode ─────────────────────────────────────────────────────

function normAlnum(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

// Preferred convention matcher (Elise's source-of-truth naming):
//   Template_{Adtype}_{WxH}   e.g. Template_Us-Vs-Them_1440x1800
// Match by the FULL adtype token in the template name + the size taken from the
// NAME (some templates are 1440x1805 in their bounding box but named _1440x1800,
// so name-size beats box-size). Width must match exactly; height within a small
// tolerance. This replaces the stale hardcoded STYLE_TEMPLATE_PREFIXES for the
// common case and immunizes against Elise renaming template families.
// Order-form style names whose Figma template/adtype is named differently.
var STYLE_ADTYPE_ALIAS = {
  "socialmediaprofile": "socialprofile",        // Template_Social-Profile
  "tweetpostmockup": "mockup",                  // Template_Mockup
  "searchbarwithtalentbadge": "searchresults",  // Adtype_Search-Results
  "graphicwithtext": "illustration",            // order-form "Graphic with Text" = Figma Illustration family
  "lifestylephoto": "lifestylephotofullbleed",  // order-form "Lifestyle Photo" = Lifestyle-Photo-Full-Bleed
};

// Variant selection among templates that match style+size. `hint` carries:
//   wantCTA  (bool)  — true (default) picks a WITH-CTA layout, skipping "Alt"
//                      (Elise's No-CTA variant); false prefers the Alt layout.
//   prefer   ("dark"|"light") — tone to prefer; alternated per concept for variety.
// Falls back gracefully: if the preferred combination isn't present, it relaxes
// (any tone, then any variant) rather than returning nothing.
function selectVariant(candidates, hint) {
  if (candidates.length <= 1) return candidates[0] || null;
  hint = hint || {};
  var wantCTA = hint.wantCTA !== false;   // default true
  function isAlt(c)  { return /(_|\b)alt(_|\b)/i.test(c.name); }
  function tone(c)   { return /(_|\b)dark(_|\b)/i.test(c.name) ? "dark"
                            : /(_|\b)light(_|\b)/i.test(c.name) ? "light" : ""; }
  var pool = candidates.slice();
  // CTA preference: with-CTA => drop Alt; no-CTA => keep only Alt if any exist.
  var nonAlt = pool.filter(function (c) { return !isAlt(c); });
  var alt    = pool.filter(isAlt);
  if (wantCTA && nonAlt.length) pool = nonAlt;
  else if (!wantCTA && alt.length) pool = alt;
  // Layout-family preference: styles like Testimonial resolve to multiple
  // families (Photo / Text-Only / Text-and-Photo). When a photo is available,
  // prefer a template whose name includes "Photo"; when not, prefer "Text-Only".
  if (hint.hasPhoto === true) {
    var photoFam = pool.filter(function (c) { return /photo/i.test(c.name); });
    if (photoFam.length) pool = photoFam;
  } else if (hint.hasPhoto === false) {
    var textFam = pool.filter(function (c) { return /text-?only/i.test(c.name); });
    if (textFam.length) pool = textFam;
  }
  // Tone preference (only if this family actually has toned variants).
  if (hint.prefer) {
    var toned = pool.filter(function (c) { return tone(c) === hint.prefer; });
    if (toned.length) pool = toned;
    else {
      var anyTone = pool.filter(function (c) { return tone(c) !== ""; });
      if (anyTone.length) pool = anyTone;   // family is toned but not our pref — take any tone
    }
  }
  return pool[0];
}

function findTemplateByConvention(searchRoot, visualStyle, w, h, hint) {
  var raw = normAlnum(visualStyle);
  var an = STYLE_ADTYPE_ALIAS[raw] || raw;
  if (!an) return null;
  // Elise names some template frames Template_* and others Adtype_*_{WxH} — search
  // both so Pie-Chart / Search-Results / Sticky-Note (Adtype_-named) are found too.
  var all = findAllByPrefix(searchRoot, "Template").concat(findAllByPrefix(searchRoot, "Adtype"));
  // Collect EVERY template that matches this adtype + exact width + near-exact
  // height, so selectVariant can choose the right Dark/Light/Alt among them.
  var matches = [];
  for (var i = 0; i < all.length; i++) {
    var c = all[i];
    if (normAlnum(c.name).indexOf(an) === -1) continue;  // adtype must be in the name
    var cw, ch;
    var m = String(c.name).match(/(\d{3,5})\s*[x×]\s*(\d{3,5})/i);
    if (m) { cw = +m[1]; ch = +m[2]; }
    else { var wh = nodeWH(c); if (!wh) continue; cw = wh[0]; ch = wh[1]; }
    if (cw !== w) continue;
    if (Math.abs(ch - h) <= 12) matches.push(c);
  }
  // Fallback: a template frame's OWN name can be wrong — e.g. the Bespoke
  // starter's size frames are mislabeled 'Template_Split-Screen_*' in Figma.
  // But Elise's 'Adtype_{Style}/' SECTION is the reliable owner. If nothing
  // matched by frame name, trust the section: find the Adtype container for
  // this style and take its size-matched child frames (name-agnostic).
  if (!matches.length) {
    var wantSect = "adtype" + an;
    var sects = findAllByPrefix(searchRoot, "Adtype");
    var container = null;
    for (var si = 0; si < sects.length; si++) {
      if (normAlnum(sects[si].name).indexOf(wantSect) === 0) { container = sects[si]; break; }
    }
    if (container) {
      var kids = findAllByPrefix(container, "Template");
      for (var ki = 0; ki < kids.length; ki++) {
        var kc = kids[ki], kw, kh;
        var km = String(kc.name).match(/(\d{3,5})\s*[x×]\s*(\d{3,5})/i);
        if (km) { kw = +km[1]; kh = +km[2]; }
        else { var kwh = nodeWH(kc); if (!kwh) continue; kw = kwh[0]; kh = kwh[1]; }
        if (kw === w && Math.abs(kh - h) <= 12) matches.push(kc);
      }
      if (matches.length) {
        log("    Matched via section '" + container.name + "' (child frame '" +
            matches[0].name + "' is mislabeled in Figma — should be Template_Adtype_" +
            visualStyle.replace(/\s+/g, "-") + "_" + w + "x" + h + ")");
      }
    }
  }
  if (!matches.length) return null;
  var chosen = selectVariant(matches, hint) || matches[0];
  var node = chosen, viaSet = null;
  if (chosen.type === "COMPONENT_SET") { node = pickPreferredVariant(chosen, []) || chosen; viaSet = chosen; }
  return { node: node, viaSet: viaSet };
}

function findStyledTemplate(searchRoot, visualStyle, w, h, hint) {
  // 1) Elise's naming convention first (source of truth).
  var conv = findTemplateByConvention(searchRoot, visualStyle, w, h, hint);
  if (conv) {
    log("    Found template by convention: '" + conv.node.name + "'");
    return conv;
  }

  // 2) Fallback: legacy hardcoded prefix maps (kept so older/renamed families
  //    still resolve; logs loudly when even this misses).
  var key = normalizeStyle(visualStyle);
  var prefixes = STYLE_TEMPLATE_PREFIXES[key];
  if (!prefixes) {
    log("    ⚠ No template by convention and unknown visual_style: '" + visualStyle + "' (normalized '" + key + "')");
    return null;
  }

  var variantPrefs = STYLE_VARIANT_PREFERENCES[key] || [];

  // First pass: restrict search to the style's preferred Adtype container.
  // This prevents name collisions (e.g., Sticky Note's inner template is named
  // "Template_TestimonialA" but lives inside "Adtype: Sticky Note").
  var preferredContainerNames = STYLE_ADTYPE_CONTAINERS[key] || [];
  for (var ci = 0; ci < preferredContainerNames.length; ci++) {
    var container = findLayerByName(searchRoot, preferredContainerNames[ci]);
    if (!container) continue;
    var hit = matchInside(container, prefixes, w, h, variantPrefs);
    if (hit) {
      log("    Found styled template inside '" + preferredContainerNames[ci] + "'" + (hit.viaSet ? " variant '" + hit.node.name + "'" : ""));
      return hit;
    }
  }

  // Second pass: widen to the entire searchRoot.
  return matchInside(searchRoot, prefixes, w, h, variantPrefs);
}

function pickPreferredVariant(componentSet, variantPrefs) {
  // Pick a variant from a COMPONENT_SET, preferring ones whose name contains
  // any of the variantPrefs strings (in order). Falls back to children[0].
  if (!componentSet || !("children" in componentSet) || componentSet.children.length === 0) return null;
  if (variantPrefs && variantPrefs.length > 0) {
    for (var p = 0; p < variantPrefs.length; p++) {
      var pref = variantPrefs[p].toLowerCase();
      for (var i = 0; i < componentSet.children.length; i++) {
        var c = componentSet.children[i];
        if (c.name && c.name.toLowerCase().indexOf(pref) !== -1) return c;
      }
    }
  }
  return componentSet.children[0];
}

function matchInside(root, prefixes, w, h, variantPrefs) {
  for (var p = 0; p < prefixes.length; p++) {
    var candidates = findAllByPrefix(root, prefixes[p]);
    var matches = [];
    for (var i = 0; i < candidates.length; i++) {
      var c = candidates[i];
      if (c.type === "COMPONENT_SET") {
        var v = pickPreferredVariant(c, variantPrefs);
        if (v) {
          var vwh = nodeWH(v);
          if (vwh && vwh[0] === w && vwh[1] === h) {
            matches.push({ node: v, viaSet: c });
          }
        }
      } else {
        var wh = nodeWH(c);
        if (wh && wh[0] === w && wh[1] === h) {
          matches.push({ node: c });
        }
      }
    }
    if (matches.length > 0) return matches[0];
  }
  return null;
}

async function assembleStyledPerRow(searchRoot, manifest, destination, baseX, baseY) {
  var assembled = 0;
  var failed = 0;
  var assembledIds = [];
  var rowGap = 200;
  var maxHeight = 0;
  var currentX = baseX;
  var currentY = baseY;
  var rowItems = 0;

  for (var idx = 0; idx < manifest.length; idx++) {
    var row = manifest[idx];
    var assetId = row.asset_id || ("ad_" + (idx + 1));
    var visualStyle = row.Visual_Style || row.visual_style || "";
    var dims = parseResolutionToWH(row.Resolutions || row.resolution || "");
    if (!dims) {
      log("[" + assetId + "] ✗ no parseable resolution — skipping");
      failed++;
      continue;
    }
    log("\n[" + assetId + "] " + visualStyle + " · " + dims[0] + "x" + dims[1]);

    // Variant-specific lookup: when the row carries a template_frame_id (e.g.
    // Text Only's WhiteBorder vs NoBorder variants), fetch that exact Figma
    // node instead of falling through to name-based search — the variants
    // share the same template name so name-search would always pick the first.
    var found = null;
    var templateFrameId = row.template_frame_id || row.Template_Frame_Id || "";
    if (templateFrameId) {
      var directNode = await figma.getNodeByIdAsync(templateFrameId);
      if (directNode && "clone" in directNode) {
        found = { node: directNode };
        log("  Using exact variant frame: " + templateFrameId + " (" + (row.variant_name || "no variant_name") + ")");
      } else {
        log("  ⚠ template_frame_id " + templateFrameId + " not found or not cloneable — falling back to name search");
      }
    }
    if (!found) {
      found = findStyledTemplate(searchRoot, visualStyle, dims[0], dims[1]);
    }
    if (!found) {
      log("  ✗ No styled template found for " + visualStyle + " at " + dims[0] + "x" + dims[1]);
      failed++;
      continue;
    }
    log("  Using template: " + (found.viaSet ? found.viaSet.name + " > " : "") + found.node.name);

    var clone = found.node.clone();
    clone.name = "ASSEMBLED_" + assetId;

    if (destination && "appendChild" in destination) {
      destination.appendChild(clone);
    } else {
      figma.currentPage.appendChild(clone);
    }
    clone.x = currentX;
    clone.y = currentY;

    // Style key + image
    var key = normalizeStyle(visualStyle);
    var nodeId = row.figma_node_id || row.figma_library_node_id || row.figma_asset_id || "";
    if (STYLES_THAT_SKIP_IMAGE[key]) {
      log("  (style '" + visualStyle + "' skips image override — keeping template imagery)");
    } else if (STYLES_WITH_DUAL_IMAGE[key]) {
      // Dual-image style (currently Split Screen). Fill left and right
      // placeholders independently from the row's two library node IDs.
      var leftId = row.figma_node_id_left || row.Figma_Node_Id_Left || "";
      var rightId = row.figma_node_id_right || row.Figma_Node_Id_Right || "";
      var placeholders = STYLES_WITH_DUAL_IMAGE[key];
      var dualOk = await applyDualLibraryImagesToClone(clone, leftId, rightId, placeholders[0], placeholders[1]);
      if (dualOk) {
        log("  ✓ dual images applied (LEFT=" + (row.figma_asset_name_left || leftId) + ", RIGHT=" + (row.figma_asset_name_right || rightId) + ")");
      } else {
        // Fallback: try the legacy single-image flow against the largest target
        // so at least one placeholder gets a photo if dual data is missing.
        log("  ⚠ dual image fill failed — falling back to single-target fill");
        var fbOk = await applyLibraryImageToClone(clone, nodeId || leftId || rightId);
        if (fbOk) log("  ✓ single fallback image applied");
      }
    } else {
      var imgOk = await applyLibraryImageToClone(clone, nodeId);
      if (imgOk) log("  ✓ image applied (" + (row.figma_asset_name || nodeId) + ")");
      else log("  ⚠ no image applied");
    }

    // Text — style-specific candidates.
    // Reminder's two body-area text layers BOTH share the name
    // "Notification_Headline_Text" (one is the "Reminder" label, the other
    // is the message body). findLayerByName picks the first in document
    // order — that's the label — so the generic flow would overwrite the
    // label with the headline copy. Handle Reminder explicitly by index.
    var ctaText = row.CTA || row.cta || "";

    if (key === "reminder" || key === "tweet / post mockup") {
      // Mockup reuses the Reminder base; same Notification_Headline_Text layers
      // (index 0 = label, index 1 = body). Mockup has 6 of them — only the
      // primary body fills here; per-row copy needs distinct Figma layer names.
      // Layer order inside Reminder templates (from inspect_templates.py,
      // verified across both variants 5355:454 / 5355:480):
      //   [0] Notification_Headline_Text — "Reminder" label (static; do not write)
      //   [1] Notification_Headline_Text — body copy (write the message here)
      //   ... Notification_SubjectName_Text — CTA button text
      var bodyMatches = findAllLayersByName(clone, "Notification_Headline_Text");
      var bodyText = row.Primary_Text_Long || row.body_long || row.Primary_Text_Short || row.body_short || row.Headline_On_Creative || row.Headline || row.headline || "";
      if (bodyText && bodyMatches.length >= 2) {
        var bodyOk = await setTextLayer(bodyMatches[1], bodyText);
        if (bodyOk) log("  ✓ reminder body filled (index 1; label at index 0 preserved)");
      } else if (bodyText && bodyMatches.length === 1) {
        // Defensive: if Brandon ever collapses to a single text layer, fill it.
        var soloOk = await setTextLayer(bodyMatches[0], bodyText);
        if (soloOk) log("  ✓ reminder body filled (single layer)");
      } else if (bodyText) {
        log("  ⚠ reminder body text present but no Notification_Headline_Text layers found");
      }
      if (ctaText) {
        var ctaOk = await setFirstTextByCandidates(clone, ["Notification_SubjectName_Text"], ctaText);
        if (ctaOk) log("  ✓ reminder CTA filled (Notification_SubjectName_Text)");
      }
    } else {
      // Style-specific names first (so styles that already work don't regress),
      // then the universal "Copy_Headline" — Brandon's current templates renamed
      // the headline layer to that, and the old per-style names are stale.
      var headlineCandidates = (STYLE_HEADLINE_LAYERS[key] || ["headline_text"]).concat(["Copy_Headline"]);
      var headlineText = row.Headline_On_Creative || row.Headline_Long || row.Headline || row.headline || "";
      var hlOk = await setFirstTextByCandidates(clone, headlineCandidates, headlineText);
      if (hlOk) log("  ✓ headline filled");
      else if (headlineText) log("  ⚠ headline NOT filled — no layer matched [" + headlineCandidates.join(", ") + "]");

      // CTA — skipped for styles where the CTA layer is the headline target
      if (ctaText && !STYLES_THAT_SKIP_CTA[key]) {
        var ctaOk = await setFirstTextByCandidates(clone, ["cta_text", "CTA_Text", "Copy_CTA", "cta"], ctaText);
        // Current templates wrap the CTA label in a "CTA" component/frame rather
        // than a bare text layer — fill its inner text node as a fallback.
        if (!ctaOk) ctaOk = await setTextInContainer(clone, "CTA", ctaText);
        if (ctaOk) log("  ✓ cta filled");
        else log("  ⚠ cta NOT filled");
      }

      // Subhead / stat line — style-specific layers first, then the universal
      // "Copy_Subhead" (current template convention). Short copy fits best.
      var subLayers = (STYLE_SUBHEAD_LAYERS[key] || []).concat(["Copy_Subhead"]);
      var subText = row.Description || row.description || row.Primary_Text_Short || row.body_short || "";
      if (subText) {
        var subOk = await setFirstTextByCandidates(clone, subLayers, subText);
        if (subOk) log("  ✓ subhead/stat filled");
      }

      // Body copy — templates that use "Copy_Body" (Sticky-Note, Mockup, Reminder).
      var bodyText = row.Primary_Text_Short || row.body_short || row.Primary_Text_Long || row.body_long || "";
      if (bodyText && await setFirstTextByCandidates(clone, ["Copy_Body"], bodyText)) log("  ✓ body filled");

      // Testimonial quote — the long-form copy goes in Copy_Testimonial.
      var quote = row.Primary_Text_Long || row.body_long || row.Primary_Text_Short || row.body_short || "";
      if (quote && await setFirstTextByCandidates(clone, ["Copy_Testimonial"], quote)) log("  ✓ testimonial quote filled");

      // ── Per-style structured copy (fields generated by the tool) ──────────────
      // Testimonial author
      if (row.Testimonial_Author && await setFirstTextByCandidates(clone, ["Copy_Author"], row.Testimonial_Author)) log("  ✓ testimonial author filled");
      // Search Results — three role rows
      var srRows = splitPipe(row.Search_Results);
      for (var si = 0; si < srRows.length && si < 3; si++)
        await setFirstTextByCandidates(clone, ["Copy_Title" + (si + 1)], srRows[si]);
      if (srRows.length) log("  ✓ search result rows filled (" + Math.min(srRows.length, 3) + ")");
      // Social Media Profile
      if (row.Profile_Name) await setFirstTextByCandidates(clone, ["Copy_Name"], row.Profile_Name);
      if (row.Profile_Title) await setFirstTextByCandidates(clone, ["Copy_Title"], row.Profile_Title);
      if (row.Profile_Left) await setFirstTextByCandidates(clone, ["Copy_Left-Column"], row.Profile_Left);
      if (row.Profile_Right) await setFirstTextByCandidates(clone, ["Copy_Right-Column"], row.Profile_Right);
      if (row.Profile_Name) log("  ✓ social profile filled");
      // Chat Bubble
      if (row.Chat_Label) await setFirstTextByCandidates(clone, ["Copy_Chat-Bubble-1"], row.Chat_Label);
      if (row.Chat_Message) await setFirstTextByCandidates(clone, ["Copy_Chat-Bubble-2"], row.Chat_Message);
      // Text with Button
      if (row.Button_Text) await setFirstTextByCandidates(clone, ["Copy_Button"], row.Button_Text);
      // Pie Chart — four quadrant labels + center callout
      var pieLabels = splitPipe(row.Pie_Labels);
      var quad = ["Copy_TopLeft", "Copy_TopRight", "Copy_BottomLeft", "Copy_BottomRight"];
      for (var qi = 0; qi < pieLabels.length && qi < 4; qi++)
        await setFirstTextByCandidates(clone, [quad[qi]], pieLabels[qi]);
      if (row.Pie_Center) await setFirstTextByCandidates(clone, ["TextOnly_Subhead_Text", "Copy_Center"], row.Pie_Center);
      if (pieLabels.length) log("  ✓ pie quadrants filled (" + Math.min(pieLabels.length, 4) + ")");

      // Sticky Note: also try to fill the right-side headline if we have a body
      if (key === "sticky note") {
        // Prefer the structured two-column copy (Left/Right headline + 2 bullets each).
        var lh = row.Left_Headline || row.left_headline || headlineText || "";
        var rh = row.Right_Headline || row.right_headline || "";
        var lb = splitPipe(row.Left_Bullets || row.left_bullets);
        var rb = splitPipe(row.Right_Bullets || row.right_bullets);
        if (lh) await setFirstTextByCandidates(clone, ["Left_Headline_Text"], lh);
        if (rh) await setFirstTextByCandidates(clone, ["right_headline_text", "Right_Headline_Text"], rh);
        if (lb[0]) await setFirstTextByCandidates(clone, ["Left_Bullet_Text1", "Left_Bullet_Text_1"], lb[0]);
        if (lb[1]) await setFirstTextByCandidates(clone, ["Left_Bullet_Text2", "Left_Bullet_Text_2"], lb[1]);
        if (rb[0]) await setFirstTextByCandidates(clone, ["Right_Bullet_Text1", "Right_Bullet_Text_1"], rb[0]);
        if (rb[1]) await setFirstTextByCandidates(clone, ["Right_Bullet_Text2", "Right_Bullet_Text_2"], rb[1]);
        if (lh || rh || lb.length || rb.length) {
          log("  ✓ sticky-note columns filled (structured)");
        } else {
          // Fallback: mirror the short body into the right-side layer (legacy behavior).
          var rightText = row.Primary_Text_Short || row.body_short || "";
          if (rightText) await setFirstTextByCandidates(clone, STYLE_BULLET_LAYERS[key] || [], rightText);
        }
      }
    }

    // Pie Chart: size the slice from the data % and fill the center callout.
    if (key === "pie chart") {
      var chartPct = row.Chart_Pct || row.chart_pct || row.Chart_Pct_Value || "";
      if (chartPct !== "" && chartPct !== null && chartPct !== undefined) {
        var chartOk = await fillPieChartValue(clone, chartPct);
        log(chartOk
          ? "  ✓ pie chart slice → " + chartPct + "% (center callout filled)"
          : "  ⚠ pie chart: no arc ellipse found to size");
      } else {
        log("  (pie chart: no Chart_Pct in row — slice left as-is)");
      }
    }

    // Us vs Them: fill both side headlines + the three bullets per side.
    if (key === "us vs them") {
      await fillUsVsThemCopy(clone, row);
      log("  ✓ us-vs-them copy filled (us/them headlines + bullets)");
    }

    // Poll: question + two bars (% text + fill width) from generated values.
    if (key === "poll") {
      await fillPollCopy(clone, row);
    }

    // Safety net: no lorem ipsum may ship. Replace any placeholder text left in
    // unmapped layers with the row's real copy.
    await clearResidualLoremIpsum(clone, row);

    // Position next clone in a flexible grid (8 per row)
    rowItems++;
    maxHeight = Math.max(maxHeight, clone.height);
    if (rowItems % 4 === 0) {
      currentX = baseX;
      currentY += maxHeight + rowGap;
      maxHeight = 0;
    } else {
      currentX += clone.width + 200;
    }

    assembled++;
    assembledIds.push(clone.id);
    await new Promise(function (r) { setTimeout(r, 50); });
  }

  return { assembled: assembled, failed: failed, ids: assembledIds };
}

// ── Concept-board mode (existing v3 behavior, retained) ─────────────────────

function getCopyFrameTextValueLayers(notesFrame) {
  if (!notesFrame) return { headline: null, primary: null, cta: null };
  var copyFrame = findDirectChildByName(notesFrame, "Copy Frame");
  if (!copyFrame || !("children" in copyFrame)) return { headline: null, primary: null, cta: null };
  function lastTextChild(frame) {
    if (!frame || !("children" in frame)) return null;
    var txts = [];
    for (var i = 0; i < frame.children.length; i++) {
      if (frame.children[i].type === "TEXT") txts.push(frame.children[i]);
    }
    return txts.length > 0 ? txts[txts.length - 1] : null;
  }
  var groups = [];
  for (var i = 0; i < copyFrame.children.length; i++) {
    var c = copyFrame.children[i];
    if (c.type === "FRAME") groups.push(c);
  }
  return {
    headline: groups.length >= 1 ? lastTextChild(groups[0]) : null,
    primary:  groups.length >= 2 ? lastTextChild(groups[1]) : null,
    cta:      groups.length >= 3 ? lastTextChild(groups[2]) : null,
  };
}

function findImageFrameByDimensions(layoutFrame, w, h) {
  if (!layoutFrame || !("children" in layoutFrame)) return null;
  for (var i = 0; i < layoutFrame.children.length; i++) {
    var c = layoutFrame.children[i];
    if (c.type !== "FRAME" || !("width" in c)) continue;
    if (Math.round(c.width) === w && Math.round(c.height) === h) return c;
  }
  return null;
}

async function fillConceptBoard(clone, conceptRows, conceptIndex, styledSearchRoot) {
  // Use the FIRST row of the concept group as the canonical source for both
  // the photo and the copy. Then fill ALL image frame slots in the board
  // using that same photo + copy, looking up the right-sized styled template
  // for each slot. This way every board shows one consistent concept across
  // every size the board provides — independent of how the manifest is sliced.
  var leadRow = conceptRows[0];
  var visualStyle = leadRow.Visual_Style || leadRow.visual_style || "";
  var leadNodeId = leadRow.figma_node_id || leadRow.figma_library_node_id || leadRow.figma_asset_id || "";
  var leadHeadline = leadRow.Headline_On_Creative || leadRow.Headline_Long || leadRow.Headline || leadRow.headline || "";
  var leadPrimary = leadRow.Primary_Text_Short || leadRow.body_short || leadRow.body || leadRow.Primary_Text_Long || "";
  var leadCta = leadRow.CTA || leadRow.cta || "";

  // Variant hint: always with-CTA unless the order explicitly says no CTA;
  // alternate Dark/Light across concepts for visual variety.
  var wantCTA = !(leadRow.no_cta === "true" || leadRow.no_cta === true || leadRow.No_CTA === "true");
  var variantHint = { wantCTA: wantCTA, prefer: (conceptIndex % 2 === 0 ? "light" : "dark"), hasPhoto: !!leadNodeId };

  log("  Lead row: style='" + visualStyle + "', photo=" + (leadRow.figma_asset_name || leadNodeId || "(none)"));
  log("  Headline: '" + leadHeadline.substring(0, 60) + (leadHeadline.length > 60 ? "..." : "") + "'");

  // Meta wants a LONG and a SHORT copy version of the SAME concept, on the same
  // visual (per Adrie). Copy Version 1 = long (main headline + long primary text);
  // Copy Version 2 = short (short headline + short primary text). Same CTA.
  var longHeadline  = leadRow.Headline_Long || leadRow.Headline_On_Creative || leadHeadline;
  var longPrimary   = leadRow.Primary_Text_Long || leadRow.body_long || leadPrimary;
  var shortHeadline = leadRow.Headline_Short || leadRow.headline_short || leadHeadline;
  var shortPrimary  = leadRow.Primary_Text_Short || leadRow.body_short || leadPrimary;

  // Copy Version 1 panel (long): Notes > Copy Frame > [groups] > [last TEXT child]
  var f13 = findLayerByName(clone, "Frame 13");
  if (f13) {
    var notes = findDirectChildByName(f13, "Notes");
    var slots = getCopyFrameTextValueLayers(notes);
    if (slots.headline) await setTextLayer(slots.headline, longHeadline);
    if (slots.primary)  await setTextLayer(slots.primary, longPrimary);
    if (slots.cta && leadCta) await setTextLayer(slots.cta, leadCta);
    log("  Copy Version 1 (long): filled");
  }
  // Copy Version 2 panel (short)
  var f14 = findLayerByName(clone, "Frame 14");
  if (f14) {
    var notes2 = findDirectChildByName(f14, "Notes");
    var slots2 = getCopyFrameTextValueLayers(notes2);
    if (slots2.headline) await setTextLayer(slots2.headline, shortHeadline);
    if (slots2.primary)  await setTextLayer(slots2.primary, shortPrimary);
    if (slots2.cta && leadCta) await setTextLayer(slots2.cta, leadCta);
    log("  Copy Version 2 (short): filled");
  }

  // Update the "Ad Concept #" and "Ad Type" pills
  var content = findLayerByName(clone, "Content");
  if (content) {
    var adInfo = findDirectChildByName(content, "Ad Info");
    if (adInfo) {
      var conceptPill = findLayerByName(adInfo, "Ad Concept Number");
      if (conceptPill) {
        var btnLabel = findLayerByName(conceptPill, "Button Label");
        if (btnLabel) {
          var conceptLabel = "Ad Concept " + (conceptIndex + 1);
          if (leadRow.concept_tag) conceptLabel += " · " + leadRow.concept_tag;
          await setTextLayer(btnLabel, conceptLabel);
        }
      }
      var adType = findDirectChildByName(adInfo, "Ad Type");
      if (adType) {
        var typeLabel = findLayerByName(adType, "Button Label");
        if (typeLabel && visualStyle) await setTextLayer(typeLabel, visualStyle);
      }
    }
  }

  // Fill EVERY image frame slot in the board, using the lead photo + lead copy
  // for each. The styled template lookup is by visual_style + slot dimensions.
  var layout = content ? findDirectChildByName(content, "Layout - Static Feed") : null;
  if (!layout) {
    log("  ✗ 'Layout - Static Feed' frame not found in board");
    return { imagesApplied: 0, totalRows: conceptRows.length, boardSlots: 0 };
  }

  // Collect all FRAME children of layout that look like image slots (non-text).
  var slotFrames = [];
  for (var k = 0; k < layout.children.length; k++) {
    var c = layout.children[k];
    if (c.type === "FRAME" && "width" in c && c.width >= 800 && c.height >= 800) {
      slotFrames.push(c);
    }
  }
  log("  Image slot frames in board: " + slotFrames.length);

  var applied = 0;
  var slotFilled = []; // parallel to slotFrames; true if this slot got content
  for (var s = 0; s < slotFrames.length; s++) {
    var imageFrame = slotFrames[s];
    var w = Math.round(imageFrame.width);
    var h = Math.round(imageFrame.height);
    slotFilled.push(false);

    // All three sizes (1:1 1440x1440, 4:5 1440x1800, 9:16 1080x1920) now have
    // styled templates from Elise, so no size is skipped — each slot gets its
    // correctly-sized styled template.

    if (styledSearchRoot) {
      var found = findStyledTemplate(styledSearchRoot, visualStyle, w, h, variantHint);
      if (found) {
        var styledClone = found.node.clone();
        styledClone.name = "STYLED_concept-" + (conceptIndex + 1) + "_" + w + "x" + h;
        // Detach all instances so Brandon can edit any layer in the clone
        detachAllInstances(styledClone);

        var key = normalizeStyle(visualStyle);

        // Apply lead photo unless this style keeps its template imagery
        // (testimonial green gradient + headshot, text-with-button gradient).
        if (leadNodeId && !STYLES_THAT_SKIP_IMAGE[key]) {
          await applyLibraryImageToClone(styledClone, leadNodeId);
        } else if (STYLES_THAT_SKIP_IMAGE[key]) {
          log("    (style '" + visualStyle + "' skips image override; keeping template imagery)");
        }

        // Fill text by ROLE. Copy_* is Elise's current convention, so try it
        // FIRST, then fall back to the legacy per-style layer names.
        var headlineCandidates = ["Copy_Headline"].concat(STYLE_HEADLINE_LAYERS[key] || []).concat(["headline_text"]);
        if (leadHeadline) await setFirstTextByCandidates(styledClone, headlineCandidates, leadHeadline);
        // On-creative subhead ONLY. The Meta Primary Text (short/long) belongs in
        // the left panels — it must NEVER be printed on the image. Use the
        // dedicated Subhead_On_Creative; if a manifest predates the copy split and
        // has none, clear the subhead rather than duplicating the primary text.
        var subheadCandidates = ["Copy_Subhead"].concat(STYLE_SUBHEAD_LAYERS[key] || []);
        var creativeSubhead = leadRow.Subhead_On_Creative || leadRow.subhead_on_creative || "";
        await setFirstTextByCandidates(styledClone, subheadCandidates, creativeSubhead);
        if (leadCta && !STYLES_THAT_SKIP_CTA[key]) {
          await setFirstTextByCandidates(styledClone, ["Copy_CTA", "cta_text", "CTA_Text", "CTA", "cta"], leadCta);
        }
        if (key === "sticky note") {
          await fillStickyNoteCopy(styledClone, leadHeadline, leadPrimary, leadRow.Primary_Text_Long || leadPrimary);
        }

        // ── Per-style STRUCTURED copy (same fills as the styled_per_row path) ──
        // Testimonial quote + author
        var quote = leadRow.Primary_Text_Long || leadRow.body_long || leadPrimary;
        if (quote) await setFirstTextByCandidates(styledClone, ["Copy_Testimonial"], quote);
        if (leadRow.Testimonial_Author) await setFirstTextByCandidates(styledClone, ["Copy_Author"], leadRow.Testimonial_Author);
        // Search Results — up to three role rows
        var srRows = splitPipe(leadRow.Search_Results);
        for (var si = 0; si < srRows.length && si < 3; si++) await setFirstTextByCandidates(styledClone, ["Copy_Title" + (si + 1)], srRows[si]);
        // Social Media Profile
        if (leadRow.Profile_Name) await setFirstTextByCandidates(styledClone, ["Copy_Name"], leadRow.Profile_Name);
        if (leadRow.Profile_Title) await setFirstTextByCandidates(styledClone, ["Copy_Title"], leadRow.Profile_Title);
        if (leadRow.Profile_Left) await setFirstTextByCandidates(styledClone, ["Copy_Left-Column"], leadRow.Profile_Left);
        if (leadRow.Profile_Right) await setFirstTextByCandidates(styledClone, ["Copy_Right-Column"], leadRow.Profile_Right);
        // Chat Bubble + Text-with-Button
        if (leadRow.Chat_Label) await setFirstTextByCandidates(styledClone, ["Copy_Chat-Bubble-1"], leadRow.Chat_Label);
        if (leadRow.Chat_Message) await setFirstTextByCandidates(styledClone, ["Copy_Chat-Bubble-2"], leadRow.Chat_Message);
        if (leadRow.Button_Text) await setFirstTextByCandidates(styledClone, ["Copy_Button"], leadRow.Button_Text);
        // Pie Chart — four quadrant labels + slice value
        var pieLabels = splitPipe(leadRow.Pie_Labels);
        var quad = ["Copy_TopLeft", "Copy_TopRight", "Copy_BottomLeft", "Copy_BottomRight"];
        for (var qi = 0; qi < pieLabels.length && qi < 4; qi++) await setFirstTextByCandidates(styledClone, [quad[qi]], pieLabels[qi]);
        if (key === "pie chart" && (leadRow.Chart_Pct || leadRow.chart_pct)) await fillPieChartValue(styledClone, leadRow.Chart_Pct || leadRow.chart_pct);
        // Us vs Them (side headlines + bullets) and Poll (question + bars)
        if (key === "us vs them") await fillUsVsThemCopy(styledClone, leadRow);
        if (key === "poll") await fillPollCopy(styledClone, leadRow);

        // Safety net: never ship lorem-ipsum placeholder text on the styled ad.
        await clearResidualLoremIpsum(styledClone, leadRow);

        // Place styled clone inside the slot frame
        if ("appendChild" in imageFrame) {
          imageFrame.appendChild(styledClone);
          if ("x" in styledClone) { styledClone.x = 0; styledClone.y = 0; }
        } else if (imageFrame.parent && "appendChild" in imageFrame.parent) {
          imageFrame.parent.appendChild(styledClone);
          styledClone.x = imageFrame.x;
          styledClone.y = imageFrame.y;
        }
        applied++;
        slotFilled[s] = true;
        log("    ✓ " + w + "x" + h + " slot: placed " + (found.viaSet ? found.viaSet.name + " variant" : found.node.name));
        continue;
      } else {
        log("    ⚠ " + w + "x" + h + " slot: no styled template for '" + visualStyle + "'");
      }
    }

    // Fallback: raw photo fill on the empty slot (only if styled template was missing)
    if (leadNodeId) {
      var libraryNode = await figma.getNodeByIdAsync(leadNodeId);
      if (libraryNode) {
        var sourceFill = findSourceImageFill(libraryNode);
        if (sourceFill && applyImageFillToLayer(imageFrame, sourceFill)) {
          applied++;
          slotFilled[s] = true;
          log("    ✓ " + w + "x" + h + " slot: raw photo fill (no styled template)");
        }
      }
    }
  }

  // Hide any unfilled slot (and its corresponding size label TEXT) so the
  // concept board looks clean — no orphan empty rectangles.
  var unfilled = 0;
  for (var s2 = 0; s2 < slotFrames.length; s2++) {
    if (!slotFilled[s2]) {
      var f = slotFrames[s2];
      var w2 = Math.round(f.width);
      var h2 = Math.round(f.height);
      f.visible = false;
      // Find and hide the matching label TEXT in the same Layout container.
      // Labels are formatted like "9:16 - 1080x1920" / "1:1 - 1440x1440".
      for (var i = 0; i < layout.children.length; i++) {
        var c = layout.children[i];
        if (c.type === "TEXT" && c.characters && c.characters.indexOf(w2 + "x" + h2) !== -1) {
          c.visible = false;
        }
      }
      unfilled++;
    }
  }
  if (unfilled > 0) log("  Hidden " + unfilled + " unfilled slot(s)");

  // Board-wide safety net: catch any lorem-ipsum left ANYWHERE on the board —
  // the left copy panel, un-mapped structured layers (e.g. Us-Vs-Them "them"
  // bullets), subheads without copy — and replace with real row copy. Guarantees
  // no board ever ships placeholder text.
  await clearResidualLoremIpsum(clone, leadRow);

  return { imagesApplied: applied, totalRows: conceptRows.length, boardSlots: slotFrames.length };
}

function groupRowsByConcept(rows) {
  var groups = {};
  var order = [];
  for (var i = 0; i < rows.length; i++) {
    var key = rows[i].concept_tag || rows[i].asset_id || ("concept_" + i);
    if (!groups[key]) { groups[key] = []; order.push(key); }
    groups[key].push(rows[i]);
  }
  return order.map(function (k) { return { tag: k, rows: groups[k] }; });
}

// ── Legacy mode ─────────────────────────────────────────────────────────────

async function fillLegacyTemplate(clone, row) {
  var nodeId = row.figma_node_id || row.figma_library_node_id || row.figma_asset_id || "";
  var imgOk = await applyLibraryImageToClone(clone, nodeId);
  await setFirstTextByCandidates(clone, ["headline_text"], row.Headline_On_Creative || row.headline || "");
  await setFirstTextByCandidates(clone, ["body_text"], row.Primary_Text_Short || row.body || "");
  await setFirstTextByCandidates(clone, ["cta_text"], row.CTA || row.cta || "");
  return imgOk;
}

// ── Assemble ────────────────────────────────────────────────────────────────

// The standard output frame the plugin clones once per concept. Elise owns it;
// ADAM never rebuilds the layout, only clones + fills it. Found by exact name so
// there's no "Capture Template" click.
var BOARD_MASTER_NAME = "Meta - Static Grouped";
function findBoardMaster() {
  var match = null;
  function walk(n) {
    if (match) return;
    if (n.name === BOARD_MASTER_NAME && n.type === "FRAME") { match = n; return; }
    if ("children" in n) {
      for (var i = 0; i < n.children.length; i++) walk(n.children[i]);
    }
  }
  walk(figma.root);
  return match;
}

// ── Normalize layer names (one-time Figma cleanup) ───────────────────────────
// Standardizes off-convention layer names to the scheme ADAM expects, so Figma
// stays the clean source of truth. COLLISION-AWARE: a layer is only renamed when
// the new name isn't already used elsewhere in its enclosing template — never
// collapses two layers onto one name (verified: 36 safe renames, 1 skip).
async function normalizeLayerNames() {
  await figma.loadAllPagesAsync();
  var IMG_MAP = { "Image_Placeholder": "Image-Placeholder", "image_placeholder": "Image-Placeholder",
                  "right_image_placeholder": "Right-Image-Placeholder", "left_image_placeholder": "Left-Image-Placeholder" };
  var TXT_MAP = { "TextOnly_headline_text": "Copy_Headline", "TextOnly_Subhead_Text": "Copy_Subhead",
                  "cta_text": "Copy_CTA", "Notification_Headline_Text": "Copy_Headline", "Subhead-Text": "Copy_Subhead" };
  var renamed = 0, skipped = 0;

  function walkAll(n, fn) { fn(n); if ("children" in n) for (var i = 0; i < n.children.length; i++) walkAll(n.children[i], fn); }
  function enclosingTemplate(node) {
    var p = node.parent;
    while (p) {
      if (p.name && (p.name.indexOf("Template_") === 0 || p.name.indexOf("Adtype") === 0)) return p;
      p = p.parent;
    }
    return node.parent || node;
  }
  function nameExistsIn(root, target, except) {
    var found = false;
    (function w(n) { if (found) return; if (n !== except && n.name === target) { found = true; return; }
      if ("children" in n) for (var i = 0; i < n.children.length; i++) w(n.children[i]); })(root);
    return found;
  }
  function tryRename(node, target) {
    if (node.name === target) return;
    if (nameExistsIn(enclosingTemplate(node), target, node)) { skipped++; return; }
    node.name = target; renamed++;
  }

  walkAll(figma.root, function (node) {
    var nm = node.name || "";
    // frame names → convention (no collision risk; names are unique per frame)
    if ((node.type === "FRAME" || node.type === "COMPONENT" || node.type === "INSTANCE") && nm.indexOf("Template_") === 0) {
      var nn = nm.replace("Template_Adtype_Hybrid_", "Template_Hybrid_")
                 .replace("Template_Adtype_Talent-Profile_", "Template_Talent-Profile_")
                 .replace("Template_LifestylePhoto_", "Template_Lifestyle-Photo-Full-Bleed_")
                 .replace(/_1440x1880$/, "_1440x1800");
      if (nn !== nm) { node.name = nn; renamed++; }
    }
    // image layers (must actually carry an IMAGE fill)
    if (IMG_MAP[nm] && node.fills && node.fills.length &&
        node.fills.some(function (f) { return f.type === "IMAGE"; })) {
      tryRename(node, IMG_MAP[nm]);
    }
    // legacy text layers → Copy_*
    if (node.type === "TEXT" && TXT_MAP[nm]) tryRename(node, TXT_MAP[nm]);
  });

  // board master: left-panel value layers → CopyV{n}_{field}; slot 1440x1080 → 1440x1800
  var board = findBoardMaster();
  if (board) {
    walkAll(board, function (n) { if (n.name === "1440x1080") { n.name = "1440x1800"; renamed++; } });
    var panel = findLayerByName(board, "Frame 15");
    if (panel) {
      ["Frame 13", "Frame 14"].forEach(function (fname, idx) {
        var vframe = findLayerByName(panel, fname);
        if (!vframe) return;
        var notes = findDirectChildByName(vframe, "Notes");
        var slots = getCopyFrameTextValueLayers(notes);
        var v = idx + 1;
        if (slots.headline) { slots.headline.name = "CopyV" + v + "_Headline"; renamed++; }
        if (slots.primary)  { slots.primary.name  = "CopyV" + v + "_Primary";  renamed++; }
        if (slots.cta)      { slots.cta.name       = "CopyV" + v + "_CTA";      renamed++; }
      });
    }
  }

  log("✓ Normalize complete: " + renamed + " renamed, " + skipped + " skipped (collision-avoided).");
  figma.notify("Layer names normalized: " + renamed + " renamed, " + skipped + " skipped.");
  figma.ui.postMessage({ type: "normalize-complete", renamed: renamed, skipped: skipped });
}

// Delete ONLY boards this plugin produced (names starting ASSEMBLED_concept- or
// STYLED_concept-). Never touches Template_*/Adtype_* or any reference build.
// The output area: a 'Generated Tests' SECTION whose FRAME child is the per-sprint
// container template. The plugin clones that frame each run, so the destination is
// fully controlled — no capture needed. Returns {park, template} (either may be null).
function findGeneratedArea() {
  var park = null;
  (function walk(n) {
    if (park) return;
    if (n.type === "SECTION" && /generated tests/i.test(n.name || "")) { park = n; return; }
    if ("children" in n) for (var i = 0; i < n.children.length; i++) walk(n.children[i]);
  })(figma.root);
  var tmpl = null;
  if (park && park.children) {
    for (var i = 0; i < park.children.length; i++) {
      if (park.children[i].type === "FRAME") { tmpl = park.children[i]; break; }
    }
  }
  return { park: park, template: tmpl };
}

async function cleanupTestBoards() {
  await figma.loadAllPagesAsync();
  var re = /^(ASSEMBLED|STYLED)_concept-/;
  var toDelete = [];
  function walk(n) {
    // A whole 'Sprint · ' container (the cloned frame, or a legacy section) goes
    // wholesale — its boards with it. Then any loose ASSEMBLED_/STYLED_concept
    // board. Never matches the container TEMPLATE ('Testing_...' / 'Meta - Static
    // Grouped'), so your 'Generated Tests' template stays intact.
    if (/^Sprint · /.test(n.name || "")) { toDelete.push(n); return; }
    if (n.name && re.test(n.name)) { toDelete.push(n); return; }
    if ("children" in n) for (var i = 0; i < n.children.length; i++) walk(n.children[i]);
  }
  for (var p = 0; p < figma.root.children.length; p++) walk(figma.root.children[p]);
  var count = toDelete.length;
  for (var d = 0; d < toDelete.length; d++) { try { toDelete[d].remove(); } catch (e) {} }
  log("🧹 Deleted " + count + " test board(s) (ASSEMBLED_concept-* / STYLED_concept-*).");
  figma.notify("Deleted " + count + " test boards.");
  figma.ui.postMessage({ type: "cleanup-complete", count: count });
}

async function assemble(payload) {
  await figma.loadAllPagesAsync();

  // Capture is now optional. When nothing is captured, default to styled_per_row
  // mode using the entire current page as the search root.
  var template = null;
  if (capturedTemplateId) {
    template = await figma.getNodeByIdAsync(capturedTemplateId);
    if (!template) {
      log("⚠ Captured node no longer exists — falling back to page search.");
      capturedTemplateId = null;
    }
  }
  var forcedMode = null;
  if (!template) {
    // Standard output: clone the board master ('Meta - Static Grouped') per
    // concept — no "Capture Template" click required. Fall back to template
    // auto-discovery only if the board master isn't in the file.
    var boardMaster = findBoardMaster();
    if (boardMaster) {
      template = boardMaster;
      forcedMode = "concept_board";
      log("No template captured — using board master '" + boardMaster.name + "' (concept_board mode; no click needed).");
    } else {
      template = findTemplatesRoot();
      var rootLabel = (template === figma.root) ? "entire document" : ("page '" + template.name + "'");
      log("Board master not found — auto-discovering templates across the " + rootLabel + " (styled_per_row mode).");
    }
  }

  var manifest;
  try { manifest = parseCSV(payload.csv); }
  catch (e) { err("CSV parse error: " + e.message); return; }

  var mode = forcedMode || detectTemplateMode(template);
  log("\n=== Assembly start: mode=" + mode + ", " + manifest.length + " rows ===");

  var destination = null;
  if (capturedDestinationId) {
    destination = await figma.getNodeByIdAsync(capturedDestinationId);
    if (!destination) capturedDestinationId = null;
  }

  var baseX, baseY;
  if (destination && "x" in destination) { baseX = 0; baseY = 0; }
  else {
    // Place assembled frames in empty space to the RIGHT of everything already
    // on the page, so a run never lands on top of Elise's templates or prior runs.
    var maxRight = null, topY = null;
    var pk = figma.currentPage.children;
    for (var pi = 0; pi < pk.length; pi++) {
      var pn = pk[pi];
      if (!("x" in pn) || !("width" in pn)) continue;
      var right = pn.x + pn.width;
      if (maxRight === null || right > maxRight) maxRight = right;
      if (topY === null || pn.y < topY) topY = pn.y;
    }
    if (maxRight === null) {
      var v = figma.viewport.center;
      baseX = v.x - 800; baseY = v.y - 800;
    } else {
      baseX = maxRight + 2000;   // clear gap to the right of existing content
      baseY = (topY !== null ? topY : 0);
    }
  }

  var assembled = 0;
  var assembledIds = [];

  if (mode === "styled_per_row") {
    // Use the captured frame as the search root for templates.
    // Fall back to document-wide auto-discovery if the captured frame has too few
    // templates (e.g., user captured one Adtype container but manifest has multiple
    // styles), so the finder can scope each style by its Adtype container across pages.
    var searchRoot = template;
    var distinctStyles = {};
    for (var i = 0; i < manifest.length; i++) {
      var s = normalizeStyle(manifest[i].Visual_Style || manifest[i].visual_style);
      if (s) distinctStyles[s] = true;
    }
    var styleCount = Object.keys(distinctStyles).length;
    if (styleCount > 1) {
      searchRoot = findTemplatesRoot();
      var srLabel = (searchRoot === figma.root) ? "entire document" : ("page '" + searchRoot.name + "'");
      log("Manifest has " + styleCount + " distinct styles — auto-searching the " + srLabel + " for templates");
    }
    var result = await assembleStyledPerRow(searchRoot, manifest, destination, baseX, baseY);
    assembled = result.assembled;
    assembledIds = result.ids;
    log("\n✓ Assembly complete: " + assembled + " assembled, " + result.failed + " failed");
  } else if (mode === "concept_board") {
    var groups = groupRowsByConcept(manifest);
    log("Grouped " + manifest.length + " rows into " + groups.length + " concepts");
    // For concept_board mode, look for styled templates on the entire page so we can
    // place them inside each concept board's image frame slots.
    var styledSearchRoot = figma.currentPage;
    log("Styled-template search root: current page (will place styled clones inside image slots)");

    // Output goes into a CLONE of the 'Generated Tests' container (the frame
    // inside the 'Generated Tests' section). Each run = one cloned container,
    // named per sprint, parked inside 'Generated Tests' to the right of existing
    // sprints — the plugin controls the destination, no capture needed. Honors an
    // explicit captured destination if one was set; falls back to loose page
    // placement if the area isn't in the file.
    var area = findGeneratedArea();
    var insetX = 579, insetY = 460, pitch = template.height + 240;
    var sprintContainer = null;
    if (!(destination && "appendChild" in destination) && area.template) {
      // Learn the layout (inset + board pitch) from the container's own boards.
      var tmplKids = (area.template.children || []).filter(function (c) { return "width" in c && "x" in c; });
      if (tmplKids.length) {
        insetX = tmplKids[0].x; insetY = tmplKids[0].y;
        if (tmplKids.length >= 2) pitch = tmplKids[1].y - tmplKids[0].y;
      }
      sprintContainer = area.template.clone();
      var first = manifest[0] || {};
      var runLabel = first.sprint_id || first.Sprint_Id ||
        [first.Driver, first.Platform, first.Delivery_Date].filter(function (x) { return x; }).join(" · ");
      if (!runLabel) runLabel = "Generated " + new Date().toISOString().slice(0, 16).replace("T", " ");
      sprintContainer.name = "Sprint · " + runLabel;
      // Clear the placeholder boards inside the clone.
      var placeholders = (sprintContainer.children || []).slice();
      for (var pr = 0; pr < placeholders.length; pr++) { try { placeholders[pr].remove(); } catch (e) {} }
      // Park it: append to the 'Generated Tests' section, right of existing content.
      if (area.park && "appendChild" in area.park) area.park.appendChild(sprintContainer);
      else figma.currentPage.appendChild(sprintContainer);
      var px = area.template.x + area.template.width + 600, py = area.template.y;
      if (area.park && area.park.children) {
        var maxR = null;
        for (var q = 0; q < area.park.children.length; q++) {
          var ch = area.park.children[q];
          if (ch !== sprintContainer && "x" in ch && "width" in ch) { var rr = ch.x + ch.width; if (maxR === null || rr > maxR) maxR = rr; }
        }
        if (maxR !== null) px = maxR + 600;
      }
      sprintContainer.x = px; sprintContainer.y = py;
      try { sprintContainer.resizeWithoutConstraints(sprintContainer.width, insetY + groups.length * pitch); } catch (e) {}
      log("Output: cloned '" + area.template.name + "' → '" + sprintContainer.name + "' in 'Generated Tests'.");
    } else if (!area.template) {
      log("⚠ 'Generated Tests' container not found — placing boards loose on the page.");
    }
    var container = sprintContainer || destination;

    for (var g = 0; g < groups.length; g++) {
      var group = groups[g];
      log("\n[Concept " + (g + 1) + "/" + groups.length + "] " + group.tag);
      var clone = template.clone();
      clone.name = "ASSEMBLED_concept-" + (g + 1) + "_" + group.tag;
      // Detach instances so the entire concept board (including its embedded
      // copy/notes panels and pills) is fully editable for Brandon's polish.
      detachAllInstances(clone);
      if (container && "appendChild" in container) container.appendChild(clone);
      else figma.currentPage.appendChild(clone);
      if (sprintContainer) { clone.x = insetX; clone.y = insetY + (g * pitch); }   // relative to the container frame
      else { clone.x = baseX; clone.y = baseY + (g * (template.height + 240)); }
      var r = await fillConceptBoard(clone, group.rows, g, styledSearchRoot);
      log("  Slots filled: " + r.imagesApplied + "/" + (r.boardSlots != null ? r.boardSlots : r.totalRows));
      if (r.imagesApplied > 0) { assembled++; assembledIds.push(clone.id); }
      await new Promise(function (r) { setTimeout(r, 50); });
    }
    log("\n✓ Assembly complete: " + assembled + "/" + groups.length + " boards" + (sprintContainer ? " (in '" + sprintContainer.name + "')" : ""));
  } else {
    // Legacy
    for (var idx = 0; idx < manifest.length; idx++) {
      var row = manifest[idx];
      var assetId = row.asset_id || ("ad_" + (idx + 1));
      log("\n[" + assetId + "] " + (row.Visual_Style || row.visual_style || ""));
      var clone = template.clone();
      clone.name = "ASSEMBLED_" + assetId;
      if (destination && "appendChild" in destination) destination.appendChild(clone);
      else figma.currentPage.appendChild(clone);
      clone.x = baseX + (idx * (template.width + 80));
      clone.y = baseY;
      var ok = await fillLegacyTemplate(clone, row);
      if (ok) { assembled++; assembledIds.push(clone.id); }
      await new Promise(function (r) { setTimeout(r, 50); });
    }
    log("\n✓ Legacy assembly complete: " + assembled + "/" + manifest.length);
  }

  figma.ui.postMessage({
    type: "assembly-complete",
    assembled: assembled,
    failed: manifest.length - assembled,
    total: manifest.length,
    frameIds: assembledIds,
  });

  if (assembledIds.length > 0) {
    var nodes = [];
    for (var n = 0; n < assembledIds.length; n++) {
      var node = await figma.getNodeByIdAsync(assembledIds[n]);
      if (node) nodes.push(node);
    }
    if (nodes.length > 0) {
      figma.currentPage.selection = nodes;
      figma.viewport.scrollAndZoomIntoView(nodes);
    }
  }
}

// ── Message router ──────────────────────────────────────────────────────────

figma.ui.onmessage = async function (msg) {
  if (msg.type === "capture-template") captureTemplate();
  else if (msg.type === "capture-destination") captureDestination();
  else if (msg.type === "assemble") await assemble(msg);
  else if (msg.type === "normalize-names") await normalizeLayerNames();
  else if (msg.type === "cleanup-boards") await cleanupTestBoards();
  else if (msg.type === "close") figma.closePlugin();
};
