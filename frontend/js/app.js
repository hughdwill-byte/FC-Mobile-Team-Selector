// ------------------------------------------------------------------ state
const State = {
  meta: null,
  players: [],
  view: "squad",
  squad: null,
  selectedFormation: 0,
  editing: null,      // player being edited (or null = new)
  sort: { key: "best_score", dir: -1 },
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (isErr ? " err" : "");
  setTimeout(() => (t.className = "toast"), 2200);
}
function ratingClass(v) { return v >= 82 ? "hi" : v >= 74 ? "mid" : "lo"; }

// Goalkeepers use different main stats; the six stat columns are relabelled for them.
const GK_LABELS = {
  pace: "Diving", shooting: "Handling", passing: "Kicking",
  dribbling: "Reflexes", defending: "Positioning", physical: "Physical",
};
const statLabel = (stat, isGk) => (isGk ? (GK_LABELS[stat] || stat) : stat);

// ---- UI-state persistence (so a reload lands back where you were) ----
const LS_KEY = "fcm.ui.v1";
function persist() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      view: State.view, selectedFormation: State.selectedFormation,
      upkind: State._upkind, rulefile: State._rulefile, search: State._search,
      sort: State.sort, trainingXp: State._trainingXp, squadMode: State._squadMode,
    }));
  } catch (e) { /* private mode / disabled storage: ignore */ }
}
function restoreUi() {
  try {
    const d = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
    if (d.view) State.view = d.view;
    if (typeof d.selectedFormation === "number") State.selectedFormation = d.selectedFormation;
    if (d.upkind) State._upkind = d.upkind;
    if (d.rulefile) State._rulefile = d.rulefile;
    if (typeof d.search === "string") State._search = d.search;
    if (d.sort && d.sort.key) State.sort = d.sort;
    if (typeof d.trainingXp === "number") State._trainingXp = d.trainingXp;
    if (d.squadMode) State._squadMode = d.squadMode;
  } catch (e) { /* ignore */ }
}

// ------------------------------------------------------------------ boot
async function boot() {
  try {
    State.meta = await API.meta();
  } catch (e) {
    document.body.innerHTML = "<p style='padding:40px'>Cannot reach the backend. Is the app running?</p>";
    return;
  }
  restoreUi();
  wireTabs();
  wireDrawer();
  wireKeys();
  $("#btn-refresh").onclick = () => render();
  await loadPlayers();
  setView(State.view || "squad");
}

async function loadPlayers() {
  State.players = await API.players();
  $("#player-count").textContent = `${State.players.length} player${State.players.length === 1 ? "" : "s"}`;
}

function wireTabs() {
  $$(".tab").forEach((b) => (b.onclick = () => setView(b.dataset.view)));
}
function setView(v) {
  State.view = v;
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
  persist();
  render();
}

// ------------------------------------------------------------------ router
async function render() {
  const app = $("#app");
  app.innerHTML = "<div class='hint'>Loading…</div>";
  try {
    if (State.view === "squad") return renderSquad(app);
    if (State.view === "players") return renderPlayers(app);
    if (State.view === "upgrades") return renderUpgrades(app);
    if (State.view === "gaps") return renderGaps(app);
    if (State.view === "bench") return renderBench(app);
    if (State.view === "rules") return renderRules(app);
    if (State.view === "data") return renderData(app);
  } catch (e) {
    app.innerHTML = `<div class='panel'>Error: ${esc(e.message)}</div>`;
  }
}

function notEnough(app, have) {
  app.innerHTML = `<div class='empty-state'>
    <h2>Need at least 11 players</h2>
    <p>You have <b>${have}</b>. Add players under the <span class="kbd">Players</span> tab
    (or load the sample squad — see the README), then come back here.</p>
    <button class="btn primary" onclick="setView('players')">Go to Players</button>
  </div>`;
}

// ------------------------------------------------------------------ Best XI
const BAND_Y = {
  GK: 0.93, CB: 0.76, RB: 0.76, LB: 0.76, RWB: 0.72, LWB: 0.72,
  CDM: 0.63, CM: 0.52, RM: 0.52, LM: 0.52, CAM: 0.40,
  RW: 0.30, LW: 0.30, CF: 0.25, ST: 0.16,
};
function hintX(code) { return code.includes("L") && code !== "GK" ? -1 : code.includes("R") ? 1 : 0; }

function layout(slots) {
  // group by y band, distribute x evenly within each band (left/right hinted)
  const groups = {};
  slots.forEach((s, i) => {
    const y = BAND_Y[s.position] ?? 0.5;
    (groups[y] ||= []).push({ ...s, i });
  });
  const coords = {};
  Object.values(groups).forEach((g) => {
    g.sort((a, b) => hintX(a.position) - hintX(b.position) || a.i - b.i);
    const n = g.length;
    // Wide bands (with L*/R* roles) spread to the touchlines; central bands stay
    // narrow so pairs/trios of central players don't fly out to the wings.
    const wide = g.some((s) => /^[LR]/.test(s.position) && s.position !== "GK");
    const span = n === 1 ? 0 : (wide ? 0.76 : Math.min(0.5, 0.2 * (n - 1)));
    g.forEach((s, k) => {
      const x = n === 1 ? 0.5 : 0.5 - span / 2 + (span * k) / (n - 1);
      coords[s.i] = { x, y: BAND_Y[s.position] ?? 0.5 };
    });
  });
  return coords;
}

