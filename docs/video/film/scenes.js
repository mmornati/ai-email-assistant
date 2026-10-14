/* The AI Mail Assistant film: one morning of the demo mailbox, drawn as a metro line map.
 * Every scene is a pure function of t; animations hook onto the spoken sentences (cues).
 * The mail below is the demo run of the real engine on an invented mailbox (docs/assets/demo/run.json):
 * [from, subject, route r=rules m=model e=escalated w=waiting, tag, archived]. Regenerate it if the demo changes. */
"use strict";

const MAIL = [["Calendar", "Invitation: Pricing review @ Wed 10:00", "r", "Meeting/Invite", 0], ["Priya Nair", "Q4 hiring plan: need your sign-off by Thursday", "m", "Action", 0], ["Code Review", "[harbor/api] Review requested: Rate-limit the export endpo", "r", "GitHub-Admin", 0], ["Status", "[RESOLVED] api p95 latency above 800 ms", "r", "Alerts", 1], ["Calendar", "Updated invitation: 1:1 Sam / Léa @ Thu 15:00", "r", "Meeting/Invite", 0], ["Status", "[FIRING] api p95 latency above 800 ms", "r", "Alerts", 0], ["Summit Events", "Webinar: shipping AI features safely (Oct 28)", "m", "Newsletter", 0], ["Deals", "48h only: 30% off everything", "r", "Promo", 1], ["Jonas Weber", "Re: renewal", "e", "Action", 0], ["Code Review", "[harbor/api] CI failed on main", "r", "GitHub-Admin", 0], ["Léa Dubois", "Onboarding deck for Monday", "m", "Action", 0], ["Docs", "Priya Nair shared \"Q4 Plan\" with you", "r", "Shares", 0], ["Tom Okafor", "quick one", "e", "Action", 0], ["Harbor All-Hands", "This week at Harbor: offsite dates, new parental leave pol", "r", "Internal-Comms", 0], ["Marta Silva", "Notes from the vendor call", "m", "Meeting/Notes", 0], ["Travel desk", "Your receipt: train to Lyon", "r", "Admin", 0], ["The Weekly Byte", "The Weekly Byte #212: smaller models, bigger wins", "r", "Newsletter", 0], ["Calendar", "Accepted: Launch retro @ Fri 11:00", "r", "Meeting/Invite", 0], ["Meeting Notes", "Summary: Weekly product sync", "r", "Meeting/Notes", 0], ["Ana Costa", "Friday?", "w", "", 0], ["Daniel Kim", "Moved the launch retro to the 3rd floor", "m", "FYI", 0], ["Docs", "Léa Dubois commented on \"Onboarding deck\"", "r", "Shares", 0], ["Deals", "Your cart misses you", "r", "Promo", 1], ["Code Review", "[harbor/web] Merged: New pricing page (#311)", "r", "GitHub-Admin", 1], ["Summit Events", "Last seats: the platform engineering roundtable", "m", "Newsletter", 1], ["Code Review", "[harbor/api] Dependabot: bump urllib3", "r", "GitHub-Admin", 1], ["Cloud Billing", "Invoice for September is available", "r", "Admin", 0], ["Product Notes", "Product Notes: onboarding teardown", "r", "Newsletter", 1], ["Calendar", "Invitation: Quarterly planning @ Mon 09:30", "r", "Meeting/Invite", 0], ["Payroll", "Your October payslip is available", "r", "Admin", 0], ["Summit Events", "Your weekly events digest", "m", "Newsletter", 1], ["Deals", "New arrivals picked for you", "r", "Promo", 1], ["Code Review", "[harbor/infra] Issue closed: flaky deploy step", "r", "GitHub-Admin", 1], ["Harbor All-Hands", "Office closed on the 1st", "r", "Internal-Comms", 0], ["Status", "Certificate for status.harbor.example expires in 14 days", "r", "Alerts", 0], ["Design Systems Weekly", "Tokens, themes and dark mode", "r", "Newsletter", 1], ["The Weekly Byte", "The Weekly Byte #211: the evaluation issue", "r", "Newsletter", 0]];
const TASKS = [["Approve the Q4 hiring plan (two senior roles)", "2026-10-16"], ["Confirm the revised renewal terms to Jonas (clause 7)", "2026-10-20"], ["Review the onboarding deck (slides 4-9) before Monday", "2026-10-19"], ["Tell Tom whether the Team plan includes API access", "2026-10-16"]];

