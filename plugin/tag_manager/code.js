// ADAM Tag Manager — Figma plugin
// =================================================
// A live, faceted tag browser + tag editor + CSV exporter for Brandon's
// photo library. Mirrors pipeline/figma_library.py for tag detection.
//
// Convention (must match library_tagger/code.js and figma_library.py):
//   A tagged photo is a FRAME/COMPONENT/INSTANCE that has BOTH:
//     1. A direct child with an image fill, AND
//     2. At least 3 direct children with visible=false whose names match
//        the tag registry below.
//   Tag nodes are visible=false and can be RECTANGLE/FRAME/INSTANCE/
//   COMPONENT/ELLIPSE/GROUP. The node's NAME is the tag value.
//   New tags are written as 1x1 hidden rectangles with name = tag value.

figma.showUI(__html__, { width: 540, height: 800 });

// ── Tag registry — must stay in sync with pipeline/figma_library.py ──────────

var TAG_REGISTRY = {
  "lifestyle_photo": "style", "photo_with_text": "style", "testimonial": "style",
  "team": "people", "hands_only": "people", "none": "people",
  "laptop": "objects", "phone": "objects", "tablet": "objects",
  "desktop_monitor": "objects", "headphones": "objects", "notebook": "objects",
  "pen": "objects", "coffee": "objects", "plant": "objects",
  "whiteboard": "objects", "camera": "objects", "book": "objects",
  "document": "objects",
  "home_office": "setting", "corporate_office": "setting", "coworking": "setting",
  "coffee_shop": "setting", "outdoor": "setting", "studio": "setting",
  "kitchen": "setting", "bookstore": "setting", "greenhouse": "setting",
  "retail": "setting", "hotel": "setting", "warehouse": "setting",
  "asian": "demographics", "south_asian": "demographics", "black": "demographics",
  "latino": "demographics", "white": "demographics", "mixed": "demographics",
  "young_adult": "age", "adult": "age", "mature": "age",
  "warm": "palette", "cool": "palette", "neutral": "palette",
  "green": "palette", "dark": "palette", "bright": "palette",
  "upwork_green": "palette",
  "focused": "mood", "confident": "mood", "happy": "mood",
  "contemplative": "mood", "surprised": "mood",
  "typing": "activity", "on_phone": "activity", "on_call": "activity",
  "meeting": "activity", "thinking": "activity", "presenting": "activity",
  "holding_coffee": "activity", "holding_object": "activity",
  "walking": "activity", "standing": "activity", "gesturing": "activity",
  "facing_camera": "activity", "working": "activity", "browsing": "activity",
  "reading": "activity", "writing": "activity", "listening": "activity",
  "drawing": "activity", "waving": "activity", "sitting": "activity",
  "centered": "composition", "left_of_frame": "composition",
  "right_of_frame": "composition", "close_up": "composition",
  "medium_shot": "composition", "wide_shot": "composition",
};

var PEOPLE_PATTERN = /^(man|woman)_\d+$/;
var RIGHTS_PATTERN = /^rights_(\d{4})_(\d{2})$/;
var TAG_NODE_TYPES = { RECTANGLE: 1, FRAME: 1, INSTANCE: 1, COMPONENT: 1, ELLIPSE: 1, GROUP: 1 };
var PHOTO_NODE_TYPES = { FRAME: 1, COMPONENT: 1, INSTANCE: 1 };
var MIN_RECOGNIZED_TAGS_FOR_PHOTO = 3;

// CSV column layout — matches library_tagger/code.js
var CSV_TAG_COLUMNS = {
  people: { multi: true,  dim: "people" },
  demographic: { multi: true,  dim: "demographics" },
  age: { multi: false, dim: "age" },
  device: { multi: true,  dim: "objects" },
  location: { multi: false, dim: "setting" },
  color_palette: { multi: true,  dim: "palette" },
  style_fit: { multi: false, dim: "style" },
  activity: { multi: true,  dim: "activity" },
  rights: { multi: false, dim: "rights" },
};
var CSV_HEADER = ["photo_name", "description"]
  .concat(Object.keys(CSV_TAG_COLUMNS));