async function renderSquad(app) {
  const potential = State._squadMode === "potential";
  State.squad = await API.squad(5, potential);
  if (!State.squad.enough_players) return notEnough(app, State.squad.have);
  const results = State.squad.results;
  const sel = Math.min(State.selectedFormation, results.length - 1);
  const fr = results[sel];
  const coords = layout(fr.slots);

  const slotsHtml = fr.slots.map((s) => {
    const c = coords[s.slot_index];
    const empty = s.player_id == null;
    return `<div class="slot ${empty ? "empty" : ""}" style="left:${c.x * 100}%;top:${c.y * 100}%"
      data-pid="${s.player_id ?? ""}">
      <div class="card">
        <div class="pos">${s.position}${empty ? "" : ` · OVR ${Math.round(s.ovr)}`}</div>
        <div class="nm">${esc(empty ? "—" : s.player_name)}</div>
        <div class="sc">${empty ? "" : s.score.toFixed(1)}</div>
      </div></div>`;
  }).join("");

  const formationList = results.map((r, i) => {
    const delta = i === 0 ? "" : `<span class="fdelta">−${(results[0].total - r.total).toFixed(1)}</span>`;
    return `<div class="formation-item ${i === sel ? "active" : ""}" data-idx="${i}">
      <span class="fname">${esc(r.formation)}</span>
      <span><span class="ftot">${r.total.toFixed(1)}</span>${delta}</span>
    </div>`;
  }).join("");

  const reasoning = fr.slots.map((s) => {
    const ru = s.runner_up_name
      ? `${esc(s.runner_up_name)} <span class="hint">(${s.runner_up_score.toFixed(1)})</span>` : "—";
    return `<tr>
      <td><span class="chip pos">${s.position}</span></td>
      <td class="clickable" data-pid="${s.player_id ?? ""}">${esc(s.player_name)}</td>
      <td class="num rating ${s.player_id == null ? "" : ratingClass(s.ovr)}">${s.player_id == null ? "—" : Math.round(s.ovr)}</td>
      <td class="num rating ${s.player_id == null ? "" : ratingClass(s.score)}">${s.player_id == null ? "—" : s.score.toFixed(1)}</td>
      <td>${ru}</td>
    </tr>`;
  }).join("");

  const modeToggle = `
    <div style="display:flex;gap:4px">
      <button class="btn small ${!potential ? "primary" : "ghost"}" data-mode="current">Current</button>
      <button class="btn small ${potential ? "primary" : "ghost"}" data-mode="potential">Potential (all ranked up)</button>
    </div>`;
  const potentialBanner = potential ? `
    <div class="panel" style="border-color:#204034">
      <b>Potential XI</b> — assuming every player is ranked up to the max rank (their OVR, stats and
      unlocked positions applied). Best potential formation <b>${esc(results[0].formation)}</b> scores
      <b class="gain-pos">${results[0].total.toFixed(1)}</b>${State.squad.current_best_total != null
        ? ` · <b class="gain-pos">+${(results[0].total - State.squad.current_best_total).toFixed(1)}</b> over your current best (${State.squad.current_best_total.toFixed(1)})`
        : ""}. <span class="hint">This is what to push for.</span>
    </div>` : "";

  app.innerHTML = `
    <div class="section-title"><h2>${potential ? "Potential XI" : "Best XI"}</h2>${modeToggle}</div>
    <div class="hint" style="margin:-6px 0 12px">Best of ${State.squad.have} players across ${State.meta.formations.length} formations · Hungarian-optimal</div>
    ${potentialBanner}
    <div class="pitch-wrap">
      <div class="pitch">
        <div class="circle"></div><div class="box top"></div><div class="box bot"></div>
        ${slotsHtml}
      </div>
      <div class="col" style="flex:1 1 320px">
        <div class="panel"><h3>Top formations</h3><div class="formation-list">${formationList}</div></div>
        <div class="panel"><h3>Why — slot by slot (${esc(fr.formation)})</h3>
          <table><thead><tr><th>Slot</th><th>Starter</th><th class="num">OVR</th><th class="num">Score</th><th>Runner-up</th></tr></thead>
          <tbody>${reasoning}</tbody></table>
        </div>
      </div>
    </div>`;

  $$("[data-mode]").forEach((b) => (b.onclick = () => { State._squadMode = b.dataset.mode; State.selectedFormation = 0; persist(); render(); }));
  $$(".formation-item").forEach((it) => (it.onclick = () => { State.selectedFormation = +it.dataset.idx; persist(); render(); }));
  $$("[data-pid]").forEach((el) => (el.onclick = () => { const id = +el.dataset.pid; if (id) openEditor(id); }));
}