const SIGN = '"Barlow Semi Condensed", "Arial Narrow", sans-serif';
const READ = '"Atkinson Hyperlegible", Inter, sans-serif';
const INK = "#121417", INK2 = "#474b51", INK3 = "#6b6f75", RULE = "#cfcabc", ENAMEL = "#f4f2ec", ENAMEL2 = "#e9e6dc", RED = "#e4002b";
const LINE = {
  "Action": "#e4002b", "Alerts": "#ff6a13", "GitHub-Admin": "#5b6770", "Meeting/Invite": "#0072ce", "Meeting/Notes": "#41b6e6",
  "Shares": "#009b8d", "Admin": "#8c5a2b", "Internal-Comms": "#7a3e9d", "Newsletter": "#ffb500", "Promo": "#e8559a", "FYI": "#00a650",
};
const DARK_TEXT = new Set(["Newsletter", "Meeting/Notes", "Alerts", "Promo"]);

const STR = {
  en: {
    clock: "08:00", unread: "new", overnight: "arrived this week", inbox: "Inbox",
    rules: "Rules", rulesSub: "plain code · no model", routed: "routed by rules", noModel: "model calls", nothingSent: "nothing leaves your Mac",
    first: "First pass", escal: "Escalation", read: "read by a model", calls: "2 model calls · Copilot CLI or Claude Code",
    validate: "Validate", checks: ["The right messages", "Known labels only", "Tasks only where allowed", "Real dates"],
    waiting: "Waiting for you", refused: "anything else: refused",
    tasksTitle: "My Tasks", due: "Due", archived: "archived", labelled: "Every message labelled",
    clock9: "09:00", nothingNew: "nothing new to read", zero: "model calls this hour", spurDark: "the express spur stays dark",
    s1: "Dry run first", s1b: "make preview · make classify", s2: "A plan you can read", s2b: "state/plan.json", s3: "Journalled, undoable", s3b: "triage.py undo",
    name: "AI Mail Assistant", tagline: "Every message, routed.", oss: "Open source · MIT · macOS + Gmail", url: "mmornati.github.io/ai-email-assistant",
    demo: "Invented demo mailbox · real engine",
  },
  fr: {
    clock: "08:00", unread: "nouveaux", overnight: "arrivés cette semaine", inbox: "Boîte de réception",
    rules: "Règles", rulesSub: "du code · aucun modèle", routed: "aiguillés par les règles", noModel: "appel de modèle", nothingSent: "rien ne quitte votre Mac",
    first: "Premier passage", escal: "Escalade", read: "lus par un modèle", calls: "2 appels de modèle · Copilot CLI ou Claude Code",
    validate: "Validation", checks: ["Les bons messages", "Libellés connus uniquement", "Tâches seulement si permises", "Des dates réelles"],
    waiting: "En attente de vous", refused: "tout le reste : refusé",
    tasksTitle: "Mes tâches", due: "Échéance", archived: "archivés", labelled: "Chaque message a son libellé",
    clock9: "09:00", nothingNew: "rien de nouveau à lire", zero: "appel de modèle cette heure-ci", spurDark: "la voie express reste éteinte",
    s1: "D'abord une simulation", s1b: "make preview · make classify", s2: "Un plan lisible", s2b: "state/plan.json", s3: "Journalisé, réversible", s3b: "triage.py undo",
    name: "AI Mail Assistant", tagline: "Chaque message trouve sa voie.", oss: "Open source · MIT · macOS + Gmail", url: "mmornati.github.io/ai-email-assistant",
    demo: "Boîte de démo inventée · vrai moteur",
  },
};

/* ------------------------------------------------------------------ the line map */
const TRUNK = 430, X = { inbox: 110, rules: 420, classify: 640, validate: 860, end: 1000 }, SPUR = TRUNK - 46;
const RULE_TAGS = ["Alerts", "GitHub-Admin", "Meeting/Invite", "Shares", "Admin", "Internal-Comms", "Promo", "Meeting/Notes", "Newsletter"];
const MODEL_TAGS = ["Meeting/Notes", "Newsletter", "FYI", "Action"];
const UP = {}, DOWN = {};
RULE_TAGS.forEach((t, i) => { UP[t] = 150 + i * 26; });
MODEL_TAGS.forEach((t, i) => { DOWN[t] = TRUNK + 50 + i * 26; });
const count = (side, tag) => MAIL.filter((m) => (side === "r" ? m[2] === "r" : m[2] !== "r") && m[3] === tag).length;