// ── Helpers ──────────────────────────────────────────────────────────────────

function classifyTag(tag) {
  if (RIGHTS_PATTERN.test(tag)) return "rights";
  if (PEOPLE_PATTERN.test(tag)) return "people";
  return TAG_REGISTRY[tag] || "uncategorized";
}

function isRecognizedTag(name) {
  if (!name) return false;
  if (RIGHTS_PATTERN.test(name)) return true;
  if (PEOPLE_PATTERN.test(name)) return true;
  return Object.prototype.hasOwnProperty.call(TAG_REGISTRY, name);
}

function childHasImageFill(child) {
  if (!("fills" in child)) return false;
  var fills = child.fills;
  if (!Array.isArray(fills)) return false;
  for (var i = 0; i < fills.length; i++) {
    if (fills[i] && fills[i].type === "IMAGE") return true;
  }
  return false;
}

function isTaggedPhotoNode(node) {
  if (!node || !PHOTO_NODE_TYPES[node.type]) return false;
  if (!("children" in node) || !node.children || node.children.length === 0) return false;

  var hasDirectImage = false;
  var recognizedTagCount = 0;

  for (var i = 0; i < node.children.length; i++) {
    var child = node.children[i];
    if (!child) continue;
    if (childHasImageFill(child)) hasDirectImage = true;
    if (child.visible === false && TAG_NODE_TYPES[child.type]) {
      var name = (child.name || "").trim();
      if (name && isRecognizedTag(name)) recognizedTagCount++;
    }
  }
  return hasDirectImage && recognizedTagCount >= MIN_RECOGNIZED_TAGS_FOR_PHOTO;
}

function getTagsOnPhoto(photoNode) {
  if (!("children" in photoNode)) return [];
  var tags = [];
  for (var i = 0; i < photoNode.children.length; i++) {
    var c = photoNode.children[i];
    if (!c) continue;
    if (c.visible === false && TAG_NODE_TYPES[c.type]) {
      var name = (c.name || "").trim();
      if (name) tags.push(name);
    }
  }
  return tags;
}

function getTagNodesOnPhoto(photoNode) {
  // Returns the actual node objects (for editing)
  if (!("children" in photoNode)) return [];
  var nodes = [];
  for (var i = 0; i < photoNode.children.length; i++) {
    var c = photoNode.children[i];
    if (!c) continue;
    if (c.visible === false && TAG_NODE_TYPES[c.type]) {
      if ((c.name || "").trim()) nodes.push(c);
    }
  }
  return nodes;
}

function walkForPhotos(node, results) {
  if (!node) return;
  if (isTaggedPhotoNode(node)) {
    results.push(node);
    return;
  }
  if (!("children" in node)) return;
  for (var i = 0; i < node.children.length; i++) {
    walkForPhotos(node.children[i], results);
  }
}

// ── In-memory cache ─────────────────────────────────────────────────────────

var cachedPhotos = []; // [{ id, name, tags }]
var nodeCache = {};    // id → SceneNode

// ── Scan ─────────────────────────────────────────────────────────────────────

async function scanLibrary() {
  await figma.loadAllPagesAsync();
  var photoNodes = [];
  walkForPhotos(figma.currentPage, photoNodes);

  cachedPhotos = [];
  nodeCache = {};
  for (var i = 0; i < photoNodes.length; i++) {
    var photo = photoNodes[i];
    var tags = getTagsOnPhoto(photo);
    if (tags.length === 0) continue;
    cachedPhotos.push({ id: photo.id, name: photo.name, tags: tags });
    nodeCache[photo.id] = photo;
  }

  return {
    photos: cachedPhotos,
    registry: TAG_REGISTRY,
  };
}

// ── Tag mutation (editor) ───────────────────────────────────────────────────