// ------------------------------------------------------------------ Players
function renderPlayers(app) {
  const q = (State._search || "").toLowerCase();
  let rows = State.players.filter((p) =>
    p.name.toLowerCase().includes(q) || (p.positions || []).join(" ").toLowerCase().includes(q));
  const { key, dir } = State.sort;
  rows.sort((a, b) => {
    const av = a[key], bv = b[key];
    return (av > bv ? 1 : av < bv ? -1 : 0) * dir;
  });

  const head = [
    ["name", "Name"], ["ovr", "OVR"], ["positions", "Positions"],
    ["pace", "PAC"], ["shooting", "SHO"], ["passing", "PAS"], ["dribbling", "DRI"],
    ["defending", "DEF"], ["physical", "PHY"],
    ["best_position", "Best"], ["best_score", "Score"], ["rank", "Rank"], ["training_level", "Lvl"],
  ].map(([k, label]) => `<th class="${["ovr","pace","shooting","passing","dribbling","defending","physical","best_score","rank","training_level"].includes(k) ? "num" : ""}" data-sort="${k}">${label}${State.sort.key === k ? (dir < 0 ? " ▾" : " ▴") : ""}</th>`).join("");

  const body = rows.map((p) => `<tr class="clickable" data-id="${p.id}">
    <td><b>${esc(p.name)}</b> ${(p.playstyles || []).map((s) => `<span class="chip ps">${esc(s.name)}${s.plus ? "+" : ""}</span>`).join("")}</td>
    <td class="num rating ${ratingClass(p.ovr)}">${p.ovr}</td>
    <td>${(p.positions || []).map((x) => `<span class="chip pos">${esc(x)}</span>`).join("") || "<span class='hint'>none</span>"}</td>
    <td class="num">${p.pace}</td><td class="num">${p.shooting}</td><td class="num">${p.passing}</td>
    <td class="num">${p.dribbling}</td><td class="num">${p.defending}</td><td class="num">${p.physical}</td>
    <td><span class="chip pos">${esc(p.best_position)}</span></td>
    <td class="num rating ${ratingClass(p.best_score)}">${p.best_score.toFixed(1)}</td>
    <td class="num">${p.rank}/5</td><td class="num">${p.training_level}/30</td>
  </tr>`).join("");

  app.innerHTML = `
    <div class="toolbar">
      <button class="btn primary" id="add-player">+ Add player <span class="kbd">n</span></button>
      <input type="search" id="search" placeholder="Search name or position…" value="${esc(State._search || "")}" />
      <span class="hint">${rows.length} shown · click a row to edit</span>
    </div>
    <div class="panel" style="padding:0;overflow-x:auto">
      <table><thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="13" class="empty-state">No players yet — add one.</td></tr>`}</tbody></table>
    </div>`;

  $("#add-player").onclick = () => openEditor(null);
  const s = $("#search");
  s.oninput = () => { State._search = s.value; persist(); const pos = s.selectionStart; renderPlayers(app); const ns = $("#search"); ns.focus(); ns.setSelectionRange(pos, pos); };
  $$("th[data-sort]").forEach((th) => (th.onclick = () => {
    const k = th.dataset.sort;
    State.sort = { key: k, dir: State.sort.key === k ? -State.sort.dir : (k === "name" || k === "best_position" ? 1 : -1) };
    persist();
    renderPlayers(app);
  }));
  $$("tr[data-id]").forEach((tr) => (tr.onclick = () => openEditor(+tr.dataset.id)));
}

// ------------------------------------------------------------------ Player editor drawer
function openEditor(id) {
  const p = id ? State.players.find((x) => x.id === id) : null;
  // New players start with every field blank (you fill them in).
  State.editing = p ? JSON.parse(JSON.stringify(p)) : {
    name: "", ovr: "", rank: "", training_level: "",
    pace: "", shooting: "", passing: "", dribbling: "", defending: "", physical: "",
    positions: [], rankup_positions: [], playstyles: [], skill_points: "", notes: "", base_stats: null,
  };
  $("#drawer-title").textContent = id ? "Edit player" : "Add player";
  $("#player-delete-wrap").style.display = id ? "" : "none";
  buildEditorForm();
  $("#drawer").classList.remove("hidden");
  setTimeout(() => $("#f-name")?.focus(), 30);
}

function buildEditorForm() {
  const p = State.editing;
  const stats = State.meta.main_stats;
  const isGk = (p.positions || []).includes("GK");
  const val = (v) => (v === "" || v === null || v === undefined ? "" : v);
  const posChips = State.meta.positions.map((code) =>
    `<span class="chip pos ${p.positions.includes(code) ? "" : "off"}" data-pos="${code}"
      style="cursor:pointer;${p.positions.includes(code) ? "" : "opacity:.35"}">${code}</span>`).join(" ");
  const psOptions = (sel) => `<option value="">— none —</option>` +
    State.meta.playstyles.map((n) => `<option ${sel === n ? "selected" : ""}>${n}</option>`).join("");
  const ps0 = p.playstyles[0] || {}, ps1 = p.playstyles[1] || {};

  $("#drawer-body").innerHTML = `
    <div class="field"><label>Name</label><input id="f-name" value="${esc(p.name)}" placeholder="Player name" /></div>
    <div class="grid3">
      <div class="field"><label>OVR</label><input id="f-ovr" type="number" value="${val(p.ovr)}" placeholder="—" /></div>
      <div class="field"><label>Rank (0–5)</label><input id="f-rank" type="number" min="0" max="5" value="${val(p.rank)}" placeholder="0" /></div>
      <div class="field"><label>Training (0–30)</label><input id="f-training_level" type="number" min="0" max="30" value="${val(p.training_level)}" placeholder="0" /></div>
    </div>
    <div class="field"><label>${isGk ? "Goalkeeper stats (current)" : "Main stats (current)"}</label>
      ${isGk ? '<div class="hint" style="margin-bottom:6px">GK selected — these six are Diving / Handling / Kicking / Reflexes / Positioning / Physical.</div>' : ""}
      <div class="statgrid">
        ${stats.map((s) => `<div class="field" style="margin:0"><label>${statLabel(s, isGk)}</label><input id="f-${s}" type="number" value="${val(p[s])}" placeholder="—" /></div>`).join("")}
      </div>
    </div>
    <div class="field"><label>Base stats (at training level 0)</label>
      <div class="hint" style="margin-bottom:6px">Optional but recommended — the fair way to compare cards, and what the <b>Potential XI</b> is built from.</div>
      <div class="statgrid">
        ${stats.map((s) => `<div class="field" style="margin:0"><label>${statLabel(s, isGk)}</label>
          <input id="b-${s}" type="number" placeholder="—"
            value="${p.base_stats && p.base_stats[s] != null ? p.base_stats[s] : ""}" /></div>`).join("")}
      </div>
    </div>
    <div class="field"><label>Positions (click to toggle)</label><div id="pos-chips">${posChips}</div></div>
    <div class="field"><label>Unlocks on next rank up (optional)</label>
      <input id="f-rankup_positions" value="${esc((p.rankup_positions || []).join(", "))}" placeholder="e.g. CF, RW" /></div>
    <div class="grid2">
      <div class="field"><label>PlayStyle 1</label><select id="f-ps0">${psOptions(ps0.name)}</select>
        <label style="margin-top:6px"><input type="checkbox" id="f-ps0plus" ${ps0.plus ? "checked" : ""}/> Gold (PlayStyle+)</label></div>
      <div class="field"><label>PlayStyle 2</label><select id="f-ps1">${psOptions(ps1.name)}</select>
        <label style="margin-top:6px"><input type="checkbox" id="f-ps1plus" ${ps1.plus ? "checked" : ""}/> Gold (PlayStyle+)</label></div>
    </div>
    <div class="field"><label>Skill points available</label><input id="f-skill_points" type="number" min="0" value="${val(p.skill_points)}" placeholder="0" /></div>
    <div class="field"><label>Notes</label><textarea id="f-notes" rows="2">${esc(p.notes || "")}</textarea></div>
    <div class="field"><label>Growth override (advanced, per training level — optional)</label>
      <div class="statgrid">
        ${stats.map((s) => `<div class="field" style="margin:0"><label>${statLabel(s, isGk)}</label>
          <input id="g-${s}" type="number" step="0.1" placeholder="default"
            value="${p.growth_override && p.growth_override[s] != null ? p.growth_override[s] : ""}" /></div>`).join("")}
      </div>
      <div class="hint">Leave blank to use the default curve from rules/growth.json.</div>
    </div>`;

  $$("#pos-chips .chip").forEach((c) => (c.onclick = () => {
    syncEditor();                       // keep everything the user has typed so far
    const code = c.dataset.pos;
    const arr = State.editing.positions;
    const i = arr.indexOf(code);
    if (i >= 0) arr.splice(i, 1); else arr.push(code);
    buildEditorForm();                  // rebuild (labels may change for GK)
  }));
}

// Read the current form values back into State.editing WITHOUT coercing blanks to
// defaults, so rebuilding the form (e.g. after toggling a position) preserves them.
function syncEditor() {
  const p = State.editing;
  const g = (id) => document.getElementById(id);
  if (!g("f-name")) return;
  const raw = (id) => { const v = g(id).value; return v === "" ? "" : Number(v); };
  p.name = g("f-name").value;
  p.ovr = raw("f-ovr"); p.rank = raw("f-rank"); p.training_level = raw("f-training_level");
  State.meta.main_stats.forEach((s) => { p[s] = raw("f-" + s); });
  p.rankup_positions = g("f-rankup_positions").value.split(",").map((x) => x.trim()).filter(Boolean);
  const psl = [];
  ["ps0", "ps1"].forEach((k) => { const nm = g("f-" + k).value; if (nm) psl.push({ name: nm, plus: g("f-" + k + "plus").checked }); });
  p.playstyles = psl;
  p.skill_points = raw("f-skill_points");
  p.notes = g("f-notes").value;
  const growth = {}; let has = false;
  State.meta.main_stats.forEach((s) => { const v = g("g-" + s).value.trim(); if (v !== "") { growth[s] = Number(v); has = true; } });
  p.growth_override = has ? growth : null;
  const bs = {}; let hasB = false;
  State.meta.main_stats.forEach((s) => { const v = g("b-" + s).value.trim(); if (v !== "") { bs[s] = Number(v); hasB = true; } });
  p.base_stats = hasB ? bs : null;
}

function collectEditor() {
  const p = State.editing;
  const g = (id) => $("#" + id);
  const num = (id, d = 0) => { const v = parseFloat(g(id).value); return isNaN(v) ? d : v; };
  const stats = State.meta.main_stats;
  const growth = {};
  let hasGrowth = false;
  stats.forEach((s) => { const v = g("g-" + s).value.trim(); if (v !== "") { growth[s] = parseFloat(v); hasGrowth = true; } });
  const baseStats = {};
  let hasBase = false;
  stats.forEach((s) => { const v = g("b-" + s).value.trim(); if (v !== "") { baseStats[s] = parseFloat(v); hasBase = true; } });
  const playstyles = [];
  ["ps0", "ps1"].forEach((k) => {
    const name = g("f-" + k).value;
    if (name) playstyles.push({ name, plus: g("f-" + k + "plus").checked });
  });
  return {
    name: g("f-name").value.trim(),
    ovr: Math.round(num("f-ovr", 0)), rank: Math.round(num("f-rank", 0)), training_level: Math.round(num("f-training_level", 0)),
    pace: num("f-pace"), shooting: num("f-shooting"), passing: num("f-passing"),
    dribbling: num("f-dribbling"), defending: num("f-defending"), physical: num("f-physical"),
    positions: p.positions,
    rankup_positions: g("f-rankup_positions").value.split(",").map((x) => x.trim()).filter(Boolean),
    playstyles,
    base_stats: hasBase ? baseStats : null,
    growth_override: hasGrowth ? growth : null,
    skill_points: Math.round(num("f-skill_points", 0)),
    notes: g("f-notes").value.trim(),
  };
}

function wireDrawer() {
  const close = () => $("#drawer").classList.add("hidden");
  $("#drawer-close").onclick = close;
  $("#player-cancel").onclick = close;
  $("#drawer").onclick = (e) => { if (e.target.id === "drawer") close(); };
  $("#player-save").onclick = savePlayer;
  $("#player-delete").onclick = deletePlayer;
}

async function savePlayer() {
  const data = collectEditor();
  if (!data.name) return toast("Name is required", true);
  try {
    if (State.editing.id) await API.updatePlayer(State.editing.id, data);
    else await API.createPlayer(data);
    $("#drawer").classList.add("hidden");
    await loadPlayers();
    toast("Saved");
    render();
  } catch (e) { toast(e.message, true); }
}
async function deletePlayer() {
  if (!State.editing.id) return;
  if (!confirm(`Delete ${State.editing.name}?`)) return;
  await API.deletePlayer(State.editing.id);
  $("#drawer").classList.add("hidden");
  await loadPlayers();
  toast("Deleted");
  render();
}

// ------------------------------------------------------------------ Upgrades
async function renderUpgrades(app) {
  const d = await API.upgrades(40);
  if (!d.enough_players) return notEnough(app, d.have);
  State._upkind = State._upkind || "combined";
  const kinds = { combined: d.combined, training: d.by_kind.training, rankup: d.by_kind.rankup, skill: d.by_kind.skill };
  const list = kinds[State._upkind] || [];
  State._upRows = list;
  const warn = d.costs_unverified ? `<span class="badge warn">unverified costs</span>` : "";

  const rows = list.map((c, i) => `<tr>
    <td class="num">${i + 1}</td>
    <td>${esc(c.label)}</td>
    <td class="num gain-pos">+${c.gain.toFixed(2)}</td>
    <td class="num">${c.raw_cost} <span class="hint">${esc(c.cost_currency)}</span></td>
    <td class="num rating hi">${c.gain_per_cost.toFixed(4)}</td>
    <td class="num">${c.new_squad_score.toFixed(1)}</td>
    <td class="num"><button class="btn apply" data-up="${i}">Apply</button></td>
  </tr>`).join("");

  const tabBtn = (k, label) => `<button class="btn small ${State._upkind === k ? "primary" : "ghost"}" data-uk="${k}">${label}</button>`;

  const normalTable = `
    <div class="panel" style="padding:0;overflow-x:auto">
      <table><thead><tr><th class="num">#</th><th>Do this next</th><th class="num">Squad +</th>
        <th class="num">Cost</th><th class="num">Gain / cost</th><th class="num">New score</th><th></th></tr></thead>
      <tbody>${rows || `<tr><td colspan="7" class="empty-state">No improving upgrades found (everything is maxed or gives no gain).</td></tr>`}</tbody></table>
    </div>`;

  const trainingPlanner = `
    <div class="panel">
      <h3>Training budget planner</h3>
      <p class="hint">Enter how much training XP you have. The planner spends it in best-value
      order — the biggest squad-score gain per XP first — across your whole club, not one level at a time.</p>
      <div class="toolbar">
        <input type="number" id="xp-input" placeholder="XP available, e.g. 5000" min="0"
          value="${State._trainingXp || ""}" style="max-width:220px;background:var(--panel);border:1px solid var(--line);color:var(--txt);padding:8px 10px;border-radius:8px" />
        <button class="btn primary" id="xp-go">Plan training</button>
      </div>
    </div>
    <div id="train-results"></div>`;

  const content = State._upkind === "training" ? trainingPlanner : normalTable;

  app.innerHTML = `
    <div class="section-title"><h2>Upgrade plan ${warn}</h2>
      <span class="hint">Baseline squad score <b>${d.baseline_squad_score.toFixed(1)}</b> · ranked by squad-score gain per resource</span></div>
    <div class="toolbar">
      ${tabBtn("combined", "Combined (best value)")}
      ${tabBtn("training", "Training")}
      ${tabBtn("rankup", "Rank ups")}
      ${tabBtn("skill", "Skill points")}
    </div>
    ${d.costs_unverified ? `<div class="panel" style="border-color:#5a4a1e"><b>Costs are placeholders.</b>
      The gain-per-cost ranking is only as good as the cost curves in <code>rules/costs.json</code>.
      Edit them under the <b>Rules</b> tab to match your game, then recompute.</div>` : ""}
    ${content}`;

  $$("[data-uk]").forEach((b) => (b.onclick = () => { State._upkind = b.dataset.uk; persist(); renderUpgrades(app); }));
  $$("[data-up]").forEach((b) => (b.onclick = () => openApplyModal(State._upRows[+b.dataset.up])));

  if (State._upkind === "training") {
    const go = () => {
      const xp = Math.max(0, parseFloat($("#xp-input").value) || 0);
      State._trainingXp = xp;
      persist();
      loadTrainingPlan();
    };
    $("#xp-go").onclick = go;
    $("#xp-input").onkeydown = (e) => { if (e.key === "Enter") go(); };
    if (State._trainingXp > 0) loadTrainingPlan();
  }
}

async function loadTrainingPlan() {
  const box = $("#train-results");
  if (!box) return;
  box.innerHTML = "<div class='hint' style='padding:8px'>Planning…</div>";
  let d;
  try { d = await API.trainingPlan(State._trainingXp); }
  catch (e) { box.innerHTML = `<div class='panel'>Error: ${esc(e.message)}</div>`; return; }

  if (!d.steps || !d.steps.length) {
    box.innerHTML = `<div class="panel empty-state">No worthwhile training found for that budget
      (players may be maxed, or the XP is less than the cheapest useful level).</div>`;
    return;
  }
  State._trainRows = d.steps;
  const rows = d.steps.map((s, i) => `<tr>
    <td class="num">${i + 1}</td>
    <td><b>${esc(s.player_name)}</b> <span class="hint">${s.from_level} → ${s.to_level} (${s.levels} lvl${s.levels === 1 ? "" : "s"})</span></td>
    <td class="num gain-pos">+${s.gain.toFixed(2)}</td>
    <td class="num">${s.cost.toLocaleString()} <span class="hint">XP</span></td>
    <td class="num rating hi">${s.gain_per_cost.toFixed(4)}</td>
    <td class="num">${s.cumulative_xp.toLocaleString()}</td>
    <td class="num"><button class="btn apply" data-tr="${i}">Apply</button></td>
  </tr>`).join("");
  const reason = d.stopped_reason === "budget"
    ? "Budget spent — more worthwhile training is available if you get more XP."
    : d.stopped_reason === "step_cap"
      ? "Reached the planner's step limit."
      : "Spent everything worth spending — remaining XP wouldn't improve the squad.";

  box.innerHTML = `
    <div class="row">
      <div class="panel col"><h3>Summary</h3>
        <ul class="mini-list">
          <li><span>XP budget</span><b>${d.xp_budget.toLocaleString()}</b></li>
          <li><span>XP spent</span><b>${d.spent.toLocaleString()}</b></li>
          <li><span>XP left over</span><b>${d.remaining.toLocaleString()}</b></li>
          <li><span>Levels trained</span><b>${d.levels_trained}</b></li>
          <li><span>Squad score</span><b>${d.baseline_squad_score.toFixed(1)} → ${d.final_squad_score.toFixed(1)}</b></li>
          <li><span>Total gain</span><b class="gain-pos">+${d.total_gain.toFixed(2)}</b></li>
        </ul>
        <p class="hint" style="margin-top:8px">${reason}</p>
      </div>
      <div class="col" style="flex:2 1 560px"><div class="panel" style="padding:0;overflow-x:auto">
        <table><thead><tr><th class="num">#</th><th>Train</th><th class="num">Squad +</th>
          <th class="num">Cost</th><th class="num">Gain / XP</th><th class="num">XP so far</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table>
      </div></div>
    </div>`;

  $$("[data-tr]", box).forEach((b) => (b.onclick = () => {
    const s = State._trainRows[+b.dataset.tr];
    openApplyModal({ kind: "training", player_id: s.player_id, player_name: s.player_name, apply: s.apply });
  }));
}

// ------------------------------------------------------------------ Apply an upgrade to a player
function openApplyModal(c) {
  if (!c) return;
  const p = State.players.find((x) => x.id === c.player_id);
  if (!p) return toast("Player not found", true);
  const a = c.apply || {};
  const kind = c.kind;
  const isGk = (p.positions || []).includes("GK");
  const stats = State.meta.main_stats;
  const deltas = a.stat_deltas || {};

  let info = "";
  if (kind === "training") info = `Set <b>${esc(p.name)}</b>'s training level to <b>${a.new_training_level}</b> (from ${p.training_level}).`;
  else if (kind === "rankup") info = `Rank up <b>${esc(p.name)}</b>: rank <b>${p.rank} → ${a.new_rank}</b>${a.unlocked_positions && a.unlocked_positions.length ? `, unlocking <b>${a.unlocked_positions.join(", ")}</b>` : ""}.`;
  else if (kind === "skill") info = `Spend 1 skill point on <b>${esc(p.name)}</b> (you'll have ${Math.max(0, (p.skill_points || 0) - 1)} left).`;

  // Inputs start EMPTY; the model's estimate is shown only as a faint placeholder hint.
  const statInputs = stats.map((s) => {
    const est = deltas[s];
    const ph = est ? `est +${est}` : "0";
    return `<div class="field" style="margin:0"><label>${statLabel(s, isGk)} +</label>
      <input id="ap-${s}" type="number" step="0.1" placeholder="${ph}" /></div>`;
  }).join("");

  const ovrRow = kind === "rankup" ? `
    <div class="field"><label>OVR increase</label><input id="ap-ovr" type="number" step="1" placeholder="${a.ovr_delta ? "est +" + a.ovr_delta : "0"}" /></div>
    <label style="display:block;margin-bottom:12px"><input type="checkbox" id="ap-sp" checked /> Gained 1 skill point from this rank up</label>` : "";

  // Right-side drawer for this player (same style as the player editor).
  const overlay = document.createElement("div");
  overlay.className = "drawer";
  overlay.innerHTML = `<div class="drawer-panel">
    <div class="drawer-head"><h2>Apply upgrade</h2><button class="btn ghost" id="ap-x">✕</button></div>
    <div class="drawer-body">
      <div class="apply-note">${info}<br><span class="hint">Enter how much each stat actually went up in-game. Leave a box empty for no change; the faint number is the model's estimate for reference.</span></div>
      ${ovrRow}
      <div class="field"><label>${isGk ? "GK stat" : "Stat"} increases</label><div class="statgrid">${statInputs}</div></div>
    </div>
    <div class="drawer-foot">
      <button class="btn primary" id="ap-confirm">Apply to player</button>
      <button class="btn ghost" id="ap-cancel">Cancel</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  const q = (sel) => overlay.querySelector(sel);
  overlay.onclick = (e) => { if (e.target === overlay) close(); };
  q("#ap-x").onclick = close;
  q("#ap-cancel").onclick = close;
  q("#ap-confirm").onclick = async () => {
    const num = (sel) => { const v = parseFloat(q(sel).value); return isNaN(v) ? 0 : v; };
    const upd = {};
    stats.forEach((s) => { upd[s] = (p[s] || 0) + num("#ap-" + s); });
    if (kind === "training") upd.training_level = a.new_training_level;
    if (kind === "rankup") {
      upd.rank = a.new_rank;
      upd.ovr = Math.round((p.ovr || 0) + num("#ap-ovr"));
      if (q("#ap-sp").checked) upd.skill_points = (p.skill_points || 0) + 1;
      const unlocked = (a.unlocked_positions || []).filter((x) => !(p.positions || []).includes(x));
      if (unlocked.length) upd.positions = [...(p.positions || []), ...unlocked];
    }
    if (kind === "skill") upd.skill_points = Math.max(0, (p.skill_points || 0) - 1);
    try {
      await API.updatePlayer(p.id, upd);
      close();
      await loadPlayers();
      toast(`Applied to ${p.name}`);
      render();
    } catch (e) { toast(e.message, true); }
  };
}

// ------------------------------------------------------------------ Gaps
async function renderGaps(app) {
  const d = await API.gaps();
  if (!d.enough_players) return notEnough(app, d.have);
  const prio = d.priority_positions.map((p, i) => `<li>
    <span><b>${i + 1}. <span class="chip pos">${esc(p.position)}</span></b> <span class="reasons">${esc(p.reasons.join(" · "))}</span></span>
    <span class="rating ${p.priority > 4 ? "lo" : "mid"}">${p.priority.toFixed(1)}</span></li>`).join("");
  const slots = d.slots.map((s) => `<tr>
    <td><span class="chip pos">${esc(s.position)}</span></td>
    <td>${esc(s.player_name)}</td>
    <td class="num rating ${ratingClass(s.score)}">${s.score.toFixed(1)}</td>
    <td class="num">${s.deficit_vs_avg > 0 ? "−" + s.deficit_vs_avg.toFixed(1) : "+" + (-s.deficit_vs_avg).toFixed(1)}</td>
    <td>${s.out_of_position ? '<span class="badge warn">out of pos</span> ' : ""}${s.no_specialist ? '<span class="badge warn">no specialist</span> ' : ""}<span class="reasons">${esc(s.reasons.join(" · "))}</span></td>
  </tr>`).join("");
  app.innerHTML = `
    <div class="section-title"><h2>Squad gaps</h2>
      <span class="hint">Formation <b>${esc(d.formation)}</b> · squad average <b>${d.squad_average}</b></span></div>
    <div class="row">
      <div class="col"><div class="panel"><h3>Positions to save resources for</h3>
        <ul class="mini-list">${prio || "<li>No obvious weak spots — squad is balanced.</li>"}</ul></div></div>
      <div class="col" style="flex:2 1 520px"><div class="panel" style="padding:0;overflow-x:auto">
        <table><thead><tr><th>Slot</th><th>Starter</th><th class="num">Score</th><th class="num">vs avg</th><th>Flags</th></tr></thead>
        <tbody>${slots}</tbody></table></div></div>
    </div>`;
}

// ------------------------------------------------------------------ Bench
async function renderBench(app) {
  const d = await API.bench(7);
  const rows = d.bench.map((b) => `<tr class="clickable" data-id="${b.player_id}">
    <td><b>${esc(b.player_name)}</b></td>
    <td class="num rating ${ratingClass(b.ovr)}">${b.ovr}</td>
    <td>${(b.positions || []).map((x) => `<span class="chip pos">${esc(x)}</span>`).join("")}</td>
    <td><span class="chip pos">${esc(b.best_position)}</span></td>
    <td class="num rating ${ratingClass(b.best_score)}">${b.best_score.toFixed(1)}</td>
  </tr>`).join("");
  app.innerHTML = `
    <div class="section-title"><h2>Bench</h2><span class="hint">Your next 7 best players outside the XI (visibility only)</span></div>
    <div class="panel" style="padding:0;overflow-x:auto">
      <table><thead><tr><th>Name</th><th class="num">OVR</th><th>Positions</th><th>Best</th><th class="num">Score</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="5" class="empty-state">No bench players.</td></tr>`}</tbody></table></div>`;
  $$("tr[data-id]").forEach((tr) => (tr.onclick = () => openEditor(+tr.dataset.id)));
}