function stroke(pts, color, lw, alpha = 1) { if (pts.length > 1) line(pts, color, lw, alpha); }
function route(m) {
  const start = [[X.inbox, TRUNK], [X.rules, TRUNK]];
  if (m[2] === "r") return [...start, [X.rules, UP[m[3]]], [X.end, UP[m[3]]]];
  const mid = m[2] === "m" ? [[X.classify, TRUNK], [X.validate, TRUNK]]
    : [[X.classify, TRUNK], [X.classify + 40, SPUR], [X.validate - 40, SPUR], [X.validate, TRUNK]];
  if (m[2] === "w") return [...start, ...mid, [X.end, TRUNK]];
  return [...start, ...mid, [X.validate, DOWN[m[3]]], [X.end, DOWN[m[3]]]];
}
function plen(pts) { let s = 0; for (let i = 1; i < pts.length; i++) s += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return s; }
function pointAt(pts, k) { const p = partial(pts, k); return p[p.length - 1] || pts[0]; }

/* o: trunk, rules, spur, model, waiting (0..1 draw-on), dimRules, dimModel, labels */
function map(o) {
  const a = o.alpha ?? 1;
  const dr = o.dimRules ?? 1, dm = o.dimModel ?? 1;
  RULE_TAGS.forEach((tag, i) => {
    const k = seg(o.rules ?? 0, i * 0.06, 0.5 + i * 0.06);
    stroke(partial([[X.rules, UP[tag]], [X.end, UP[tag]]], outCubic(k)), LINE[tag], 8, a * dr);
  });
  MODEL_TAGS.forEach((tag, i) => {
    const k = seg(o.model ?? 0, i * 0.12, 0.6 + i * 0.12);
    stroke(partial([[X.validate, DOWN[tag]], [X.end, DOWN[tag]]], outCubic(k)), LINE[tag], 8, a * dm);
  });
  stroke(partial([[X.inbox, TRUNK], [X.validate, TRUNK]], o.trunk ?? 0), INK, 10, a);
  stroke(partial([[X.validate, TRUNK], [X.end, TRUNK]], o.waiting ?? 0), RED, 10, a);
  const spur = [[X.classify, TRUNK], [X.classify + 40, SPUR], [X.validate - 40, SPUR], [X.validate, TRUNK]];
  const sk = partial(spur, o.spur ?? 0), sa = a * (o.spurAlpha ?? 1);
  stroke(sk, INK, 10, sa); stroke(sk, ENAMEL, 4, sa);
  // stations
  const pill = (x, y0, y1, k) => { if (k <= 0) return; panel(x - 13, y0 - 13, 26, y1 - y0 + 26, { r: 13, fill: ENAMEL, stroke: INK, lw: 4, alpha: a * k }); };
  pill(X.rules, UP.Alerts, TRUNK, seg(o.trunk ?? 0, 0.3, 0.5));
  if ((o.trunk ?? 0) >= 0.99) pill(X.validate, TRUNK, (o.model ?? 0) > 0 ? DOWN.Action : TRUNK, 1);
  if ((o.trunk ?? 0) > 0.7) { dot(X.classify, TRUNK, 11, ENAMEL, a); ring(X.classify, TRUNK, 11, INK, 4, a); }
  if ((o.spur ?? 0) > 0.5) { dot((X.classify + X.validate) / 2, SPUR, 9, ENAMEL, sa); ring((X.classify + X.validate) / 2, SPUR, 9, INK, 4, sa); }
  dot(X.inbox, TRUNK, 22, INK, a); dot(X.inbox, TRUNK, 10, ENAMEL, a);
  if (o.labels) {
    const L = o.labels;
    text(S.inbox, X.inbox, TRUNK + 52, { size: 19, weight: 700, font: SIGN, align: "center", alpha: a * (L.inbox ?? 0) });
    text(S.rules, X.rules - 24, TRUNK + 40, { size: 19, weight: 700, font: SIGN, align: "right", alpha: a * (L.rules ?? 0) });
    text(S.rulesSub.toUpperCase(), X.rules - 24, TRUNK + 60, { size: 12, weight: 600, font: SIGN, color: INK2, align: "right", spacing: "1px", alpha: a * (L.rules ?? 0) });
    text(S.first, X.classify, TRUNK + 42, { size: 19, weight: 700, font: SIGN, align: "center", alpha: a * (L.first ?? 0) });
    text("GPT-6-LUNA", X.classify, TRUNK + 62, { size: 12, weight: 600, font: SIGN, color: INK2, align: "center", spacing: "1px", alpha: a * (L.first ?? 0) });
    text(`${S.escal.toUpperCase()} · GPT-6.1-SOL`, (X.classify + X.validate) / 2, SPUR + 30, { size: 12, weight: 600, font: SIGN, color: INK2, align: "center", spacing: "1px", alpha: a * (L.escal ?? 0) });
    text(S.validate, X.validate - 24, TRUNK + 100, { size: 19, weight: 700, font: SIGN, align: "right", alpha: a * (L.validate ?? 0) });
  }
  if (o.terminals) {
    const T = o.terminals;
    const term = (y, color, name, n, k, red) => {
      if (k <= 0) return;
      dot(X.end, y, 9, ENAMEL, a * k); ring(X.end, y, 9, color, 5, a * k);
      text(name, X.end + 22, y + 6, { size: 17, weight: 700, font: SIGN, alpha: a * k, color: red ? RED : INK });
      text(String(n), 1200, y + 6, { size: 16, weight: 600, font: MONO, align: "right", alpha: a * k, color: red ? RED : INK });
    };
    RULE_TAGS.forEach((tag, i) => term(UP[tag], LINE[tag], tag, Math.round(count("r", tag) * (T.ruleN ?? 1)), seg(T.rules ?? 0, i * 0.05, 0.4 + i * 0.05) * dr));
    MODEL_TAGS.forEach((tag, i) => term(DOWN[tag], LINE[tag], tag, Math.round(count("m", tag) * (T.modelN ?? 1)), seg(T.model ?? 0, i * 0.1, 0.5 + i * 0.1) * dm));
    term(TRUNK, RED, S.waiting, 1, T.waiting ?? 0, true);
  }
}