async function addTagToPhoto(photoId, tagName) {
  tagName = (tagName || "").trim();
  if (!tagName) return { ok: false, reason: "empty tag" };

  var photo = nodeCache[photoId] || await figma.getNodeByIdAsync(photoId);
  if (!photo) return { ok: false, reason: "photo not found" };

  // Skip if already present
  var existing = getTagsOnPhoto(photo);
  if (existing.indexOf(tagName) !== -1) return { ok: true, alreadyPresent: true };

  var rect = figma.createRectangle();
  rect.name = tagName;
  rect.resize(1, 1);
  rect.visible = false;
  photo.appendChild(rect);

  // Refresh cache entry
  refreshCacheEntry(photo);
  return { ok: true };
}

async function removeTagFromPhoto(photoId, tagName) {
  var photo = nodeCache[photoId] || await figma.getNodeByIdAsync(photoId);
  if (!photo) return { ok: false, reason: "photo not found" };

  var nodes = getTagNodesOnPhoto(photo);
  var removed = 0;
  for (var i = 0; i < nodes.length; i++) {
    if ((nodes[i].name || "").trim() === tagName) {
      nodes[i].remove();
      removed++;
    }
  }
  refreshCacheEntry(photo);
  return { ok: true, removed: removed };
}

async function copyTagsFromTo(fromId, toIds, replace) {
  var src = nodeCache[fromId] || await figma.getNodeByIdAsync(fromId);
  if (!src) return { ok: false, reason: "source not found" };

  var srcTags = getTagsOnPhoto(src);
  if (srcTags.length === 0) return { ok: false, reason: "source has no tags" };

  var copiedTo = 0;
  for (var i = 0; i < toIds.length; i++) {
    var tgt = nodeCache[toIds[i]] || await figma.getNodeByIdAsync(toIds[i]);
    if (!tgt) continue;
    if (tgt.id === src.id) continue;

    // If replace mode, clear all existing tags first
    if (replace) {
      var existingNodes = getTagNodesOnPhoto(tgt);
      for (var e = 0; e < existingNodes.length; e++) existingNodes[e].remove();
    }

    var existingTags = replace ? [] : getTagsOnPhoto(tgt);
    var existingSet = {};
    for (var x = 0; x < existingTags.length; x++) existingSet[existingTags[x]] = 1;

    for (var t = 0; t < srcTags.length; t++) {
      if (existingSet[srcTags[t]]) continue; // already has it
      var rect = figma.createRectangle();
      rect.name = srcTags[t];
      rect.resize(1, 1);
      rect.visible = false;
      tgt.appendChild(rect);
    }
    refreshCacheEntry(tgt);
    copiedTo++;
  }

  return { ok: true, copiedTo: copiedTo, srcTagCount: srcTags.length };
}

function refreshCacheEntry(photoNode) {
  if (!isTaggedPhotoNode(photoNode)) {
    // Photo may have dropped below the threshold
    delete nodeCache[photoNode.id];
    cachedPhotos = cachedPhotos.filter(function (p) { return p.id !== photoNode.id; });
    return;
  }
  var tags = getTagsOnPhoto(photoNode);
  nodeCache[photoNode.id] = photoNode;
  var idx = -1;
  for (var i = 0; i < cachedPhotos.length; i++) {
    if (cachedPhotos[i].id === photoNode.id) { idx = i; break; }
  }
  var entry = { id: photoNode.id, name: photoNode.name, tags: tags };
  if (idx >= 0) cachedPhotos[idx] = entry;
  else cachedPhotos.push(entry);
}

// ── CSV export ──────────────────────────────────────────────────────────────