// ------------------------------------------------------------------ Rules
async function renderRules(app) {
  const files = ["formations", "stat_weights", "positions", "growth", "rankup", "skills", "playstyles", "costs", "attributes"];
  State._rulefile = State._rulefile || "costs";
  const data = await API.rule(State._rulefile);
  const verified = data.verified === true;
  const list = files.map((f) => `<div class="formation-item ${f === State._rulefile ? "active" : ""}" data-rf="${f}">
    <span class="fname">${f}.json</span>
    ${State.meta.unverified_files.includes(f) ? '<span class="badge warn">unverified</span>' : '<span class="badge ok">ok</span>'}</div>`).join("");
  app.innerHTML = `
    <div class="section-title"><h2>Rules &amp; tuning</h2>
      <span class="hint">Edit the JSON that drives scoring, formations and upgrade costs. Saved to <code>rules/</code>.</span></div>
    <div class="row">
      <div class="col" style="flex:0 0 220px"><div class="panel"><h3>Files</h3><div class="formation-list">${list}</div></div></div>
      <div class="col" style="flex:2 1 520px"><div class="panel">
        <h3>${State._rulefile}.json ${verified ? '<span class="badge ok">verified</span>' : '<span class="badge warn">unverified</span>'}</h3>
        <textarea id="rule-text" class="code">${esc(JSON.stringify(data, null, 2))}</textarea>
        <div class="toolbar" style="margin-top:10px">
          <button class="btn primary" id="rule-save">Save & recompute</button>
          <span class="hint">Tip: set <code>"verified": true</code> once you've confirmed the numbers to clear the badge.</span>
        </div>
      </div></div>
    </div>`;
  $$("[data-rf]").forEach((it) => (it.onclick = () => { State._rulefile = it.dataset.rf; persist(); renderRules(app); }));
  $("#rule-save").onclick = async () => {
    try {
      const parsed = JSON.parse($("#rule-text").value);
      const res = await API.saveRule(State._rulefile, parsed);
      State.meta.unverified_files = res.unverified_files;
      toast("Saved — recomputed on next view");
      renderRules(app);
    } catch (e) { toast("Invalid JSON: " + e.message, true); }
  };
}