/* messages travelling: each trip starts at start + i*gap, speed in px/s */
function trips(t, list, start, gap, speed = 520) {
  list.forEach((m, i) => {
    const pts = route(m), L = plen(pts);
    const k = (t - start - i * gap) * speed / L;
    if (k <= 0 || k >= 1) return;
    const [x, y] = pointAt(pts, k);
    const sig = m[2] === "w" || m[3] === "Action";
    dot(x, y, 7, sig ? RED : ENAMEL); ring(x, y, 7, sig ? RED : INK, 2.5);
  });
}

function bullet(tag, x, y, alpha = 1) {
  const s = `AI/${tag}`, w = measure(s, 12, 700, SIGN) + 16;
  panel(x, y - 11, w, 22, { r: 11, fill: LINE[tag], stroke: false, alpha });
  text(s, x + 8, y + 4.5, { size: 12, weight: 700, font: SIGN, color: DARK_TEXT.has(tag) ? INK : "#fff", alpha });
  return w;
}
function title(s, sub, k, x = 80, y = 104) {
  text(s, x, y + (1 - outCubic(k)) * 16, { size: 46, weight: 800, font: SIGN, alpha: k, spacing: "-0.5px" });
  if (sub) text(sub, x, y + 34, { size: 19, font: READ, color: INK2, alpha: k });
}

/* ------------------------------------------------------------------ scenes */
function sMorning(t, d, cues) {
  const a1 = at(cues, 1, 2), a2 = at(cues, 2, 5);
  // departure-board clock
  const kc = seg(t, 0.1, 0.6);
  panel(80, 70, 300, 132, { r: 16, fill: INK, stroke: false, alpha: kc });
  text(S.clock, 230, 168, { size: 96, weight: 800, font: SIGN, color: ENAMEL, align: "center", alpha: kc });
  const kn = outCubic(seg(t, a1, a1 + 1.8));
  text(String(Math.round(MAIL.length * kn)), 80, 330, { size: 120, weight: 800, font: SIGN, alpha: seg(t, a1, a1 + 0.3) });
  text(S.unread, 80, 372, { size: 28, weight: 700, font: SIGN, alpha: seg(t, a1, a1 + 0.3) });
  text(S.overnight, 80, 402, { size: 20, font: READ, color: INK2, alpha: seg(t, a1, a1 + 0.3) });
  // the pile: rows fall in one after another, unlabelled
  const x = 470, w = 730;
  ctx.save(); rr(x, 60, w, 560, 16); ctx.clip();
  panel(x, 60, w, 560, { r: 16, fill: "#fff", stroke: RULE, alpha: kc });
  MAIL.forEach((m, i) => {
    const k = outBack(seg(t, a1 + i * 0.05, a1 + 0.35 + i * 0.05));
    if (k <= 0) return;
    const y = 92 + i * 30 - (1 - k) * 30;
    if (y > 620) return;
    dot(x + 22, y - 5, 4.5, "#0072ce", k);
    text(m[0], x + 40, y, { size: 15, weight: 700, font: READ, alpha: clamp(k) });
    text(m[1], x + 200, y, { size: 15, font: READ, color: INK2, alpha: clamp(k) });
  });
  ctx.restore();
  // the third sentence: every kind of mail, one pile
  const kinds = ["Action", "Meeting/Invite", "Alerts", "Newsletter", "GitHub-Admin", "Promo"];
  kinds.forEach((tag, i) => {
    const k = seg(t, a2 + i * 0.18, a2 + 0.4 + i * 0.18);
    const cx = 80 + (i % 3) * 120, cy = 470 + Math.floor(i / 3) * 40;
    dot(cx + 8, cy - 5, 8, LINE[tag], k);
    text(tag.split("/")[0], cx + 24, cy + 1, { size: 16, weight: 700, font: SIGN, alpha: k });
  });
  text(S.demo.toUpperCase(), 80, 660, { size: 12, weight: 600, font: SIGN, color: INK3, spacing: "1.5px", alpha: kc });
}