function csvEscape(v) {
  if (v === null || v === undefined) return "";
  var s = String(v);
  if (s.indexOf(",") >= 0 || s.indexOf('"') >= 0 || s.indexOf("\n") >= 0) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function buildCsv() {
  var rows = [CSV_HEADER.map(csvEscape).join(",")];

  // Sort photos by name for stable output
  var sorted = cachedPhotos.slice().sort(function (a, b) {
    return (a.name || "").localeCompare(b.name || "");
  });

  for (var i = 0; i < sorted.length; i++) {
    var p = sorted[i];
    var bucket = {};
    for (var col in CSV_TAG_COLUMNS) bucket[col] = [];

    for (var t = 0; t < p.tags.length; t++) {
      var tag = p.tags[t];
      var dim = classifyTag(tag);

      // Map tag's dimension to its CSV column
      var matched = false;
      for (var col2 in CSV_TAG_COLUMNS) {
        if (CSV_TAG_COLUMNS[col2].dim === dim) {
          bucket[col2].push(tag);
          matched = true;
          break;
        }
      }
      // Tags that don't match any CSV column (composition, mood, uncategorized)
      // are dropped from CSV but remain in Figma
    }

    var row = [csvEscape(p.name), csvEscape("")];
    for (var col3 in CSV_TAG_COLUMNS) {
      var meta = CSV_TAG_COLUMNS[col3];
      var values = bucket[col3];
      var cellValue = meta.multi ? values.join(", ") : (values[0] || "");
      row.push(csvEscape(cellValue));
    }
    rows.push(row.join(","));
  }

  return rows.join("\n");
}

// ── Selection bridge ────────────────────────────────────────────────────────

function postSelection() {
  var sel = figma.currentPage.selection;
  var selectedPhotos = [];
  for (var i = 0; i < sel.length; i++) {
    var n = sel[i];
    if (isTaggedPhotoNode(n)) {
      selectedPhotos.push({
        id: n.id,
        name: n.name,
        tags: getTagsOnPhoto(n),
      });
    }
  }
  figma.ui.postMessage({ type: "selection", photos: selectedPhotos });
}

// ── Message router ───────────────────────────────────────────────────────────

figma.ui.onmessage = async function (msg) {
  try {
    if (msg.type === "scan") {
      var data = await scanLibrary();
      figma.ui.postMessage({ type: "library", data: data });
      postSelection();
    } else if (msg.type === "select-photos") {
      var nodes = [];
      for (var i = 0; i < (msg.ids || []).length; i++) {
        var n = nodeCache[msg.ids[i]];
        if (n) nodes.push(n);
      }
      figma.currentPage.selection = nodes;
      if (msg.zoom && nodes.length > 0) figma.viewport.scrollAndZoomIntoView(nodes);
    } else if (msg.type === "add-tag") {
      var rA = await addTagToPhoto(msg.photoId, msg.tag);
      if (!rA.ok) figma.notify("Could not add tag: " + (rA.reason || ""));
      else if (rA.alreadyPresent) figma.notify("Tag already on photo");
      else figma.notify("Added '" + msg.tag + "'");
      var data2 = await scanLibrary();
      figma.ui.postMessage({ type: "library", data: data2 });
      postSelection();
    } else if (msg.type === "remove-tag") {
      var rR = await removeTagFromPhoto(msg.photoId, msg.tag);
      if (!rR.ok) figma.notify("Could not remove tag: " + (rR.reason || ""));
      else figma.notify("Removed '" + msg.tag + "'");
      var data3 = await scanLibrary();
      figma.ui.postMessage({ type: "library", data: data3 });
      postSelection();
    } else if (msg.type === "copy-tags") {
      var rC = await copyTagsFromTo(msg.fromId, msg.toIds || [], !!msg.replace);
      if (!rC.ok) {
        figma.notify("Copy failed: " + (rC.reason || ""));
      } else {
        figma.notify(
          "Copied " + rC.srcTagCount + " tag(s) to " + rC.copiedTo + " photo(s)"
        );
      }
      var data4 = await scanLibrary();
      figma.ui.postMessage({ type: "library", data: data4 });
      postSelection();
    } else if (msg.type === "export-csv") {
      var csv = buildCsv();
      figma.ui.postMessage({ type: "csv", text: csv, photoCount: cachedPhotos.length });
    } else if (msg.type === "close") {
      figma.closePlugin();
    }
  } catch (e) {
    figma.ui.postMessage({ type: "error", message: e.message });
  }
};

// Forward selection changes to UI live
figma.on("selectionchange", postSelection);

// Auto-scan + initial selection on open
(async function () {
  try {
    var data = await scanLibrary();
    figma.ui.postMessage({ type: "library", data: data });
    postSelection();
  } catch (e) {
    figma.ui.postMessage({ type: "error", message: e.message });
  }
})();