// ------------------------------------------------------------------ Data
function renderData(app) {
  app.innerHTML = `
    <div class="section-title"><h2>Data — backup, import, export</h2></div>
    <div class="row">
      <div class="col"><div class="panel"><h3>Export</h3>
        <p class="hint">Download your collection to edit in a spreadsheet or keep as a backup.</p>
        <div class="toolbar">
          <a class="btn" href="/api/export/csv">Export CSV</a>
          <a class="btn" href="/api/export/json">Export JSON</a>
          <a class="btn" href="/api/backup/db">Download SQLite backup</a>
        </div></div></div>
      <div class="col"><div class="panel"><h3>Import CSV</h3>
        <p class="hint">Columns: name, ovr, rank, training_level, the six stats, positions (pipe-separated e.g. <code>ST|CF</code>),
        rankup_positions, playstyles (<code>Rapid+|Finesse Expert</code>), skill_points, notes.</p>
        <div class="field"><input type="file" id="csv-file" accept=".csv" /></div>
        <label><input type="checkbox" id="csv-replace" /> Replace my whole collection (otherwise append)</label>
        <div class="toolbar" style="margin-top:10px"><button class="btn primary" id="csv-import">Import</button></div>
      </div></div>
    </div>
    <div class="panel"><h3>Backing up</h3>
      <p class="hint">Everything lives in one file: <code>data/fcmobile.sqlite3</code>. Copy it anywhere to back up;
      drop it back to restore. The "Download SQLite backup" button above grabs a copy.</p></div>`;
  $("#csv-import").onclick = async () => {
    const f = $("#csv-file").files[0];
    if (!f) return toast("Choose a CSV file first", true);
    try {
      const res = await API.importCsv(f, $("#csv-replace").checked);
      await loadPlayers();
      toast(`Imported ${res.imported} players`);
      setView("players");
    } catch (e) { toast(e.message, true); }
  };
}

// ------------------------------------------------------------------ keys
function wireKeys() {
  document.addEventListener("keydown", (e) => {
    const drawerOpen = !$("#drawer").classList.contains("hidden");
    if (drawerOpen) {
      if (e.key === "Escape") $("#drawer").classList.add("hidden");
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) savePlayer();
      return;
    }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (typing) return;
    if (e.key === "r") render();
    if (e.key === "n") openEditor(null);
    const map = { "1": "squad", "2": "players", "3": "upgrades", "4": "gaps", "5": "bench", "6": "rules", "7": "data" };
    if (map[e.key]) setView(map[e.key]);
  });
}

boot();