function sRules(t, d, cues) {
  const a1 = at(cues, 1, 2.5), a2 = at(cues, 2, 6);
  title(S.rules, null, seg(t, 0.1, 0.6));
  const ruleMail = MAIL.filter((m) => m[2] === "r");
  map({ trunk: seg(t, 0.2, 1.2) * 0.42, rules: seg(t, a1 - 0.6, a1 + 1.2), labels: { inbox: seg(t, 0.3, 0.8), rules: seg(t, 0.8, 1.2) },
    terminals: { rules: seg(t, a1, a1 + 1), ruleN: seg(t, a1 + 0.4, a1 + 4.2) } });
  trips(t, ruleMail, a1 + 0.2, 0.13, 560);
  // readouts
  const kr = seg(t, a1 + 0.6, a1 + 1.2);
  text(String(Math.round(27 * outCubic(seg(t, a1 + 0.4, a1 + 4.2)))), 80, 250, { size: 84, weight: 800, font: SIGN, alpha: kr });
  text(S.routed, 80, 282, { size: 20, weight: 700, font: SIGN, alpha: kr });
  const k0 = seg(t, a2, a2 + 0.5);
  panel(80, 312, 250, 54, { r: 12, fill: INK, stroke: false, alpha: k0 });
  text("0", 104, 351, { size: 34, weight: 800, font: SIGN, color: ENAMEL, alpha: k0 });
  text(S.noModel, 134, 346, { size: 18, weight: 700, font: SIGN, color: ENAMEL, alpha: k0 });
  text(S.nothingSent, 80, 392, { size: 16, font: READ, color: INK2, alpha: seg(t, a2 + 0.6, a2 + 1.1) });
}

function sModel(t, d, cues) {
  const a1 = at(cues, 1, 2.5), a2 = at(cues, 2, 6);
  title(S.first, null, seg(t, 0.1, 0.6));
  const model = MAIL.filter((m) => m[2] !== "r");
  // the ten travel to the first pass and wait there; the three ambiguous ones take the spur
  map({ trunk: lerp(0.42, 0.62, seg(t, 0.2, 1.4)), rules: 1, dimRules: 0.22, spur: seg(t, a2, a2 + 1), labels: { inbox: 1, rules: 0.5, first: seg(t, 0.6, 1.1), escal: seg(t, a2 + 0.5, a2 + 1) } });
  model.forEach((m, i) => {
    const toClassify = [[X.inbox, TRUNK], [X.classify, TRUNK]];
    const k1 = outCubic(seg(t, 0.4 + i * 0.12, 1.8 + i * 0.12));
    let [x, y] = pointAt(toClassify, k1);
    const queue = i * 15;
    if (k1 >= 1) x -= queue * (1 - seg(t, a1, a1 + 0.8));
    const esc = m[2] !== "m";
    if (esc && t > a2) {
      const ei = model.filter((n) => n[2] !== "m").indexOf(m);
      const kk = seg(t, a2 + 0.3 + ei * 0.35, a2 + 1.5 + ei * 0.35);
      const spur = [[X.classify, TRUNK], [X.classify + 40, SPUR], [(X.classify + X.validate) / 2, SPUR]];
      [x, y] = pointAt(spur, outCubic(kk));
      if (kk >= 1) x += (ei - 1) * 16;
    } else if (!esc && t > a1 + 0.8) {
      const mi = model.filter((n) => n[2] === "m").indexOf(m);
      x = X.classify - 42 + (mi % 4) * 28; y = TRUNK - 28 - Math.floor(mi / 4) * 22;
    }
    dot(x, y, 7, m[3] === "Action" || m[2] === "w" ? RED : ENAMEL); ring(x, y, 7, m[3] === "Action" || m[2] === "w" ? RED : INK, 2.5);
  });
  // readouts
  const kr = seg(t, 0.4, 1);
  text(String(Math.round(10 * outCubic(seg(t, 0.4, 2)))), 80, 250, { size: 84, weight: 800, font: SIGN, alpha: kr });
  text(S.read, 80, 282, { size: 20, weight: 700, font: SIGN, alpha: kr });
  const kb = seg(t, a1, a1 + 0.5);
  pill(LANG === "fr" ? "1 lot de 25 max" : "1 batch · up to 25", 80, 330, { font: SIGN, size: 16, fill: "#fff", stroke: INK, color: INK, alpha: kb });
  const ke = seg(t, a2 + 0.4, a2 + 0.9);
  pill(LANG === "fr" ? "3 escaladés" : "3 escalated", 80, 376, { font: SIGN, size: 16, fill: INK, stroke: INK, color: ENAMEL, alpha: ke });
  text(S.calls, 80, 660, { size: 14, weight: 600, font: SIGN, color: INK2, spacing: "0.5px", alpha: seg(t, a1 + 0.5, a1 + 1) });
}

