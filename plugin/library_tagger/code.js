// ADAM Library Tagger — Figma plugin
// =====================================
// Walks every photo in the user-selected source shoot frames, clones the
// user-selected template once per photo, drops the photo's image into the
// clone, and names hidden rectangles per the corresponding CSV row.
//
// Selection-based: the user picks frames in Figma and clicks "Capture" buttons
// in the plugin UI. No name-matching heuristics — too brittle.

figma.showUI(__html__, { width: 480, height: 720 });

// ── State (held in plugin memory between user actions) ───────────────────────

var capturedSourceIds = [];   // Array of node IDs for source shoot frames
var capturedTemplateId = null; // Single node ID for the template

// ── Helpers ──────────────────────────────────────────────────────────────────

function notify(msg) {
  figma.ui.postMessage({ type: "log", message: msg });
}

function err(msg) {
  figma.ui.postMessage({ type: "error", message: msg });
}

function sortVisual(nodes) {
  return nodes.slice().sort(function (a, b) {
    var yDiff = a.y - b.y;
    if (Math.abs(yDiff) > 20) return yDiff;
    return a.x - b.x;
  });
}

// Minimum dimension (in px) for a node to be considered a photo, not a tag marker.
var MIN_PHOTO_DIM = 100;

function getPhotoNodes(parentNode) {
  if (!parentNode) return [];

  // If the selected node itself is image-bearing and large, treat IT as the photo
  if (isPhotoNode(parentNode)) {
    return [parentNode];
  }

  // Otherwise walk children recursively
  if (!("children" in parentNode)) return [];

  var photos = [];
  walkChildren(parentNode, function (n) {
    if (isPhotoNode(n)) photos.push(n);
  });
  return sortVisual(photos);
}

function isPhotoNode(n) {
  if (!n) return false;
  if (!("fills" in n) || !Array.isArray(n.fills)) return false;
  // Has an image fill
  var hasImageFill = false;
  for (var j = 0; j < n.fills.length; j++) {
    if (n.fills[j].type === "IMAGE") {
      hasImageFill = true;
      break;
    }
  }
  if (!hasImageFill) return false;
  // And is reasonably sized — filters out tiny tag-marker rectangles
  if ("width" in n && n.width < MIN_PHOTO_DIM) return false;
  if ("height" in n && n.height < MIN_PHOTO_DIM) return false;
  return true;
}

