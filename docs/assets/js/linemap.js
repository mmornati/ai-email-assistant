// The line map: draws one run of the demo as a metro diagram and plays the messages along their lines.
// Rules branch off above the trunk, the model's answers branch off below it, and the trunk ends in red
// at the mail that waits for a person. Data: docs/assets/demo/run.json (demo/run_demo.py, real engine).

export const TAG_ORDER = ["Alerts", "GitHub-Admin", "Meeting/Invite", "Shares", "Admin", "Internal-Comms", "Promo",
  "Meeting/Notes", "Newsletter", "FYI", "Action", "Backlog"];
export const DARK_TEXT = new Set(["Newsletter", "Meeting/Notes", "Alerts", "Backlog", "Promo"]);
export const lineVar = (tag) => `var(--l-${tag.toLowerCase().replace(/\//g, "-")})`;

const NS = "http://www.w3.org/2000/svg";
const el = (name, attrs = {}, parent) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
};

/** Counts that cross-check: every message in the window is routed by rules or read by the model; some wait for you. */
export function tally(snap, stepName = "apply") {
  const step = snap.steps.find((s) => s.name === stepName);
  const routes = snap.routes;
  const inWindow = step.mailbox.filter((m) => routes[m.id] !== "outside");
  const branch = { rule: {}, model: {} };
  for (const m of inWindow) {
    const side = routes[m.id] === "rule" ? "rule" : "model";
    for (const t of m.tags) {
      branch[side][t] ??= { total: 0, archived: 0 };
      branch[side][t].total++;
      if (!m.inbox) branch[side][t].archived++;
    }
  }
  const byTag = {};
  for (const side of ["rule", "model"]) {
    for (const [t, c] of Object.entries(branch[side])) {
      byTag[t] ??= { total: 0, rule: 0, model: 0, archived: 0 };
      byTag[t].total += c.total;
      byTag[t][side] += c.total;
      byTag[t].archived += c.archived;
    }
  }
  const preview = snap.steps.find((s) => s.name === "preview");
  return {
    arrived: inWindow.length,
    rules: inWindow.filter((m) => routes[m.id] === "rule").length,
    model: inWindow.filter((m) => routes[m.id] !== "rule").length,
    escalated: inWindow.filter((m) => ["escalated", "waiting"].includes(routes[m.id])).length,
    waiting: inWindow.filter((m) => routes[m.id] === "waiting").length,
    calls: preview.model_calls.length,
    tasks: step.tasks.length,
    archived: inWindow.filter((m) => !m.inbox).length,
    branch, byTag,
  };
}

// "full" fills its box; "hero" leaves the upper-left free for the station sign that stands on the Inbox.
const LAYOUTS = {
  full: { W: 1220, TRUNK: 330, top: 40, X: { inbox: 60, rules: 270, classify: 610, validate: 830, end: 1010 } },
  hero: { W: 1220, TRUNK: 470, top: 150, X: { inbox: 70, rules: 560, classify: 720, validate: 880, end: 1030 }, hero: true },
};
const GAP = 26, BELOW = 54;

function geometry(name, ruleTags, modelTags) {
  const L = LAYOUTS[name];
  const g = { ...L, SPUR: L.TRUNK - 44, up: {}, down: {} };
  ruleTags.forEach((t, i) => { g.up[t] = L.top + i * GAP; });
  modelTags.forEach((t, i) => { g.down[t] = L.TRUNK + BELOW + i * (GAP + 2); });
  g.H = L.TRUNK + BELOW + Math.max(0, modelTags.length - 1) * (GAP + 2) + 30;
  return g;
}

function route(g, kind, tag) {
  const { X, TRUNK, SPUR } = g;
  const start = [[X.inbox, TRUNK], [X.rules, TRUNK]];
  if (kind === "rule") return [...start, [X.rules, g.up[tag]], [X.end, g.up[tag]]];
  const mid = kind === "model"
    ? [[X.classify, TRUNK], [X.validate, TRUNK]]
    : [[X.classify, TRUNK], [X.classify + 40, SPUR], [X.validate - 40, SPUR], [X.validate, TRUNK]];
  if (kind === "waiting") return [...start, ...mid, [X.end, TRUNK]];
  return [...start, ...mid, [X.validate, g.down[tag]], [X.end, g.down[tag]]];
}