function sValidate(t, d, cues) {
  const a1 = at(cues, 1, 2.2), a2 = at(cues, 2, 4.5);
  title(S.validate, null, seg(t, 0.1, 0.6));
  map({ trunk: lerp(0.62, 1, seg(t, 0.1, 0.9)), rules: 1, dimRules: lerp(0.22, 1, seg(t, a2 + 0.6, a2 + 1.6)), spur: 1, model: seg(t, a2, a2 + 1.2), waiting: seg(t, a2 + 0.3, a2 + 1.2),
    labels: { inbox: 1, rules: 1, first: 1, escal: 1, validate: seg(t, 0.5, 1) },
    terminals: { rules: seg(t, a2 + 0.6, a2 + 1.6), model: seg(t, a2 + 0.4, a2 + 1.4), waiting: seg(t, a2 + 0.9, a2 + 1.4), modelN: seg(t, a2 + 0.6, a2 + 2.4) } });
  trips(t, MAIL.filter((m) => m[2] !== "r"), a2, 0.16, 420);
  S.checks.forEach((c, i) => {
    const k = seg(t, a1 + i * 0.35, a1 + 0.5 + i * 0.35);
    const y = 220 + i * 44;
    dot(98, y - 7, 15, INK, k);
    check(98, y - 7, 15, ENAMEL, seg(t, a1 + i * 0.35 + 0.15, a1 + 0.6 + i * 0.35));
    text(c, 126, y, { size: 19, weight: 700, font: SIGN, alpha: k });
  });
  const kx = seg(t, a2, a2 + 0.5);
  dot(98, 220 + 4 * 44 - 7, 15, RED, kx);
  cross(98, 220 + 4 * 44 - 7, 6, "#fff", seg(t, a2 + 0.1, a2 + 0.6));
  text(S.refused, 126, 220 + 4 * 44, { size: 19, weight: 700, font: SIGN, color: RED, alpha: kx });
}