function parseCSV(text) {
  var lines = text.split(/\r?\n/).filter(function (l) {
    return l.trim().length > 0;
  });
  if (lines.length < 2) throw new Error("CSV has no data rows.");

  var headers = parseCSVLine(lines[0]);
  var rows = [];
  for (var i = 1; i < lines.length; i++) {
    var cells = parseCSVLine(lines[i]);
    var row = {};
    for (var k = 0; k < headers.length; k++) {
      row[headers[k].trim()] = (cells[k] || "").trim();
    }
    rows.push(row);
  }
  return { headers: headers, rows: rows };
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

// Tag columns to write as hidden rectangles. Excludes photo_name, description, node_id.
var TAG_COLUMNS = [
  "people",
  "demographic",
  "age",
  "device",
  "location",
  "color_palette",
  "style_fit",
  "activity",
  "rights",
];

// Full CSV column order for export
var CSV_COLUMNS = [
  "node_id",
  "photo_name",
  "description",
  "people",
  "demographic",
  "age",
  "device",
  "location",
  "color_palette",
  "style_fit",
  "activity",
  "rights",
];

// CSV-encode a single value (wrap in quotes if it contains comma/quote/newline)
function csvEscape(v) {
  if (v === null || v === undefined) return "";
  var s = String(v);
  if (s.indexOf(",") >= 0 || s.indexOf('"') >= 0 || s.indexOf("\n") >= 0) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function splitTagValues(cellValue) {
  if (!cellValue) return [];
  return cellValue
    .split(",")
    .map(function (v) {
      return v.trim();
    })
    .filter(function (v) {
      return v.length > 0;
    });
}

function walkChildren(node, cb) {
  if (!("children" in node)) return;
  for (var i = 0; i < node.children.length; i++) {
    var child = node.children[i];
    cb(child);
    walkChildren(child, cb);
  }
}

// ── Capture handlers ─────────────────────────────────────────────────────────

function captureSources() {
  var sel = figma.currentPage.selection;
  if (sel.length === 0) {
    err("Nothing selected. Select your source shoot frames in Figma, then click Capture again.");
    return;
  }
  capturedSourceIds = [];
  var summary = [];
  // Sort by visual position so the order is predictable
  var sortedSel = sortVisual(sel.slice());
  for (var i = 0; i < sortedSel.length; i++) {
    var node = sortedSel[i];
    capturedSourceIds.push(node.id);
    var photoCount = getPhotoNodes(node).length;
    summary.push("  " + (i + 1) + ". " + node.name + " (" + node.type + ") — " + photoCount + " photo(s)");
  }
  notify("Captured " + capturedSourceIds.length + " source frame(s):");
  for (var k = 0; k < summary.length; k++) notify(summary[k]);

  figma.ui.postMessage({ type: "sources-captured", count: capturedSourceIds.length });
}

function captureTemplate() {
  var sel = figma.currentPage.selection;
  if (sel.length === 0) {
    err("Nothing selected. Select the template frame in Figma, then click Capture again.");
    return;
  }
  if (sel.length > 1) {
    err("Multiple items selected. Select exactly one template frame.");
    return;
  }
  var t = sel[0];

  // If user selected a rectangle/instance that has a parent frame/component,
  // auto-climb to the parent. This is the common "I clicked into the template" case.
  if (t.type !== "FRAME" && t.type !== "COMPONENT" && t.type !== "INSTANCE") {
    if (t.parent && (t.parent.type === "FRAME" || t.parent.type === "COMPONENT" || t.parent.type === "INSTANCE")) {
      notify("Selected node was a " + t.type + ". Climbing to parent: " + t.parent.name + " (" + t.parent.type + ")");
      t = t.parent;
    } else {
      err("Template must be a FRAME, COMPONENT, or INSTANCE — you selected a " + sel[0].type + " whose parent isn't a container. Click directly on the template's parent frame in the layer panel.");
      return;
    }
  }

  capturedTemplateId = t.id;
  notify("Template captured: " + t.name + " (" + t.type + ")");

  // Inspect template — find image layers and hidden tag candidates
  var imageLayers = 0;
  var hiddenTagNodes = 0;
  var directChildren = ("children" in t) ? t.children.length : 0;

  walkChildren(t, function (n) {
    if ("fills" in n && Array.isArray(n.fills)) {
      for (var i = 0; i < n.fills.length; i++) {
        if (n.fills[i].type === "IMAGE") {
          imageLayers++;
          break;
        }
      }
    }
    // Hidden node of any tag-eligible type
    if (n.visible === false && (n.type === "RECTANGLE" || n.type === "FRAME" || n.type === "INSTANCE" || n.type === "COMPONENT" || n.type === "ELLIPSE")) {
      hiddenTagNodes++;
    }
  });

  notify("  Template direct children: " + directChildren);
  notify("  Image-bearing layers (any depth): " + imageLayers);
  notify("  Hidden tag-eligible nodes (any depth): " + hiddenTagNodes);

  if (imageLayers === 0) {
    notify("  WARNING: Template has no image-bearing layer. Photos can't be placed.");
  }
  if (hiddenTagNodes === 0) {
    notify("  WARNING: Template has no hidden tag-eligible nodes. Tags will be created from scratch.");
  }

  figma.ui.postMessage({ type: "template-captured" });
}

// ── Export PNGs ──────────────────────────────────────────────────────────────

async function exportPNGs(payload) {
  await figma.loadAllPagesAsync();

  if (capturedSourceIds.length === 0) {
    err("Capture source frames first (Step 1).");
    return;
  }

  // Build ordered photo list
  var allPhotos = [];
  for (var i = 0; i < capturedSourceIds.length; i++) {
    var src = await figma.getNodeByIdAsync(capturedSourceIds[i]);
    if (!src) continue;
    var photos = getPhotoNodes(src);
    for (var p = 0; p < photos.length; p++) {
      allPhotos.push(photos[p]);
    }
  }

  notify("Exporting " + allPhotos.length + " PNG(s) at 0.5x scale...");
  notify("Browser will prompt about multiple downloads — click Allow.");

  var success = 0;
  var failed = 0;

  for (var idx = 0; idx < allPhotos.length; idx++) {
    var photo = allPhotos[idx];
    try {
      var bytes = await photo.exportAsync({
        format: "PNG",
        constraint: { type: "SCALE", value: 0.5 },
      });

      // Convert Uint8Array to plain number array for postMessage transfer
      var byteArray = [];
      for (var b = 0; b < bytes.length; b++) {
        byteArray.push(bytes[b]);
      }

      // Build filename: zero-padded sequence + sanitized node_id + photo name
      var seq = String(idx + 1);
      while (seq.length < 3) seq = "0" + seq;
      var nodeIdSafe = photo.id.replace(/:/g, "-");
      var photoNameSafe = (photo.name || "photo").replace(/[^a-zA-Z0-9_-]/g, "_");
      var filename = seq + "_" + nodeIdSafe + "__" + photoNameSafe + ".png";

      figma.ui.postMessage({
        type: "png-data",
        index: idx,
        total: allPhotos.length,
        filename: filename,
        bytes: byteArray,
      });
      success++;

      // Yield between exports
      await new Promise(function (r) { setTimeout(r, 50); });
    } catch (e) {
      failed++;
      notify("✗ Photo " + (idx + 1) + " failed: " + e.message);
    }
  }

  notify("PNG export complete. Sent: " + success + ", Failed: " + failed);
  figma.ui.postMessage({ type: "png-export-complete", count: success });
}

// ── Export ───────────────────────────────────────────────────────────────────

async function exportCSV(payload) {
  await figma.loadAllPagesAsync();

  if (capturedSourceIds.length === 0) {
    err("Capture source frames first (Step 1).");
    return;
  }

  // If a seed CSV was provided, parse it for pre-population (matches by position)
  var seedRows = [];
  if (payload && payload.seedCsv) {
    try {
      seedRows = parseCSV(payload.seedCsv).rows;
      notify("Seed CSV provided: " + seedRows.length + " rows for pre-population");
    } catch (e) {
      notify("Seed CSV parse failed (continuing without): " + e.message);
    }
  }

  // Build ordered photo list from captured sources
  var allPhotos = [];
  for (var i = 0; i < capturedSourceIds.length; i++) {
    var src = await figma.getNodeByIdAsync(capturedSourceIds[i]);
    if (!src) continue;
    var photos = getPhotoNodes(src);
    for (var p = 0; p < photos.length; p++) {
      allPhotos.push({ photo: photos[p], shootIndex: i });
    }
  }

  notify("Exporting " + allPhotos.length + " photo(s)...");

  // Build CSV
  var lines = [];
  lines.push(CSV_COLUMNS.join(","));

  for (var idx = 0; idx < allPhotos.length; idx++) {
    var entry = allPhotos[idx];
    var photoNode = entry.photo;
    var seed = seedRows[idx] || {};
    var row = {
      node_id: photoNode.id,
      photo_name: seed.photo_name || photoNode.name || ("photo_" + (idx + 1)),
      description: seed.description || "",
      people: seed.people || "",
      demographic: seed.demographic || "",
      age: seed.age || "",
      device: seed.device || "",
      location: seed.location || "",
      color_palette: seed.color_palette || "",
      style_fit: seed.style_fit || "",
      activity: seed.activity || "",
      rights: seed.rights || "",
    };

    var values = [];
    for (var c = 0; c < CSV_COLUMNS.length; c++) {
      values.push(csvEscape(row[CSV_COLUMNS[c]]));
    }
    lines.push(values.join(","));
  }

  var csvText = lines.join("\n");
  notify("Export complete. " + allPhotos.length + " rows generated.");
  if (seedRows.length > 0) {
    var preFilled = Math.min(seedRows.length, allPhotos.length);
    notify("Pre-populated tag values for the first " + preFilled + " row(s) from seed CSV.");
    if (allPhotos.length > seedRows.length) {
      notify("The last " + (allPhotos.length - seedRows.length) + " row(s) have empty tag columns — fill those in.");
    }
  }

  figma.ui.postMessage({ type: "export-ready", csvText: csvText });
}

// ── Scan ─────────────────────────────────────────────────────────────────────

async function scan(payload) {
  await figma.loadAllPagesAsync();

  if (capturedSourceIds.length === 0) {
    err("Capture source shoot frames first (Step 1).");
    return;
  }
  if (!capturedTemplateId) {
    err("Capture the template frame first (Step 2).");
    return;
  }

  var csvText = payload.csv;
  var parsed;
  try {
    parsed = parseCSV(csvText);
  } catch (e) {
    err("CSV parse failed: " + e.message);
    return;
  }

  notify("CSV parsed: " + parsed.rows.length + " rows");

  var totalPhotos = 0;
  for (var i = 0; i < capturedSourceIds.length; i++) {
    var node = await figma.getNodeByIdAsync(capturedSourceIds[i]);
    if (!node) {
      notify("Source #" + (i + 1) + ": NODE NOT FOUND (was it deleted?)");
      continue;
    }
    var photos = getPhotoNodes(node);
    totalPhotos += photos.length;
    notify("Source #" + (i + 1) + " (" + node.name + "): " + photos.length + " photos");
  }

  notify("Total source photos: " + totalPhotos);
  notify("CSV rows: " + parsed.rows.length);

  if (totalPhotos !== parsed.rows.length) {
    var diff = Math.abs(totalPhotos - parsed.rows.length);
    var which = totalPhotos > parsed.rows.length ? "extra photo(s)" : "extra CSV row(s)";
    notify("WARNING: Mismatch — " + diff + " " + which + ". Generate will process the smaller of the two.");
  }

  // Inspect template
  var template = await figma.getNodeByIdAsync(capturedTemplateId);
  if (!template) {
    err("Template not found (was it deleted?). Re-capture template.");
    return;
  }
  notify("Template: " + template.name);

  figma.ui.postMessage({ type: "scan-complete" });
}

// ── Generate ─────────────────────────────────────────────────────────────────

async function generate(payload) {
  await figma.loadAllPagesAsync();

  if (capturedSourceIds.length === 0) {
    err("Capture source shoot frames first.");
    return;
  }
  if (!capturedTemplateId) {
    err("Capture the template frame first.");
    return;
  }

  var csvText = payload.csv;
  var parsed;
  try {
    parsed = parseCSV(csvText);
  } catch (e) {
    err("CSV parse failed: " + e.message);
    return;
  }

  var template = await figma.getNodeByIdAsync(capturedTemplateId);
  if (!template) {
    err("Template not found. Re-capture and try again.");
    return;
  }

  // Build ordered photo list across all captured sources, indexed by node_id
  var allPhotos = [];
  var photoById = {};
  for (var i = 0; i < capturedSourceIds.length; i++) {
    var src = await figma.getNodeByIdAsync(capturedSourceIds[i]);
    if (!src) continue;
    var photos = getPhotoNodes(src);
    for (var p = 0; p < photos.length; p++) {
      allPhotos.push({ photo: photos[p], shootIndex: i });
      photoById[photos[p].id] = { photo: photos[p], shootIndex: i };
    }
  }

  notify("Found " + allPhotos.length + " source photos.");
  notify("CSV has " + parsed.rows.length + " rows.");

  // Detect match mode: by node_id (preferred) or by position (legacy fallback)
  var firstRow = parsed.rows[0] || {};
  var matchByNodeId = !!firstRow.node_id;
  notify("Match mode: " + (matchByNodeId ? "by node_id (stable)" : "by position (legacy)"));

  var limit = matchByNodeId ? parsed.rows.length : Math.min(allPhotos.length, parsed.rows.length);
  notify("Processing " + limit + " row(s)...");

  // Output parent — single frame to the right of the template
  var outputParent = figma.currentPage.findOne(function (n) {
    return n.type === "FRAME" && n.name === "Tagged Library Output";
  });
  if (!outputParent) {
    outputParent = figma.createFrame();
    outputParent.name = "Tagged Library Output";
    outputParent.layoutMode = "VERTICAL";
    outputParent.primaryAxisSizingMode = "AUTO";
    outputParent.counterAxisSizingMode = "AUTO";
    outputParent.paddingTop = 40;
    outputParent.paddingBottom = 40;
    outputParent.paddingLeft = 40;
    outputParent.paddingRight = 40;
    outputParent.itemSpacing = 24;
    outputParent.fills = [{ type: "SOLID", color: { r: 0.95, g: 0.95, b: 0.95 } }];
    outputParent.x = template.x + template.width + 200;
    outputParent.y = template.y;
  }

  var shootGroups = {};
  var success = 0;
  var failed = 0;
  var failures = [];

  for (var idx = 0; idx < limit; idx++) {
    var row = parsed.rows[idx];
    var photoName = (row.photo_name || ("photo_" + (idx + 1))).trim();

    // Resolve the source photo for this row
    var entry = null;
    if (matchByNodeId) {
      entry = photoById[row.node_id];
      if (!entry) {
        failed++;
        failures.push({ photo_name: photoName, error: "node_id not found: " + row.node_id });
        notify("✗ " + photoName + ": node_id not found in current selection");
        continue;
      }
    } else {
      if (idx >= allPhotos.length) break;
      entry = allPhotos[idx];
    }

    var shootKey = "Shoot " + (entry.shootIndex + 1);

    try {
      var clone = template.clone();
      clone.name = photoName;
      replaceImageInClone(clone, entry.photo);
      applyTagsToClone(clone, row);

      if (!shootGroups[shootKey]) {
        var groupFrame = figma.createFrame();
        groupFrame.name = shootKey;
        groupFrame.layoutMode = "HORIZONTAL";
        groupFrame.layoutWrap = "WRAP";
        groupFrame.primaryAxisSizingMode = "FIXED";
        groupFrame.counterAxisSizingMode = "AUTO";
        groupFrame.resizeWithoutConstraints(1200, 100);
        groupFrame.paddingTop = 16;
        groupFrame.paddingBottom = 16;
        groupFrame.paddingLeft = 16;
        groupFrame.paddingRight = 16;
        groupFrame.itemSpacing = 16;
        groupFrame.counterAxisSpacing = 16;
        groupFrame.fills = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
        outputParent.appendChild(groupFrame);
        shootGroups[shootKey] = groupFrame;
      }

      shootGroups[shootKey].appendChild(clone);
      success++;
    } catch (e) {
      failed++;
      failures.push({ photo_name: photoName, error: e.message });
      notify("✗ " + photoName + ": " + e.message);
    }

    if ((idx + 1) % 10 === 0) {
      notify("Progress: " + (idx + 1) + "/" + limit);
      await new Promise(function (r) { setTimeout(r, 0); });
    }
  }

  notify("✓ Done. Created: " + success + ", Failed: " + failed);
  if (failures.length > 0) {
    notify("Failures:");
    for (var f = 0; f < failures.length; f++) {
      notify("  - " + failures[f].photo_name + ": " + failures[f].error);
    }
  }

  figma.ui.postMessage({ type: "generate-complete" });
}

function replaceImageInClone(clone, sourcePhoto) {
  var candidates = [];
  walkChildren(clone, function (n) {
    if ("fills" in n && Array.isArray(n.fills)) {
      for (var i = 0; i < n.fills.length; i++) {
        if (n.fills[i].type === "IMAGE") {
          candidates.push(n);
          break;
        }
      }
    }
  });

  if (candidates.length === 0) {
    throw new Error("Template has no image-bearing layer to replace");
  }

  var sourceFills = sourcePhoto.fills;
  if (!Array.isArray(sourceFills)) {
    throw new Error("Source photo has no fills");
  }
  var sourceImageFill = null;
  for (var s = 0; s < sourceFills.length; s++) {
    if (sourceFills[s].type === "IMAGE") {
      sourceImageFill = sourceFills[s];
      break;
    }
  }
  if (!sourceImageFill) {
    throw new Error("Source photo has no image fill");
  }

  var target = candidates[0];
  var newFills = target.fills.map(function (f) {
    if (f.type === "IMAGE") {
      var copy = Object.assign({}, sourceImageFill);
      copy.scaleMode = f.scaleMode || sourceImageFill.scaleMode;
      return copy;
    }
    return f;
  });
  target.fills = newFills;
}

function applyTagsToClone(clone, csvRow) {
  // Collect all hidden tag-eligible nodes (rectangles, frames, instances, etc.)
  // — Brandon may have built tags as any hidden node type.
  var existingTagNodes = [];
  walkChildren(clone, function (n) {
    if (
      n.visible === false &&
      (n.type === "RECTANGLE" ||
        n.type === "FRAME" ||
        n.type === "INSTANCE" ||
        n.type === "COMPONENT" ||
        n.type === "ELLIPSE")
    ) {
      existingTagNodes.push(n);
    }
  });

  var tagValuesToApply = [];
  for (var c = 0; c < TAG_COLUMNS.length; c++) {
    var values = splitTagValues(csvRow[TAG_COLUMNS[c]]);
    for (var v = 0; v < values.length; v++) {
      tagValuesToApply.push(values[v]);
    }
  }

  var tagParent = clone;
  if (existingTagNodes.length > 0 && existingTagNodes[0].parent) {
    tagParent = existingTagNodes[0].parent;
  }

  var used = 0;
  for (var t = 0; t < tagValuesToApply.length; t++) {
    if (used < existingTagNodes.length) {
      existingTagNodes[used].name = tagValuesToApply[t];
      existingTagNodes[used].visible = false;
      used++;
    } else {
      // Create a new hidden rectangle for the extra tag
      var r = figma.createRectangle();
      r.name = tagValuesToApply[t];
      r.visible = false;
      r.resize(1, 1);
      tagParent.appendChild(r);
    }
  }

  // Remove any leftover existing tag nodes that didn't get a value assigned
  for (var rem = used; rem < existingTagNodes.length; rem++) {
    existingTagNodes[rem].remove();
  }
}

// ── Message router ───────────────────────────────────────────────────────────

figma.ui.onmessage = async function (msg) {
  if (msg.type === "capture-sources") {
    captureSources();
  } else if (msg.type === "capture-template") {
    captureTemplate();
  } else if (msg.type === "scan") {
    await scan(msg);
  } else if (msg.type === "generate") {
    await generate(msg);
  } else if (msg.type === "export") {
    await exportCSV(msg);
  } else if (msg.type === "export-pngs") {
    await exportPNGs(msg);
  } else if (msg.type === "close") {
    figma.closePlugin();
  }
};