const pathD = (pts) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ");
const lengthOf = (pts) => pts.slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]), 0);
function pointAt(pts, d) {
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
    const len = Math.hypot(x1 - x0, y1 - y0);
    if (d <= len) return [x0 + (x1 - x0) * (d / len), y0 + (y1 - y0) * (d / len)];
    d -= len;
  }
  return pts[pts.length - 1];
}

export function drawLineMap(svg, snap, { label = "Line map of the demo run", layout = "full" } = {}) {
  const t = tally(snap);
  const ruleTags = TAG_ORDER.filter((x) => t.branch.rule[x]);
  const modelTags = TAG_ORDER.filter((x) => t.branch.model[x]);
  const g = geometry(layout, ruleTags, modelTags);
  const { X, TRUNK, SPUR, W, H } = g;

  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${label}: ${t.arrived} messages arrived, ${t.rules} routed by rules, ` +
    `${t.model} read by the model in ${t.calls} calls, ${t.waiting} left waiting for you.`);
  svg.classList.add("linemap");
  svg.replaceChildren();

  const lines = el("g", {}, svg);
  const stroke = (pts, color, width = 8, parent = lines) =>
    el("path", { class: "ln", d: pathD(pts), stroke: color, "stroke-width": width }, parent);
  if (g.hero) stroke([[X.inbox, 60], [X.inbox, TRUNK]], "var(--l-trunk)", 8); // the sign's post
  for (const tag of ruleTags) stroke([[X.rules, g.up[tag]], [X.end, g.up[tag]]], lineVar(tag));
  for (const tag of modelTags) stroke([[X.validate, g.down[tag]], [X.end, g.down[tag]]], lineVar(tag));
  stroke([[X.inbox, TRUNK], [X.validate, TRUNK]], "var(--l-trunk)", 10);
  stroke([[X.validate, TRUNK], [X.end, TRUNK]], "var(--signal)", 10);
  // the express spur to the stronger model: a hollow line, dark when nothing escalates
  const spur = el("g", { class: t.escalated ? "" : "spur-off" }, lines);
  const spurPts = [[X.classify, TRUNK], [X.classify + 40, SPUR], [X.validate - 40, SPUR], [X.validate, TRUNK]];
  stroke(spurPts, "var(--l-trunk)", 10, spur);
  stroke(spurPts, "var(--l-hollow)", 4, spur);

  const st = el("g", {}, svg);
  const pill = (x, y0, y1) => el("rect", { class: "st", x: x - 13, y: y0 - 13, width: 26, height: y1 - y0 + 26, rx: 13, "stroke-width": 4 }, st);
  pill(X.rules, g.up[ruleTags[0]], TRUNK);
  pill(X.validate, TRUNK, modelTags.length ? g.down[modelTags.at(-1)] : TRUNK);
  el("circle", { class: "st", cx: X.classify, cy: TRUNK, r: 11, "stroke-width": 4 }, st);
  el("circle", { class: "st", cx: (X.classify + X.validate) / 2, cy: SPUR, r: 9, "stroke-width": 4 }, st);
  el("circle", { cx: X.inbox, cy: TRUNK, r: 22, fill: "var(--l-trunk)" }, st);
  el("circle", { cx: X.inbox, cy: TRUNK, r: 10, fill: "var(--enamel)" }, st);

  const text = (x, y, s, cls, anchor = "start") => {
    const n = el("text", { x, y, class: cls, "text-anchor": anchor }, svg);
    n.textContent = s;
    return n;
  };
  text(X.inbox + 34, TRUNK + 40, "Inbox", "lbl");
  text(X.inbox + 34, TRUNK + 60, `${t.arrived} in the window`, "lbl-s");
  const ry = g.hero ? TRUNK + 40 : TRUNK - 40;
  text(X.rules - 26, ry, "Rules", "lbl", "end");
  text(X.rules - 26, ry + 20, "plain code · no model", "lbl-s", "end");
  text(X.classify, TRUNK + 40, "First pass", "lbl", "middle");
  text(X.classify, TRUNK + 60, snap.classifier.cheap_model, "lbl-s", "middle");
  text((X.classify + X.validate) / 2, SPUR - 18, `Escalation · ${snap.classifier.escalation_model}`, "lbl-s", "middle");
  text(X.rules + 26, g.up[ruleTags[0]] - 24, `Routed by rules · ${t.rules}`, "lbl-s", "start");
  if (modelTags.length) text(X.validate + 26, TRUNK + 34, `Read by a model · ${t.model - t.waiting}`, "lbl-s", "start");
  text(X.validate - 26, TRUNK + 96, "Validate", "lbl", "end");
  text(X.validate - 26, TRUNK + 116, "code checks the model", "lbl-s", "end");

  const counters = {};
  const terminal = (key, y, color, name, total, archived) => {
    el("circle", { cx: X.end, cy: y, r: 9, fill: "var(--enamel)", stroke: color, "stroke-width": 5 }, st);
    text(X.end + 24, y + 6, name, "lbl");
    if (archived) text(X.end - 16, y - 8, `${archived} archived`, "lbl-s lbl-xs", "end");
    const n = text(W - 6, y + 6, "0", "num", "end");
    counters[key] = { node: n, total, now: 0 };
  };
  for (const tag of ruleTags) {
    const c = t.branch.rule[tag];
    terminal(`rule:${tag}`, g.up[tag], lineVar(tag), tag, c.total, c.archived);
  }
  for (const tag of modelTags) {
    const c = t.branch.model[tag];
    terminal(`model:${tag}`, g.down[tag], lineVar(tag), tag, c.total, c.archived);
  }
  terminal("waiting", TRUNK, "var(--signal)", "Waiting for you", t.waiting, 0);
  counters.waiting.node.setAttribute("fill", "var(--signal)");

  const trips = snap.steps.find((s) => s.name === "apply").mailbox
    .filter((m) => snap.routes[m.id] !== "outside")
    .sort((a, b) => b.hours - a.hours)
    .map((m, i) => {
      const kind = snap.routes[m.id];
      const pts = route(g, kind, m.tags[0]);
      const key = kind === "waiting" ? "waiting" : `${kind === "rule" ? "rule" : "model"}:${m.tags[0]}`;
      return { pts, len: lengthOf(pts), delay: i * 140, key, signal: kind === "waiting" || m.tags[0] === "Action" };
    });
  const dots = el("g", { "aria-hidden": "true" }, svg);
  let raf = 0;

  function settle() {
    cancelAnimationFrame(raf);
    dots.replaceChildren();
    for (const c of Object.values(counters)) { c.now = c.total; c.node.textContent = c.total; }
  }

  function play() {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return settle();
    cancelAnimationFrame(raf);
    dots.replaceChildren();
    for (const c of Object.values(counters)) { c.now = 0; c.node.textContent = "0"; }
    const live = trips.map((trip) => ({ ...trip, node: null, done: false }));
    const speed = 0.62; // px per ms
    const t0 = performance.now();
    const frame = (now) => {
      let running = false;
      for (const trip of live) {
        if (trip.done) continue;
        running = true;
        const d = (now - t0 - trip.delay) * speed;
        if (d < 0) continue;
        if (!trip.node) trip.node = el("circle", { r: 6.5, class: trip.signal ? "dot is-signal" : "dot" }, dots);
        if (d >= trip.len) {
          trip.done = true;
          trip.node.remove();
          const c = counters[trip.key];
          c.now++;
          c.node.textContent = c.now;
          continue;
        }
        const [x, y] = pointAt(trip.pts, d);
        trip.node.setAttribute("cx", x.toFixed(1));
        trip.node.setAttribute("cy", y.toFixed(1));
      }
      if (running) raf = requestAnimationFrame(frame);
      else settle();
    };
    raf = requestAnimationFrame(frame);
  }

  settle();
  return { play, settle, tally: t, geometry: g };
}