function sResult(t, d, cues) {
  const a1 = at(cues, 1, 2), a2 = at(cues, 2, 5), a3 = at(cues, 3, 7.5);
  title(S.labelled, null, seg(t, 0.1, 0.6));
  // the inbox, labels stepping in like a destination blind
  const x = 80, w = 640, top = 150;
  panel(x, top, w, 470, { r: 16, fill: "#fff", stroke: RULE });
  ctx.save(); rr(x, top, w, 470, 16); ctx.clip();
  const held = MAIL.find((m) => m[2] === "w");
  const shown = MAIL.filter((m) => m !== held).slice(0, 20);
  shown.splice(12, 0, held);
  let row = 0;
  shown.forEach((m, i) => {
    const gone = m[4] && t > a2 + 0.2;
    const kg = gone ? seg(t, a2 + 0.2 + i * 0.03, a2 + 0.6 + i * 0.03) : 0;
    if (kg >= 1) return;
    const y = top + 32 + row * 30 - 0;
    row += 1 - kg;
    const ka = clamp(1 - kg);
    const wait = m[2] === "w";
    if (wait && t > a3) panel(x + 4, y - 20, w - 8, 28, { r: 6, fill: "rgba(228,0,43,0.10)", stroke: false });
    text(m[0], x + 20, y, { size: 14, weight: 700, font: READ, alpha: ka, color: wait && t > a3 ? RED : INK });
    const kb = outBack(seg(t, 0.4 + i * 0.07, 0.8 + i * 0.07));
    let bx = x + 160;
    if (m[3]) {
      ctx.save(); ctx.beginPath(); ctx.rect(bx - 2, y - 13, 200, 26); ctx.clip();
      ctx.translate(0, (1 - kb) * -24);
      bx += bullet(m[3], bx, y - 4, ka) + 8;
      ctx.restore();
    } else if (t > a3) {
      const kw = seg(t, a3, a3 + 0.4);
      panel(bx, y - 15, 120, 22, { r: 11, fill: "#fff", stroke: RED, lw: 2, alpha: kw });
      text(S.waiting, bx + 60, y + 0.5, { size: 12, weight: 700, font: SIGN, color: RED, align: "center", alpha: kw });
      bx += 128;
    }
    text(m[1], bx + (m[3] ? 0 : 0), y, { size: 14, font: READ, color: INK2, alpha: ka });
  });
  ctx.restore();
  // tasks
  const tx = 760;
  text(S.tasksTitle, tx, 176, { size: 26, weight: 800, font: SIGN, alpha: seg(t, a1, a1 + 0.4) });
  TASKS.forEach((tk, i) => {
    const k = outCubic(seg(t, a1 + 0.2 + i * 0.3, a1 + 0.8 + i * 0.3));
    const y = 196 + i * 104 + (1 - k) * 20;
    panel(tx, y, 440, 94, { r: 12, fill: "#fff", stroke: RULE, alpha: k });
    ring(tx + 26, y + 26, 10, INK2, 2.5, k);
    const lines = wrap(tk[0], 370, 16, 700, READ);
    lines.slice(0, 2).forEach((l, j) => text(l, tx + 48, y + 31 + j * 20, { size: 16, weight: 700, font: READ, alpha: k }));
    const due = new Date(`${tk[1]}T12:00:00`).toLocaleDateString(LANG === "fr" ? "fr-FR" : "en-GB", { weekday: "short", day: "numeric", month: "short" });
    pill(`${S.due} ${due}`, tx + 48, y + 31 + Math.min(2, lines.length) * 20 + 8, { font: SIGN, size: 12, fill: ENAMEL2, stroke: false, color: INK, alpha: k, h: 22, padX: 8 });
  });
  const kk = seg(t, a2 + 0.4, a2 + 0.9);
  pill(`11 ${S.archived}`, 1200, 92, { align: "right", font: SIGN, size: 18, fill: INK, stroke: false, color: ENAMEL, alpha: kk, h: 36 });
}

function sQuiet(t, d, cues) {
  const a1 = at(cues, 1, 2.2), a2 = at(cues, 2, 4.5);
  const kc = seg(t, 0.1, 0.6);
  panel(80, 70, 220, 96, { r: 14, fill: INK, stroke: false, alpha: kc });
  text(S.clock9, 190, 142, { size: 70, weight: 800, font: SIGN, color: ENAMEL, align: "center", alpha: kc });
  const dark = seg(t, a1, a1 + 1.2);
  map({ trunk: 1, rules: 1, model: 1, waiting: 1, spur: 1, spurAlpha: lerp(1, 0.16, dark), dimRules: lerp(1, 0.5, dark), dimModel: lerp(1, 0.5, dark),
    labels: { inbox: 1, rules: 1, first: 1, escal: 1, validate: 1 }, terminals: { rules: 1, model: 1, waiting: 1 } });
  text(S.nothingNew, 80, 214, { size: 22, weight: 700, font: SIGN, alpha: seg(t, a1, a1 + 0.5) });
  const kz = seg(t, a1 + 0.4, a1 + 0.9);
  text("0", 80, 320, { size: 110, weight: 800, font: SIGN, alpha: kz });
  text(S.zero, 80, 352, { size: 20, weight: 700, font: SIGN, alpha: kz });
  text(S.spurDark, (X.classify + X.validate) / 2, SPUR - 76, { size: 18, weight: 700, font: SIGN, align: "center", color: INK2, alpha: seg(t, a2, a2 + 0.5) });
}

function sign(x, y, w, k, title, sub, icon) {
  const yy = y + (1 - outCubic(k)) * 24;
  panel(x, yy, w, 250, { r: 18, fill: INK, stroke: false, alpha: k });
  ctx.save(); ctx.globalAlpha *= k; icon(x + 40, yy + 60); ctx.restore();
  text(title, x + 32, yy + 160, { size: 30, weight: 800, font: SIGN, color: ENAMEL, alpha: k });
  text(sub, x + 32, yy + 200, { size: 16, font: MONO, color: "#b9bcc0", alpha: k });
}
function sSafety(t, d, cues) {
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 2.5), a2 = at(cues, 2, 5.5);
  title(LANG === "fr" ? "Rien ne bouge sans votre accord." : "Nothing moves without your say-so.", null, seg(t, a0, a0 + 0.6));
  const eye = (x, y) => { line([[x - 8, y + 20], [x + 20, y], [x + 48, y + 20], [x + 20, y + 40], [x - 8, y + 20]], ENAMEL, 4); dot(x + 20, y + 20, 8, ENAMEL); };
  const plan = (x, y) => { [0, 14, 28].forEach((dy) => line([[x, y + 6 + dy], [x + 44, y + 6 + dy]], ENAMEL, 4)); };
  const undo = (x, y) => {
    ctx.save(); ctx.strokeStyle = ENAMEL; ctx.lineWidth = 4; ctx.lineCap = "round"; ctx.beginPath(); ctx.arc(x + 22, y + 22, 20, Math.PI * 0.9, Math.PI * 2.4); ctx.stroke(); ctx.restore();
    line([[x - 2, y + 10], [x + 2, y + 24], [x + 16, y + 20]], ENAMEL, 4);
  };
  sign(80, 210, 350, seg(t, a1 - 0.6, a1 - 0.1), S.s1, S.s1b, eye);
  sign(465, 210, 350, seg(t, a1 + 0.6, a1 + 1.1), S.s2, S.s2b, plan);
  sign(850, 210, 350, seg(t, a2, a2 + 0.5), S.s3, S.s3b, undo);
}

function sEnd(t, d, cues) {
  const a1 = at(cues, 1, 2), a2 = at(cues, 2, 4), a3 = at(cues, 3, 6.5);
  const k = outBack(seg(t, 0.1, 0.8));
  // the roundel
  ctx.save(); ctx.translate(640, 220); ctx.scale(k, k);
  ring(0, 0, 70, INK, 26); panel(-110, -13, 220, 26, { r: 13, fill: "#0072ce", stroke: false });
  ctx.restore();
  text(S.name, 640, 382, { size: 64, weight: 800, font: SIGN, align: "center", alpha: seg(t, 0.4, 0.9) });
  text(S.oss, 640, 420, { size: 20, font: READ, color: INK2, align: "center", alpha: seg(t, a1, a1 + 0.5) });
  const kt = seg(t, a2, a2 + 0.4);
  panel(500, 448, 280, 52, { r: 12, fill: INK, stroke: false, alpha: kt });
  text("$", 524, 482, { size: 20, font: MONO, color: "#9ea2a7", alpha: kt });
  text(typed("make setup", seg(t, a2 + 0.2, a2 + 1.0)), 548, 482, { size: 20, font: MONO, color: ENAMEL, alpha: kt });
  text(S.tagline, 640, 560, { size: 34, weight: 800, font: SIGN, align: "center", alpha: seg(t, a3, a3 + 0.5) });
  text(S.url, 640, 600, { size: 16, weight: 600, font: SIGN, color: INK2, align: "center", spacing: "1px", alpha: seg(t, a3 + 0.3, a3 + 0.8) });
}

function enamel() {
  ctx.fillStyle = ENAMEL; ctx.fillRect(0, 0, W, H);
}

VIDEO.create({
  title: { en: "AI Mail Assistant: every message, routed", fr: "AI Mail Assistant : chaque message trouve sa voie" },
  kicker: { en: "The film · invented demo mailbox", fr: "Le film · boîte de démo inventée" },
  langs: ["en", "fr"],
  theme: { bg: ENAMEL, bg2: ENAMEL, panel: "#fff", panel2: ENAMEL2, line: RULE, ink: INK, soft: INK2, faint: INK3, deep: INK, term: INK, termInk: ENAMEL, accent: INK, good: "#00a650", warn: "#ffb500", bad: RED },
  strings: STR,
  background: enamel,
  poster: "validate",
  fonts: ['800 20px "Barlow Semi Condensed"', '700 20px "Barlow Semi Condensed"', '600 20px "Barlow Semi Condensed"', '400 20px "Atkinson Hyperlegible"', '700 20px "Atkinson Hyperlegible"'],
  scenes: { morning: sMorning, rules: sRules, model: sModel, validate: sValidate, result: sResult, quiet: sQuiet, safety: sSafety, end: sEnd },
});
