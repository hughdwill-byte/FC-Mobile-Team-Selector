/* FC Mobile Squad Optimizer - browser engine.
 * A client-side port of the Python backend: scoring, the Hungarian optimiser,
 * upgrade/training planners, gaps, bench and the takeover planner - all running in the
 * browser with data in localStorage. Exposes a global `API` matching the old REST client,
 * so the UI code is unchanged. No server required.
 */
(function () {
"use strict";

const MAIN_STATS = ["pace", "shooting", "passing", "dribbling", "defending", "physical"];

// ----------------------------------------------------------------- default rules
const DEFAULT_RULES = {
  positions: {
    verified: false,
    positions: ["GK","RB","LB","CB","RWB","LWB","CDM","CM","CAM","RM","LM","RW","LW","CF","ST"],
    out_of_position_penalty: 0.82,
    gk_mismatch_penalty: 0.05,
  },
  stat_weights: {
    verified: false,
    ovr_weight: 0.7,
    stats: MAIN_STATS.slice(),
    weights: {
      DEFAULT: { pace:0.2, shooting:0.15, passing:0.2, dribbling:0.2, defending:0.1, physical:0.15 },
      GK:  { pace:0.20, shooting:0.18, passing:0.05, dribbling:0.25, defending:0.22, physical:0.10 },
      ST:  { pace:0.20, shooting:0.35, passing:0.05, dribbling:0.20, defending:0.00, physical:0.20 },
      CF:  { pace:0.15, shooting:0.30, passing:0.15, dribbling:0.25, defending:0.00, physical:0.15 },
      RW:  { pace:0.30, shooting:0.20, passing:0.10, dribbling:0.30, defending:0.00, physical:0.10 },
      LW:  { pace:0.30, shooting:0.20, passing:0.10, dribbling:0.30, defending:0.00, physical:0.10 },
      RM:  { pace:0.25, shooting:0.12, passing:0.23, dribbling:0.25, defending:0.05, physical:0.10 },
      LM:  { pace:0.25, shooting:0.12, passing:0.23, dribbling:0.25, defending:0.05, physical:0.10 },
      CAM: { pace:0.10, shooting:0.20, passing:0.30, dribbling:0.30, defending:0.00, physical:0.10 },
      CM:  { pace:0.10, shooting:0.10, passing:0.30, dribbling:0.20, defending:0.15, physical:0.15 },
      CDM: { pace:0.05, shooting:0.05, passing:0.20, dribbling:0.10, defending:0.35, physical:0.25 },
      RB:  { pace:0.25, shooting:0.03, passing:0.20, dribbling:0.12, defending:0.25, physical:0.15 },
      LB:  { pace:0.25, shooting:0.03, passing:0.20, dribbling:0.12, defending:0.25, physical:0.15 },
      RWB: { pace:0.28, shooting:0.05, passing:0.22, dribbling:0.15, defending:0.18, physical:0.12 },
      LWB: { pace:0.28, shooting:0.05, passing:0.22, dribbling:0.15, defending:0.18, physical:0.12 },
      CB:  { pace:0.10, shooting:0.00, passing:0.08, dribbling:0.05, defending:0.42, physical:0.35 },
    },
  },
  formations: {
    verified: false,
    formations: [
      { name:"4-4-2",            slots:["GK","RB","CB","CB","LB","RM","CM","CM","LM","ST","ST"] },
      { name:"4-4-1-1",          slots:["GK","RB","CB","CB","LB","RM","CM","CM","LM","CF","ST"] },
      { name:"4-3-3",            slots:["GK","RB","CB","CB","LB","CM","CM","CM","RW","ST","LW"] },
      { name:"4-3-3 (Defend)",   slots:["GK","RB","CB","CB","LB","CDM","CM","CM","RW","ST","LW"] },
      { name:"4-3-3 (Attack)",   slots:["GK","RB","CB","CB","LB","CM","CM","CAM","RW","ST","LW"] },
      { name:"4-2-3-1",          slots:["GK","RB","CB","CB","LB","CDM","CDM","RW","CAM","LW","ST"] },
      { name:"4-2-3-1 (Wide)",   slots:["GK","RB","CB","CB","LB","CDM","CDM","RM","CAM","LM","ST"] },
      { name:"4-1-2-1-2 (Diamond)",slots:["GK","RB","CB","CB","LB","CDM","CM","CM","CAM","ST","ST"] },
      { name:"4-3-1-2",          slots:["GK","RB","CB","CB","LB","CM","CM","CM","CAM","ST","ST"] },
      { name:"4-5-1",            slots:["GK","RB","CB","CB","LB","RM","CM","CM","CM","LM","ST"] },
      { name:"4-5-1 (Attack)",   slots:["GK","RB","CB","CB","LB","RM","CM","CAM","CM","LM","ST"] },
      { name:"4-1-4-1",          slots:["GK","RB","CB","CB","LB","CDM","RM","CM","CM","LM","ST"] },
      { name:"4-2-2-2",          slots:["GK","RB","CB","CB","LB","CDM","CDM","CAM","CAM","ST","ST"] },
      { name:"4-2-4",            slots:["GK","RB","CB","CB","LB","CM","CM","RW","LW","ST","ST"] },
      { name:"4-3-2-1 (Tree)",   slots:["GK","RB","CB","CB","LB","CDM","CM","CM","CAM","CAM","ST"] },
      { name:"3-5-2",            slots:["GK","CB","CB","CB","RM","CDM","CM","CM","LM","ST","ST"] },
      { name:"3-4-3",            slots:["GK","CB","CB","CB","RM","CM","CM","LM","RW","ST","LW"] },
      { name:"3-4-1-2",          slots:["GK","CB","CB","CB","RM","CM","CM","LM","CAM","ST","ST"] },
      { name:"3-4-2-1",          slots:["GK","CB","CB","CB","RM","CM","CM","LM","CAM","CAM","ST"] },
      { name:"5-3-2",            slots:["GK","RWB","CB","CB","CB","LWB","CM","CM","CM","ST","ST"] },
      { name:"5-4-1",            slots:["GK","RWB","CB","CB","CB","LWB","RM","CM","CM","LM","ST"] },
      { name:"5-2-1-2",          slots:["GK","RWB","CB","CB","CB","LWB","CM","CM","CAM","ST","ST"] },
      { name:"5-2-3",            slots:["GK","RWB","CB","CB","CB","LWB","CM","CM","RW","ST","LW"] },
    ],
  },
  growth: {
    verified: false,
    default_gain_per_level: { pace:0.4, shooting:0.4, passing:0.4, dribbling:0.4, defending:0.4, physical:0.4 },
    // Flat training boost added to every face stat at each training level (index = level 0..30).
    // Community-compiled from FC Mobile; the boost is not linear (some levels add nothing, others add more),
    // so a card's trained stat is base_stat + training_boost[level]. Used when base stats are known;
    // if a player has a per-stat growth_override that takes precedence for that stat.
    training_boost: [0,1,1,2,2,3,3,4,4,5,6,6,7,7,8,9,9,10,10,11,12,12,13,13,14,15,15,16,16,17,18],
    max_training_level: 30,
    rankup_unlocks_every_levels: 5,
  },
  rankup: { verified:false, max_rank:5, ovr_gain:[1,1,1,1,1], stat_gain_per_rank:1.0 },
  skills: {
    verified: false,
    max_skill_points_per_player: 5,
    skill_point_per_rankup: 1,
    ovr_scaled_gain: { bands: [
      { max_ovr:74, normal:1, advanced:2 },
      { max_ovr:84, normal:3, advanced:6 },
      { max_ovr:200, normal:5, advanced:10 },
    ]},
    position_priority: {
      GK:["dribbling","pace","defending","shooting","physical","passing"],
      ST:["shooting","pace","dribbling","physical","passing","defending"],
      CF:["shooting","dribbling","passing","pace","physical","defending"],
      RW:["pace","dribbling","shooting","passing","physical","defending"],
      LW:["pace","dribbling","shooting","passing","physical","defending"],
      RM:["pace","dribbling","passing","shooting","physical","defending"],
      LM:["pace","dribbling","passing","shooting","physical","defending"],
      CAM:["passing","dribbling","shooting","pace","physical","defending"],
      CM:["passing","dribbling","physical","defending","pace","shooting"],
      CDM:["defending","physical","passing","pace","dribbling","shooting"],
      RB:["pace","defending","passing","physical","dribbling","shooting"],
      LB:["pace","defending","passing","physical","dribbling","shooting"],
      RWB:["pace","passing","defending","dribbling","physical","shooting"],
      LWB:["pace","passing","defending","dribbling","physical","shooting"],
      CB:["defending","physical","pace","passing","dribbling","shooting"],
      DEFAULT:["pace","dribbling","passing","shooting","physical","defending"],
    },
  },
  playstyles: {
    verified: false,
    plus_multiplier: 2.0,
    styles: {
      "Rapid":{category:"Ball Control",pace:3},
      "Trickster":{category:"Ball Control",dribbling:3},
      "Technical":{category:"Ball Control",dribbling:2,passing:1},
      "Tiki Taka":{category:"Passing",passing:2,dribbling:1},
      "Bullet Pass":{category:"Passing",passing:3},
      "Whipped Crosser":{category:"Passing",passing:2,pace:1},
      "Finesse Expert":{category:"Finishing",shooting:3},
      "Clinical Finisher":{category:"Finishing",shooting:3},
      "Power Shot":{category:"Finishing",shooting:2,physical:1},
      "Penalty Expert":{category:"Finishing",shooting:1},
      "Chip Shot":{category:"Finishing",shooting:2},
      "Anticipate":{category:"Defending",defending:3},
      "Guardian":{category:"Defending",defending:2,physical:1},
      "Acceleration":{category:"Physical",pace:2},
      "Relentless":{category:"Physical",physical:2,pace:1},
      "Precision Header":{category:"Physical",physical:2,shooting:1},
      "Bruiser":{category:"Physical",physical:3},
      "Deflector":{category:"Goalkeeping",defending:2,dribbling:1},
      "Rush Out":{category:"Goalkeeping",pace:2,dribbling:1},
    },
  },
  costs: {
    verified: false,
    // XP to advance from level L to L+1 (index 0 = level 0->1). FC Mobile training-XP curve
    // (community-compiled); it climbs steeply so the last few levels dominate the cost.
    training: { per_level: [100,120,150,200,270,350,440,540,660,800,950,1120,1300,1550,1900,2300,2800,3400,4100,5000,6100,7400,8900,10700,12800,15300,18300,21800,25900,30700] },
    rankup: { per_rank: [1,2,4,7,12] },
    skill: { per_point: 1 },
    training_transfer: { transfer_fee_pct: 0.1, tt_point_cost_per_level: 1 },
    normalization: { training_unit:1.0, rankup_unit:200.0, skill_unit:100.0 },
  },
  attributes: { verified:false },
};
const RULE_NAMES = Object.keys(DEFAULT_RULES);

// ----------------------------------------------------------------- FC Mobile reference data (community-compiled)
// Training XP required to reach each level (from the level below it). Level 30 is the max.
const XP_PER_LEVEL = {1:100,2:120,3:150,4:200,5:270,6:350,7:440,8:540,9:660,10:800,
  11:950,12:1120,13:1300,14:1550,15:1900,16:2300,17:2800,18:3400,19:4100,20:5000,
  21:6100,22:7400,23:8900,24:10700,25:12800,26:15300,27:18300,28:21800,29:25900,30:30700};
// Cumulative XP to reach a given level from a fresh level 0 card.
function xpToReach(level) { let t = 0; for (let l = 1; l <= level; l++) t += (XP_PER_LEVEL[l] || 0); return t; }
// Training XP a "food" card yields when fed into another player, by the food card's base OVR.
// A card on a green (in-form) rank yields the boosted amount instead of the base.
const XP_YIELD_BANDS = [
  { max_ovr:64,  base_xp:120,  green_xp:360 },
  { max_ovr:69,  base_xp:160,  green_xp:480 },
  { max_ovr:74,  base_xp:200,  green_xp:600 },
  { max_ovr:79,  base_xp:250,  green_xp:750 },
  { max_ovr:84,  base_xp:500,  green_xp:1500 },
  { max_ovr:89,  base_xp:800,  green_xp:2400 },
  { max_ovr:200, base_xp:1500, green_xp:4500 },
];
function foodXp(ovr, green) {
  for (const b of XP_YIELD_BANDS) if (ovr <= b.max_ovr) return green ? b.green_xp : b.base_xp;
  const b = XP_YIELD_BANDS[XP_YIELD_BANDS.length - 1]; return green ? b.green_xp : b.base_xp;
}

// Rank-up skill points apply a percentage multiplier to a card's face stats (secondary attributes),
// +5% per point up to a +15% cap. Used to reconstruct a fully-trained card's displayed stats.
const SKILL_POINT_PCT_PER = 0.05, SKILL_POINT_PCT_CAP = 0.15;
function skillPointMultiplier(points) { return 1 + Math.min(SKILL_POINT_PCT_CAP, Math.max(0, points) * SKILL_POINT_PCT_PER); }

// Per-position skills (community-compiled). Basic skills level 1-3 give +5%/level to their sub-attributes;
// advanced skills (rank 4+) give a flat +10 to a wider set. Sub-attributes are grouped under the app's six
// face stats via SUBATTR_TO_MAIN so the effect can be expressed in this model. Aliases share a position's tree.
const SKILLS_DB = {
  "ST": { basic: { Dexterity:["Acceleration","Sprint Speed","Agility"], Shooting:["Finishing","Shot Power","Long Shot"], Passing:["Vision","Short Passing","Long Passing"] } },
  "RW": { basic: { Dexterity:["Acceleration","Sprint Speed","Agility"], Dribbling:["Agility","Dribbling","Ball Control"], Passing:["Crossing","Short Passing","Long Passing"] } },
  "LW": { alias:"RW" }, "LM": { alias:"RM" },
  "RM": { basic: { Dexterity:["Acceleration","Sprint Speed","Agility"], Dribbling:["Agility","Dribbling","Ball Control"], Passing:["Crossing","Short Passing","Long Passing"] } },
  "CAM": { basic: { Shooting:["Finishing","Shot Power","Long Shot"], Passing:["Vision","Short Passing","Long Passing"], Dribbling:["Agility","Dribbling","Ball Control"] } },
  "CM": { basic: { Passing:["Vision","Short Passing","Long Passing"], Dribbling:["Agility","Dribbling","Ball Control"], Defending:["Interceptions","Standing Tackle","Defensive Awareness"] } },
  "CDM": { basic: { Defending:["Interceptions","Standing Tackle","Defensive Awareness"], Physical:["Strength","Stamina","Aggression"], Passing:["Vision","Short Passing","Long Passing"] } },
  "CB": { basic: { Defending:["Interceptions","Standing Tackle","Sliding Tackle"], Physical:["Strength","Jumping","Aggression"], Heading:["Heading Accuracy","Jumping","Strength"] } },
  "RB": { basic: { Pace:["Acceleration","Sprint Speed"], Defending:["Interceptions","Standing Tackle","Defensive Awareness"], Passing:["Crossing","Short Passing","Long Passing"] } },
  "LB": { alias:"RB" }, "LWB": { alias:"RB" }, "RWB": { alias:"RB" },
  "GK": { basic: { Reflexes:["Reflexes","Diving"], Handling:["Handling","Kicking"], Positioning:["Positioning","Speed"] } },
};
function skillsForPosition(pos) {
  let node = SKILLS_DB[pos]; let guard = 0;
  while (node && node.alias && guard++ < 4) node = SKILLS_DB[node.alias];
  return node || null;
}
// Group the skills' sub-attributes under the six face stats this app models.
const SUBATTR_TO_MAIN = {
  "Acceleration":"pace","Sprint Speed":"pace","Speed":"pace",
  "Finishing":"shooting","Shot Power":"shooting","Long Shot":"shooting","Volleys":"shooting","Positioning":"shooting","Curve":"shooting",
  "Vision":"passing","Short Passing":"passing","Long Passing":"passing","Crossing":"passing",
  "Agility":"dribbling","Dribbling":"dribbling","Ball Control":"dribbling","Balance":"dribbling","Reactions":"dribbling",
  "Interceptions":"defending","Standing Tackle":"defending","Sliding Tackle":"defending","Defensive Awareness":"defending","Heading Accuracy":"defending",
  "Strength":"physical","Stamina":"physical","Aggression":"physical","Jumping":"physical",
  // GK sub-attributes reuse the six-slot GK mapping (see README): Diving=pace, Handling=shooting, Kicking=passing, Reflexes=dribbling, Positioning=defending.
  "Diving":"pace","Handling":"shooting","Kicking":"passing","Reflexes":"dribbling",
};
// Which face stats a position's basic skills can raise (used to sharpen skill-point recommendations).
function skillMainStats(pos) {
  const node = skillsForPosition(pos); if (!node || !node.basic) return [];
  const out = [];
  Object.values(node.basic).forEach((subs) => subs.forEach((s) => {
    const m = SUBATTR_TO_MAIN[s]; if (m && out.indexOf(m) < 0) out.push(m);
  }));
  return out;
}

// ----------------------------------------------------------------- rules store (localStorage overrides)
const LS_RULES = "fcm.rules.overrides";
function ruleOverrides() {
  try { return JSON.parse(localStorage.getItem(LS_RULES) || "{}"); } catch (e) { return {}; }
}
function loadRule(name) {
  const ov = ruleOverrides();
  return ov[name] !== undefined ? ov[name] : DEFAULT_RULES[name];
}
function saveRuleData(name, data) {
  const ov = ruleOverrides();
  ov[name] = data;
  localStorage.setItem(LS_RULES, JSON.stringify(ov));
}
function unverifiedFiles() {
  return RULE_NAMES.filter((n) => !(loadRule(n) || {}).verified);
}

// ----------------------------------------------------------------- players store
const LS_PLAYERS = "fcm.players";
function loadPlayers() {
  try { return JSON.parse(localStorage.getItem(LS_PLAYERS) || "[]"); } catch (e) { return []; }
}
function savePlayers(list) { localStorage.setItem(LS_PLAYERS, JSON.stringify(list)); }
function nextId(list) { return list.reduce((m, p) => Math.max(m, p.id || 0), 0) + 1; }

const EDITABLE = ["name","ovr","rank","training_level", ...MAIN_STATS, "base_stats",
  "positions","rankup_positions","playstyles","growth_override","skill_points","notes","variant"];
function coerce(k, v) {
  if (v === null || v === undefined) return null;
  if (["ovr","rank","training_level","skill_points"].includes(k)) { const n = parseInt(v, 10); return isNaN(n) ? 0 : n; }
  if (MAIN_STATS.includes(k)) { const n = parseFloat(v); return isNaN(n) ? 0 : n; }
  return v;
}
function newPlayer() {
  return { id:null, name:"", ovr:50, rank:0, training_level:0,
    pace:50, shooting:50, passing:50, dribbling:50, defending:50, physical:50,
    base_stats:null, positions:[], rankup_positions:[], playstyles:[],
    growth_override:null, skill_points:0, notes:"", variant:"" };
}
function applyData(p, data) {
  EDITABLE.forEach((k) => { if (k in data && data[k] !== null && data[k] !== undefined) p[k] = coerce(k, data[k]); });
  return p;
}

// ----------------------------------------------------------------- scoring
function playerToState(p) {
  const gdef = loadRule("growth").default_gain_per_level;
  const growth = Object.assign({}, gdef);
  if (p.growth_override) for (const k in p.growth_override) if (p.growth_override[k] != null) growth[k] = p.growth_override[k];
  const stats = {}; MAIN_STATS.forEach((s) => stats[s] = Number(p[s]) || 0);
  const base = {}; if (p.base_stats) MAIN_STATS.forEach((s) => { if (p.base_stats[s] != null) base[s] = Number(p.base_stats[s]); });
  return {
    id: p.id, name: p.name, ovr: Number(p.ovr) || 0, rank: Number(p.rank) || 0,
    training_level: Number(p.training_level) || 0, stats,
    positions: (p.positions || []).slice(), rankup_positions: (p.rankup_positions || []).slice(),
    playstyles: (p.playstyles || []).map((x) => Object.assign({}, x)), growth,
    growth_override: p.growth_override || null,
    skill_points: Number(p.skill_points) || 0, base_stats: base,
  };
}
function copyState(s) {
  return { id:s.id, name:s.name, ovr:s.ovr, rank:s.rank, training_level:s.training_level,
    stats:Object.assign({}, s.stats), positions:s.positions.slice(), rankup_positions:s.rankup_positions.slice(),
    playstyles:s.playstyles.map((x)=>Object.assign({},x)), growth:Object.assign({}, s.growth),
    growth_override: s.growth_override ? Object.assign({}, s.growth_override) : null,
    skill_points:s.skill_points, base_stats:Object.assign({}, s.base_stats) };
}
function effectiveStats(state) {
  const ps = loadRule("playstyles"); const styles = ps.styles || {}; const pm = ps.plus_multiplier || 2.0;
  const out = Object.assign({}, state.stats);
  (state.playstyles || []).forEach((p) => {
    const d = styles[p.name]; if (!d) return;
    const mult = p.plus ? pm : 1.0;
    for (const stat in d) { if (MAIN_STATS.includes(stat) && typeof d[stat] === "number") out[stat] = (out[stat] || 0) + d[stat] * mult; }
  });
  const r = {}; MAIN_STATS.forEach((s) => r[s] = Math.max(0, out[s] || 0));
  return r;
}
function normWeights(pos) {
  const w = loadRule("stat_weights").weights; const src = w[pos] || w.DEFAULT;
  let total = 0; MAIN_STATS.forEach((s) => total += (src[s] || 0)); if (!total) total = 1;
  const r = {}; MAIN_STATS.forEach((s) => r[s] = (src[s] || 0) / total); return r;
}
function ovrWeight() { const w = loadRule("stat_weights").ovr_weight; const n = (w === undefined ? 0.7 : w); return Math.min(1, Math.max(0, n)); }
function isGk(state) { return state.positions.indexOf("GK") >= 0; }
function gkRating(state) {
  let sum = 0; MAIN_STATS.forEach((s) => sum += (state.stats[s] || 0));
  if (sum < 1e-6) return state.ovr;
  const eff = effectiveStats(state); const w = normWeights("GK");
  let r = 0; MAIN_STATS.forEach((s) => r += eff[s] * w[s]); return r;
}
function slotScore(state, position) {
  const pr = loadRule("positions");
  const oop = pr.out_of_position_penalty != null ? pr.out_of_position_penalty : 0.82;
  const gkp = pr.gk_mismatch_penalty != null ? pr.gk_mismatch_penalty : 0.05;
  const ow = ovrWeight();
  if (position === "GK") {
    if (!isGk(state)) return state.ovr * gkp;
    return ow * state.ovr + (1 - ow) * gkRating(state);
  }
  let factor;
  if (isGk(state) && state.positions.length === 1) factor = gkp;
  else if (state.positions.indexOf(position) >= 0) factor = 1.0;
  else factor = oop;
  const eff = effectiveStats(state); const w = normWeights(position);
  let sr = 0; MAIN_STATS.forEach((s) => sr += eff[s] * w[s]);
  return (ow * state.ovr + (1 - ow) * sr) * factor;
}
function bestPositionScore(state) {
  const cands = state.positions.length ? state.positions : ["ST"];
  let bp = cands[0], best = -1;
  cands.forEach((pos) => { const sc = slotScore(state, pos); if (sc > best) { best = sc; bp = pos; } });
  return [bp, best];
}

// upgrade simulation
function withTrainingLevel(state, delta) {
  const g = loadRule("growth");
  const maxL = g.max_training_level || 30;
  const nl = state.training_level + delta;
  if (nl > maxL || delta <= 0) return null;
  const ns = copyState(state); ns.training_level = nl;
  const boost = g.training_boost;
  const ov = state.growth_override || null;
  const boostAt = (lvl) => (Array.isArray(boost) && boost.length) ? (lvl < boost.length ? boost[lvl] : boost[boost.length - 1]) : null;
  const flatFrom = boostAt(state.training_level), flatTo = boostAt(nl);
  MAIN_STATS.forEach((s) => {
    if (ov && ov[s] != null) ns.stats[s] = ns.stats[s] + Number(ov[s]) * delta;   // player-specific per-level growth
    else if (flatTo != null) ns.stats[s] = ns.stats[s] + (flatTo - flatFrom);      // community flat training boost
    else ns.stats[s] = ns.stats[s] + (ns.growth[s] || 0) * delta;                  // fallback linear model
  });
  return ns;
}
// Advance training to the next level where stats actually change (the boost curve has "dead" levels that
// add nothing, so a plain +1 can yield zero gain). Returns the multi-level jump, its bundled XP cost, and
// the target level - so planners never stall on a flat step.
function trainStep(state) {
  const g = loadRule("growth"); const maxL = g.max_training_level || 30;
  if (state.training_level >= maxL) return null;
  const boost = g.training_boost, ov = state.growth_override || null;
  const tC = loadRule("costs").training.per_level;
  let target = state.training_level + 1;
  if (Array.isArray(boost) && boost.length && !ov) {
    const cur = state.training_level < boost.length ? boost[state.training_level] : boost[boost.length - 1];
    while (target <= maxL) { const b = target < boost.length ? boost[target] : boost[boost.length - 1]; if (b > cur) break; target++; }
    if (target > maxL) return null;
  }
  const ns = withTrainingLevel(state, target - state.training_level); if (!ns) return null;
  let xp = 0; for (let l = state.training_level; l < target; l++) xp += (l < tC.length ? tC[l] : tC[tC.length - 1]);
  return { ns, xp, levels: target - state.training_level, to_level: target };
}
// ----------------------------------------------------------------- Team OVR (FC Mobile roster metric)
// Team OVR = ceil(average base OVR) + ceil(average rank). Training level and skill points are excluded;
// only the card's base OVR and its integer rank (0-5) count. A weak bench card drags both averages down.
function teamOvrOf(states) {
  const n = states.length;
  if (!n) return { team_ovr:0, base_ovr_component:0, rank_component:0, avg_base_ovr:0, avg_rank:0, size:0, next_ovr_breakpoint:0, next_rank_breakpoint:0 };
  let so = 0, sr = 0; states.forEach((s) => { so += Number(s.ovr) || 0; sr += Number(s.rank) || 0; });
  const oc = Math.ceil(so / n), rc = Math.ceil(sr / n);
  const baseRem = so % n, rankRem = sr % n;
  return { team_ovr: oc + rc, base_ovr_component: oc, rank_component: rc, avg_base_ovr: so / n, avg_rank: sr / n, size: n,
    next_ovr_breakpoint: baseRem === 0 ? n : n - baseRem, next_rank_breakpoint: rankRem === 0 ? n : n - rankRem };
}
// The squad (11-18 cards) that maximises Team OVR: start with the best 11 by OVR, then keep adding the next
// card only while it doesn't lower the metric. You never have to fill all 18 slots.
function bestTeamOvr(states) {
  const sorted = states.slice().sort((a, b) => (Number(b.ovr) - Number(a.ovr)) || (Number(b.rank) - Number(a.rank)));
  if (sorted.length <= 11) { const t = teamOvrOf(sorted); t.included = sorted.map((s) => s.id); t.squad_size = sorted.length; return t; }
  let cur = sorted.slice(0, 11), best = teamOvrOf(cur).team_ovr;
  for (let k = 11; k < Math.min(18, sorted.length); k++) {
    const trial = sorted.slice(0, k + 1), m = teamOvrOf(trial).team_ovr;
    if (m >= best) { cur = trial; best = m; } else break;
  }
  const t = teamOvrOf(cur); t.included = cur.map((s) => s.id); t.squad_size = cur.length; return t;
}
function withRankup(state) {
  const ru = loadRule("rankup"); const maxR = ru.max_rank || 5;
  if (state.rank >= maxR) return null;
  const ns = copyState(state);
  const og = ru.ovr_gain || [1,1,1,1,1];
  ns.ovr += (state.rank < og.length ? og[state.rank] : 1);
  const bump = ru.stat_gain_per_rank || 0;
  MAIN_STATS.forEach((s) => ns.stats[s] += bump);
  ns.rank += 1;
  ns.rankup_positions.forEach((pos) => { if (ns.positions.indexOf(pos) < 0) ns.positions.push(pos); });
  ns.rankup_positions = [];
  return ns;
}
function skillPointGain(ovr) {
  const bands = (loadRule("skills").ovr_scaled_gain || {}).bands || [{max_ovr:200,normal:1}];
  for (const b of bands) if (ovr <= b.max_ovr) return b.normal;
  return bands[bands.length - 1].normal;
}
function withSkillPoint(state, stat) {
  if (state.skill_points <= 0 || MAIN_STATS.indexOf(stat) < 0) return null;
  const ns = copyState(state); ns.stats[stat] += skillPointGain(state.ovr); ns.skill_points -= 1; return ns;
}
function priorityStats(state) {
  const ps = loadRule("playstyles"); const styles = ps.styles || {}; const pm = ps.plus_multiplier || 2.0;
  const boost = {}; MAIN_STATS.forEach((s) => boost[s] = 0);
  (state.playstyles || []).forEach((p) => { const d = styles[p.name]; if (!d) return; const m = p.plus ? pm : 1.0;
    for (const st in d) if (MAIN_STATS.includes(st) && typeof d[st] === "number") boost[st] += d[st] * m; });
  const psOrder = MAIN_STATS.filter((s) => boost[s] > 0).sort((a, b) => boost[b] - boost[a]);
  const pos = state.positions.length ? state.positions[0] : "DEFAULT";
  // Face stats the position's actual in-game skills can raise come first (grounded in the skills database),
  // then the tuned position priority, then everything else as a fallback.
  const skillOrder = skillMainStats(pos);
  const pm2 = loadRule("skills").position_priority || {};
  const posOrder = pm2[pos] || pm2.DEFAULT || MAIN_STATS;
  const out = [];
  [...psOrder, ...skillOrder, ...posOrder, ...MAIN_STATS].forEach((s) => { if (MAIN_STATS.includes(s) && out.indexOf(s) < 0) out.push(s); });
  return out;
}
function fullyRankedUp(state) {
  const maxR = loadRule("rankup").max_rank || 5;
  let s = state, guard = 0;
  while (s.rank < maxR && guard < 20) { const n = withRankup(s); if (!n) break; s = n; guard++; }
  return s;
}
function potentialState(state) {
  const maxL = loadRule("growth").max_training_level || 30;
  let ns = copyState(state);
  const base = state.base_stats || {};
  if (MAIN_STATS.some((s) => base[s])) {
    MAIN_STATS.forEach((s) => ns.stats[s] = base[s] != null ? Number(base[s]) : (ns.stats[s] || 0));
    ns.training_level = 0;
    const t = withTrainingLevel(ns, maxL); if (t) ns = t;
  }
  return fullyRankedUp(ns);
}

// ----------------------------------------------------------------- Hungarian (min cost, rows<=cols)
function assignMinCost(a) {
  const n = a.length, m = a[0].length; const INF = Infinity;
  const u = new Array(n + 1).fill(0), v = new Array(m + 1).fill(0);
  const p = new Array(m + 1).fill(0), way = new Array(m + 1).fill(0);
  for (let i = 1; i <= n; i++) {
    p[0] = i; let j0 = 0;
    const minv = new Array(m + 1).fill(INF), used = new Array(m + 1).fill(false);
    do {
      used[j0] = true; const i0 = p[j0]; let delta = INF, j1 = -1;
      for (let j = 1; j <= m; j++) if (!used[j]) {
        const cur = a[i0 - 1][j - 1] - u[i0] - v[j];
        if (cur < minv[j]) { minv[j] = cur; way[j] = j0; }
        if (minv[j] < delta) { delta = minv[j]; j1 = j; }
      }
      for (let j = 0; j <= m; j++) {
        if (used[j]) { u[p[j]] += delta; v[j] -= delta; } else { minv[j] -= delta; }
      }
      j0 = j1;
    } while (p[j0] !== 0);
    do { const j1 = way[j0]; p[j0] = p[j1]; j0 = j1; } while (j0);
  }
  const result = new Array(n).fill(-1);
  for (let j = 1; j <= m; j++) if (p[j] > 0 && p[j] <= n) result[p[j] - 1] = j - 1;
  return result;
}

// ----------------------------------------------------------------- optimizer
function scoreByPosition(states, positions) {
  const table = {};
  positions.forEach((pos) => { table[pos] = states.map((s) => slotScore(s, pos)); });
  return table;
}
function solveFormation(states, formation, scoreTable) {
  const slots = formation.slots, nPlayers = states.length, nSlots = slots.length;
  const m = Math.max(nPlayers, nSlots);
  // cost matrix rows = slots (nSlots), cols = players padded to m
  const cost = [];
  for (let i = 0; i < nSlots; i++) {
    const row = new Array(m).fill(0);
    const col = scoreTable[slots[i]];
    for (let j = 0; j < nPlayers; j++) row[j] = -col[j];
    cost.push(row);
  }
  const assign = assignMinCost(cost); // assign[slotIndex] = player col (or dummy >= nPlayers)
  const chosenRows = new Set();
  assign.forEach((j) => { if (j >= 0 && j < nPlayers) chosenRows.add(j); });

  const slotsOut = []; let total = 0;
  for (let i = 0; i < nSlots; i++) {
    const pos = slots[i]; const col = scoreTable[pos];
    let ruId = null, ruName = null, ruScore = null, bestRu = -1;
    for (let k = 0; k < nPlayers; k++) {
      if (chosenRows.has(k)) continue;
      if (col[k] > bestRu) { bestRu = col[k]; ruId = states[k].id; ruName = states[k].name; ruScore = col[k]; }
    }
    const j = assign[i];
    if (j < 0 || j >= nPlayers) {
      slotsOut.push({ slot_index:i, position:pos, player_id:null, player_name:"(empty)", score:0, ovr:null,
        runner_up_id:ruId, runner_up_name:ruName, runner_up_score:ruScore });
    } else {
      const st = states[j]; const sc = col[j]; total += sc;
      slotsOut.push({ slot_index:i, position:pos, player_id:st.id, player_name:st.name, score:sc, ovr:st.ovr,
        runner_up_id:ruId, runner_up_name:ruName, runner_up_score:ruScore });
    }
  }
  return { formation: formation.name, total, slots: slotsOut };
}
function optimize(states, topN) {
  const forms = loadRule("formations").formations;
  const posSet = {}; forms.forEach((f) => f.slots.forEach((p) => posSet[p] = true));
  const table = scoreByPosition(states, Object.keys(posSet));
  const results = forms.map((f) => solveFormation(states, f, table));
  results.sort((a, b) => b.total - a.total);
  return results.slice(0, topN || 5);
}
function solveNamed(states, name) {
  const f = loadRule("formations").formations.find((x) => x.name === name);
  if (!f) return null;
  const posSet = {}; f.slots.forEach((p) => posSet[p] = true);
  return solveFormation(states, f, scoreByPosition(states, Object.keys(posSet)));
}
function bestSquadScore(states) { const t = optimize(states, 1); return t.length ? t[0].total : 0; }

// ----------------------------------------------------------------- serialization
function playerOut(p) {
  const st = playerToState(p); const [bp, bs] = bestPositionScore(st); const eff = effectiveStats(st);
  const out = { is_gk: (p.positions || []).indexOf("GK") >= 0, id: p.id, name: p.name, ovr: p.ovr,
    rank: p.rank, training_level: p.training_level };
  MAIN_STATS.forEach((s) => out[s] = p[s]);
  out.effective_stats = {}; MAIN_STATS.forEach((s) => out.effective_stats[s] = Math.round(eff[s] * 10) / 10);
  out.base_stats = p.base_stats || null;
  out.positions = p.positions || []; out.rankup_positions = p.rankup_positions || [];
  out.playstyles = p.playstyles || []; out.growth_override = p.growth_override || null;
  out.skill_points = p.skill_points; out.notes = p.notes || ""; out.variant = p.variant || "";
  out.best_position = bp; out.best_score = Math.round(bs * 100) / 100;
  return out;
}
const r2 = (x) => Math.round(x * 100) / 100;
const r3 = (x) => Math.round(x * 1000) / 1000;
function statesFromStore() { return loadPlayers().map(playerToState); }

// ----------------------------------------------------------------- upgrades
function planUpgrades(states, limit) {
  limit = limit || 40;
  const costs = loadRule("costs"); const tC = costs.training.per_level, rC = costs.rankup.per_rank, sC = costs.skill.per_point;
  const norm = costs.normalization || {};
  const unit = { training: norm.training_unit || 1, rankup: norm.rankup_unit || 1, skill: norm.skill_unit || 1 };
  const maxL = loadRule("growth").max_training_level || 30, maxR = loadRule("rankup").max_rank || 5;
  const baseline = bestSquadScore(states);
  const cands = [];
  function swap(i, ns) { const c = states.slice(); c[i] = ns; return c; }
  function add(kind, idx, state, ns, rawCost, label, detail) {
    if (!ns) return;
    const newScore = bestSquadScore(swap(idx, ns));
    const gain = newScore - baseline;
    const combined = rawCost * unit[kind];
    const gpc = combined > 0 ? gain / combined : 0;
    cands.push({ kind, player_id:state.id, player_name:state.name, label, detail,
      gain: r3(gain), raw_cost: rawCost,
      cost_currency: {training:"XP",rankup:"rank items",skill:"skill points"}[kind],
      combined_cost: r2(combined), gain_per_cost: Math.round(gpc*1e5)/1e5, new_squad_score: r3(newScore),
      apply: { kind, new_training_level: ns.training_level, new_rank: ns.rank, new_skill_points: ns.skill_points,
        ovr_delta: r2(ns.ovr - state.ovr),
        stat_deltas: (function(){ const d={}; MAIN_STATS.forEach((s)=>d[s]=r2(ns.stats[s]-state.stats[s])); return d; })(),
        unlocked_positions: ns.positions.filter((p)=>state.positions.indexOf(p)<0) } });
  }
  states.forEach((st, idx) => {
    if (st.training_level < maxL) { const lvl = st.training_level; const step = trainStep(st);
      if (step) add("training", idx, st, step.ns, step.xp, `Train ${st.name} to level ${step.to_level}`, `Training level ${lvl} -> ${step.to_level}`); }
    if (st.rank < maxR) { const raw = st.rank < rC.length ? rC[st.rank] : rC[rC.length-1];
      add("rankup", idx, st, withRankup(st), raw, `Rank up ${st.name} to rank ${st.rank+1}`, `Rank ${st.rank} -> ${st.rank+1}`); }
    if (st.skill_points > 0) { const stat = priorityStats(st)[0]; const ns = withSkillPoint(st, stat);
      add("skill", idx, st, ns, sC, `Spend 1 skill point on ${st.name} (${stat})`,
        `+skill to ${stat} (priority stat for ${st.positions[0] || "player"})`); }
  });
  const positive = cands.filter((c) => c.gain > 1e-9).sort((a, b) => (b.gain_per_cost - a.gain_per_cost) || (b.gain - a.gain));
  const byKind = {};
  ["training","rankup","skill"].forEach((k) => byKind[k] = positive.filter((c) => c.kind === k).slice(0, limit));
  return { baseline_squad_score: r3(baseline), combined: positive.slice(0, limit), by_kind: byKind,
    zero_gain_count: cands.length - positive.length, costs_unverified: !costs.verified };
}

function planTrainingBudget(states, xpBudget, maxSteps) {
  maxSteps = maxSteps || 300;
  const costs = loadRule("costs"); const tC = costs.training.per_level; const maxL = loadRule("growth").max_training_level || 30;
  const lvlCost = (l) => l < tC.length ? tC[l] : tC[tC.length-1];
  let work = states.map(copyState);
  let baseline = bestSquadScore(work), current = baseline, remaining = Number(xpBudget);
  const raw = [];
  function swap(i, ns) { const c = work.slice(); c[i] = ns; return c; }
  for (let step = 0; step < maxSteps; step++) {
    let best = null;
    for (let idx = 0; idx < work.length; idx++) {
      const st = work[idx]; const lvl = st.training_level; if (lvl >= maxL) continue;
      const ts = trainStep(st); if (!ts || ts.xp > remaining) continue;
      const score = bestSquadScore(swap(idx, ts.ns)); const gain = score - current;
      if (gain <= 1e-9) continue; const gpc = gain / ts.xp;
      if (!best || gpc > best.gpc) best = { gpc, gain, cost: ts.xp, idx, lvl, ns: ts.ns, to_level: ts.to_level, score };
    }
    if (!best) break;
    const prev = work[best.idx]; const deltas = {}; MAIN_STATS.forEach((s)=>deltas[s]=best.ns.stats[s]-prev.stats[s]);
    work[best.idx] = best.ns; current = best.score; remaining -= best.cost;
    raw.push({ player_id: best.ns.id, player_name: best.ns.name, from_level: best.lvl, to_level: best.to_level,
      gain: best.gain, cost: best.cost, stat_deltas: deltas });
  }
  let reason = "no_more_value";
  if (raw.length < maxSteps) {
    for (let idx = 0; idx < work.length; idx++) { const st = work[idx]; if (st.training_level >= maxL) continue;
      const ts = trainStep(st); if (!ts) continue;
      if (bestSquadScore(swap(idx, ts.ns)) - current > 1e-9) { reason = "budget"; break; } }
  } else reason = "step_cap";
  const merged = [];
  raw.forEach((s) => {
    const last = merged[merged.length-1];
    if (last && last.player_id === s.player_id && last.to_level === s.from_level) {
      last.to_level = s.to_level; last.gain += s.gain; last.cost += s.cost;
      MAIN_STATS.forEach((st) => last.stat_deltas[st] += s.stat_deltas[st]);
    } else { const row = Object.assign({}, s); row.stat_deltas = Object.assign({}, s.stat_deltas); merged.push(row); }
  });
  let cx = 0, cg = 0;
  merged.forEach((m) => { cx += m.cost; cg += m.gain; m.cumulative_xp = Math.round(cx); m.cumulative_gain = r3(cg);
    m.gain = r3(m.gain); m.cost = Math.round(m.cost); m.levels = m.to_level - m.from_level;
    m.gain_per_cost = m.cost ? Math.round((m.gain/m.cost)*1e5)/1e5 : 0;
    const sd = {}; MAIN_STATS.forEach((st)=>sd[st]=r2(m.stat_deltas[st])); m.stat_deltas = sd;
    m.apply = { kind:"training", new_training_level:m.to_level, stat_deltas:sd }; });
  return { xp_budget: Math.round(Number(xpBudget)), spent: Math.round(Number(xpBudget)-remaining), remaining: Math.round(remaining),
    baseline_squad_score: r3(baseline), final_squad_score: r3(current), total_gain: r3(current-baseline),
    levels_trained: merged.reduce((a,m)=>a+m.levels,0), steps: merged, stopped_reason: reason, costs_unverified: !costs.verified };
}

// ----------------------------------------------------------------- gaps + bench
function gapReport(states) {
  const squad = optimize(states, 1)[0]; if (!squad) return { formation:null, slots:[], priority_positions:[] };
  const byId = {}; states.forEach((s) => byId[s.id] = s);
  const covers = {}; states.forEach((s) => s.positions.forEach((p) => covers[p] = (covers[p]||0)+1));
  const avg = squad.slots.length ? squad.total / squad.slots.length : 0;
  const rows = squad.slots.map((a) => {
    const st = byId[a.player_id];
    const oop = !!(st && st.positions.indexOf(a.position) < 0);
    const noSpec = (covers[a.position] || 0) === 0;
    const deficit = avg - a.score; const depth = a.score - (a.runner_up_score || 0);
    const priority = deficit + (oop?6:0) + (noSpec?4:0);
    const reasons = [];
    if (oop) reasons.push("filled by an out-of-position player");
    if (noSpec) reasons.push("no natural specialist in your club");
    if (deficit > 0) reasons.push(`${deficit.toFixed(1)} below squad average`);
    if (depth > 15) reasons.push("no real backup (thin depth)");
    if (!reasons.length) reasons.push("solid");
    return { slot_index:a.slot_index, position:a.position, player_name:a.player_name, score:r2(a.score),
      out_of_position:oop, no_specialist:noSpec, deficit_vs_avg:r2(deficit), depth_gap:r2(depth), priority:r2(priority), reasons };
  });
  const prio = rows.slice().sort((a,b)=>b.priority-a.priority).filter((r)=>r.priority>0.5)
    .map((r)=>({position:r.position, priority:r.priority, reasons:r.reasons}));
  return { formation:squad.formation, squad_average:r2(avg), slots:rows, priority_positions:prio };
}
function benchView(states, size) {
  size = size || 7; const squad = optimize(states, 1)[0];
  const xi = new Set(squad ? squad.slots.map((a)=>a.player_id) : []);
  const rows = [];
  states.forEach((st) => { if (xi.has(st.id)) return; const [pos, sc] = bestPositionScore(st);
    rows.push({ player_id:st.id, player_name:st.name, ovr:st.ovr, best_position:pos, best_score:r2(sc), positions:st.positions }); });
  rows.sort((a,b)=>b.best_score-a.best_score);
  return rows.slice(0, size);
}

// ----------------------------------------------------------------- targets / takeover
function normCost(xp, rankItems) { const n = loadRule("costs").normalization || {}; return xp*(n.training_unit||1) + rankItems*(n.rankup_unit||1); }
function computeTakeover(target, incumbent, position, transferSource) {
  const costs = loadRule("costs"); const tC = costs.training.per_level, rC = costs.rankup.per_rank;
  const fee = (costs.training_transfer||{}).transfer_fee_pct != null ? costs.training_transfer.transfer_fee_pct : 0.1;
  const ttPer = (costs.training_transfer||{}).tt_point_cost_per_level != null ? costs.training_transfer.tt_point_cost_per_level : 1;
  const maxL = loadRule("growth").max_training_level || 30, maxR = loadRule("rankup").max_rank || 5;
  const lvlCost = (l)=> l<tC.length?tC[l]:tC[tC.length-1]; const rankCost = (r)=> r<rC.length?rC[r]:rC[rC.length-1];
  let t = copyState(target);
  const before = slotScore(t, position);
  const incScore = incumbent ? slotScore(incumbent, position) : 0;
  const src = transferSource || incumbent;
  const srcLevel = src ? src.training_level : 0; const srcName = src ? src.name : null;
  let rankups = [], trainingAdded = 0, xp = 0, rankItems = 0;
  const transferred = Math.floor(srcLevel * (1 - fee)); let transferLevels = 0;
  if (transferred > t.training_level) { const add = transferred - t.training_level; const nt = withTrainingLevel(t, add); if (nt) { t = nt; transferLevels = add; } }
  let guard = 0;
  while (t.positions.indexOf(position) < 0 && t.rank < maxR && guard < 12) { const nr = withRankup(t); if (!nr) break; rankItems += rankCost(t.rank); rankups.push(t.rank+1); t = nr; guard++; }
  function result(final, achievable, reason) {
    return { position, target_id:target.id, target_name:target.name,
      incumbent_id: incumbent?incumbent.id:null, incumbent_name: incumbent?incumbent.name:"(empty)",
      incumbent_score:r2(incScore), target_score_before:r2(before), target_score_after:r2(slotScore(final, position)),
      transfer_from_name:srcName, transfer_from_level:srcLevel, transfer_levels:transferLevels, tt_points:transferLevels*ttPer,
      rankups, rank_from:target.rank, final_rank:final.rank, rank_items:Math.round(rankItems),
      training_added:trainingAdded, final_level:final.training_level, xp:Math.round(xp),
      total_cost_units:r2(normCost(xp, rankItems)), achievable, reason };
  }
  if (t.positions.indexOf(position) < 0) return result(t, false, "cannot play this position even fully ranked up");
  guard = 0;
  while (slotScore(t, position) < incScore - 1e-9 && guard < 80) {
    let best = null; const cur = slotScore(t, position);
    if (t.training_level < maxL) { const ts = trainStep(t);
      if (ts) { const g = slotScore(ts.ns, position) - cur; best = { gpc:ts.xp?g/ts.xp:0, kind:"train", ns:ts.ns, c:ts.xp, levels:ts.levels }; } }
    if (t.rank < maxR) { const c = rankCost(t.rank); const nr = withRankup(t);
      if (nr) { const g = slotScore(nr, position) - cur; const cand = { gpc:c?g/c:0, kind:"rank", ns:nr, c, levels:0 }; if (!best || cand.gpc > best.gpc) best = cand; } }
    if (!best) break;
    if (best.kind === "train") { trainingAdded += best.levels; xp += best.c; } else { rankItems += best.c; rankups.push(t.rank+1); }
    t = best.ns; guard++;
  }
  const achievable = slotScore(t, position) >= incScore - 1e-9;
  return result(t, achievable, achievable ? null : "still short even fully maxed");
}
function takeoverPlan(states, formationName, targets) {
  const fr = solveNamed(states, formationName); if (!fr) return { error: `Unknown formation: ${formationName}` };
  const byId = {}; states.forEach((s) => byId[s.id] = s);
  const currentBest = optimize(states, 1)[0];
  const currentIds = new Set(currentBest.slots.filter((a)=>a.player_id!=null).map((a)=>a.player_id));
  const currentPos = {}; currentBest.slots.forEach((a)=>{ if (a.player_id!=null) currentPos[a.player_id]=a.position; });
  const tmap = {}; Object.keys(targets||{}).forEach((k)=>{ const ki=parseInt(k,10); const v=targets[k]; tmap[ki]= v==null?null:parseInt(v,10); });
  const targetSlot = {}; fr.slots.forEach((slot)=>{ const w = tmap[slot.slot_index]; targetSlot[slot.slot_index] = (w!=null)?w:slot.player_id; });
  const targetIds = new Set(Object.values(targetSlot).filter((x)=>x!=null));
  const leaving = [];
  currentIds.forEach((pid)=>{ if (!targetIds.has(pid)) { const p = byId[pid]; if (p) leaving.push(p); } });
  leaving.sort((a,b)=>b.training_level-a.training_level);
  const pool = leaving.slice();
  const takeovers = [];
  fr.slots.forEach((slot)=>{
    const pid = targetSlot[slot.slot_index];
    if (pid==null || currentIds.has(pid)) return;
    const target = byId[pid]; if (!target) return;
    const incumbent = slot.player_id!=null ? byId[slot.player_id] : null;
    let source = null;
    if (incumbent && !targetIds.has(incumbent.id)) { source = incumbent; for (let i=0;i<pool.length;i++) if (pool[i].id===incumbent.id) { pool.splice(i,1); break; } }
    else if (pool.length) source = pool.shift();
    const res = computeTakeover(target, incumbent, slot.position, source); res.slot_index = slot.slot_index;
    takeovers.push(res);
  });
  takeovers.sort((a,b)=> (a.achievable===b.achievable ? a.total_cost_units-b.total_cost_units : (a.achievable?-1:1)));
  takeovers.forEach((t,i)=>t.order=i+1);
  return { formation:formationName, current_best_formation:currentBest.formation, takeovers,
    leaving: leaving.map((p)=>({player_id:p.id, name:p.name, current_position:currentPos[p.id], training_level:p.training_level, ovr:p.ovr})),
    staying_count: [...currentIds].filter((x)=>targetIds.has(x)).length,
    costs_unverified: !loadRule("costs").verified,
    transfer_fee_pct: (loadRule("costs").training_transfer||{}).transfer_fee_pct != null ? loadRule("costs").training_transfer.transfer_fee_pct : 0.1 };
}

// ----------------------------------------------------------------- CSV
function fmtPlaystyles(list) { return (list||[]).map((p)=> (p.name||"") + (p.plus?"+":"")).join("|"); }
function parsePlaystyles(text) { return (text||"").split("|").map((s)=>s.trim()).filter(Boolean).map((raw)=>{ const plus=raw.endsWith("+"); return { name: plus?raw.slice(0,-1).trim():raw, plus }; }); }
const CSV_COLS = ["name","ovr","rank","training_level", ...MAIN_STATS, ...MAIN_STATS.map((s)=>"base_"+s),
  "positions","rankup_positions","playstyles","skill_points","notes"];
function exportCsv() {
  const players = loadPlayers();
  const lines = [CSV_COLS.join(",")];
  players.forEach((p)=>{
    const row = { name:p.name, ovr:p.ovr, rank:p.rank, training_level:p.training_level };
    MAIN_STATS.forEach((s)=>row[s]=p[s]);
    MAIN_STATS.forEach((s)=>row["base_"+s]=(p.base_stats||{})[s]!=null?p.base_stats[s]:"");
    row.positions = (p.positions||[]).join("|"); row.rankup_positions=(p.rankup_positions||[]).join("|");
    row.playstyles = fmtPlaystyles(p.playstyles); row.skill_points=p.skill_points; row.notes=p.notes||"";
    lines.push(CSV_COLS.map((c)=>{ let v=row[c]==null?"":String(row[c]); if (/[",\n]/.test(v)) v='"'+v.replace(/"/g,'""')+'"'; return v; }).join(","));
  });
  return lines.join("\n");
}
function parseCsvLine(line) { const out=[]; let cur="",q=false; for (let i=0;i<line.length;i++){ const ch=line[i];
  if (q){ if (ch==='"'){ if (line[i+1]==='"'){cur+='"';i++;} else q=false; } else cur+=ch; }
  else { if (ch===','){out.push(cur);cur="";} else if (ch==='"'){q=true;} else cur+=ch; } } out.push(cur); return out; }
function importCsvText(text, replace) {
  const rows = text.replace(/\r/g,"").split("\n").filter((l)=>l.trim().length);
  if (!rows.length) return { imported:0, replaced:!!replace };
  const header = parseCsvLine(rows[0]); const idx = {}; header.forEach((h,i)=>idx[h.trim()]=i);
  const incoming = [];
  for (let r=1;r<rows.length;r++){ const c=parseCsvLine(rows[r]); const get=(k)=> idx[k]!=null?(c[idx[k]]||"").trim():"";
    if (!get("name")) continue;
    const num=(k,d)=>{ const v=get(k); const n=parseFloat(v); return isNaN(n)?d:n; };
    const base={}; let hasBase=false; MAIN_STATS.forEach((s)=>{ const v=get("base_"+s); if (v!==""){ const n=parseFloat(v); if(!isNaN(n)){base[s]=n;hasBase=true;} } });
    incoming.push({ name:get("name"), ovr:Math.round(num("ovr",50)), rank:Math.round(num("rank",0)), training_level:Math.round(num("training_level",0)),
      pace:num("pace",50), shooting:num("shooting",50), passing:num("passing",50), dribbling:num("dribbling",50), defending:num("defending",50), physical:num("physical",50),
      base_stats: hasBase?base:null, positions:get("positions").split("|").map((x)=>x.trim()).filter(Boolean),
      rankup_positions:get("rankup_positions").split("|").map((x)=>x.trim()).filter(Boolean), playstyles:parsePlaystyles(get("playstyles")),
      skill_points:Math.round(num("skill_points",0)), notes:get("notes") }); }
  let list = replace ? [] : loadPlayers();
  incoming.forEach((p)=>{ const np=applyData(newPlayer(), p); np.id=nextId(list); list.push(np); });
  savePlayers(list);
  return { imported: incoming.length, replaced: !!replace };
}

// ----------------------------------------------------------------- API facade (async, matches old REST client)
const A = (v) => Promise.resolve(v);
window.API = {
  meta() { return A({ positions: loadRule("positions").positions, formations: loadRule("formations").formations.map((f)=>f.name),
    playstyles: Object.keys(loadRule("playstyles").styles).sort(), main_stats: MAIN_STATS.slice(), unverified_files: unverifiedFiles() }); },
  players() { return A(loadPlayers().map(playerOut)); },
  createPlayer(body) { if (!(body.name||"").trim()) return Promise.reject(new Error("Name is required"));
    const list = loadPlayers(); const p = applyData(newPlayer(), body); p.id = nextId(list); list.push(p); savePlayers(list); return A(playerOut(p)); },
  updatePlayer(id, body) { const list = loadPlayers(); const p = list.find((x)=>x.id===id); if (!p) return Promise.reject(new Error("Player not found"));
    applyData(p, body); savePlayers(list); return A(playerOut(p)); },
  deletePlayer(id) { let list = loadPlayers(); if (!list.some((x)=>x.id===id)) return Promise.reject(new Error("Player not found"));
    list = list.filter((x)=>x.id!==id); savePlayers(list); return A({ ok:true }); },
  duplicatePlayer(id) { const list = loadPlayers(); const p = list.find((x)=>x.id===id); if (!p) return Promise.reject(new Error("Player not found"));
    const clone = JSON.parse(JSON.stringify(p)); clone.id = nextId(list); clone.name = `${p.name} (copy)`; list.push(clone); savePlayers(list); return A(playerOut(clone)); },
  squad(top, potential) { const states = statesFromStore(); if (states.length < 11) return A({ enough_players:false, have:states.length, need:11, results:[] });
    const out = { enough_players:true, have:states.length, potential:!!potential };
    let use = states;
    if (potential) { out.current_best_total = r3(bestSquadScore(states)); use = states.map(potentialState); }
    out.results = optimize(use, top || 5);
    out.team_ovr = bestTeamOvr(states);                                    // Team OVR uses base OVR + rank (current)
    out.team_ovr_potential = bestTeamOvr(states.map(fullyRankedUp));       // if every card were fully ranked up
    return A(out); },
  teamOvr() { const states = statesFromStore(); return A(bestTeamOvr(states)); },
  xpInfo() { return A({ per_level: XP_PER_LEVEL, total_to_max: xpToReach(30),
    cumulative: (function(){ const o={}; for (let l=1;l<=30;l++) o[l]=xpToReach(l); return o; })(),
    yield_bands: XP_YIELD_BANDS }); },
  foodXp(ovr, green) { return A(foodXp(Number(ovr) || 0, !!green)); },
  upgrades(limit) { const states = statesFromStore(); if (states.length < 11) return A({ enough_players:false, have:states.length, need:11 });
    const plan = planUpgrades(states, limit); plan.enough_players = true; return A(plan); },
  trainingPlan(xp) { const states = statesFromStore(); if (states.length < 11) return A({ enough_players:false, have:states.length, need:11 });
    if (!(xp>0)) return A({ enough_players:true, xp_budget:0, steps:[], needs_budget:true });
    const plan = planTrainingBudget(states, xp); plan.enough_players = true; return A(plan); },
  gaps() { const states = statesFromStore(); if (states.length < 11) return A({ enough_players:false, have:states.length, need:11 });
    const rep = gapReport(states); rep.enough_players = true; return A(rep); },
  bench(size) { return A({ bench: benchView(statesFromStore(), size) }); },
  bestFormations() { const states = statesFromStore(); if (states.length < 11) return A({ current:null, potential:null });
    return A({ current: optimize(states,1)[0].formation, potential: optimize(states.map(potentialState),1)[0].formation }); },
  formationXi(f) { const fr = solveNamed(statesFromStore(), f); if (!fr) return Promise.reject(new Error("Unknown formation")); return A(fr); },
  takeoverPlan(formation, targets) { const states = statesFromStore(); if (states.length < 11) return A({ enough_players:false, have:states.length, need:11 });
    const plan = takeoverPlan(states, formation, targets); plan.enough_players = true; return A(plan); },
  rule(name) { return A(loadRule(name)); },
  saveRule(name, data) { saveRuleData(name, data); return A({ ok:true, unverified_files: unverifiedFiles() }); },
  // client-side import/export
  exportCsvText() { return exportCsv(); },
  exportJson() { return { players: loadPlayers() }; },
  importCsvFile(file, replace) { return file.text().then((t)=>importCsvText(t, replace)); },
  importJsonObj(obj, replace) { let list = replace?[]:loadPlayers(); (obj.players||[]).forEach((row)=>{ const p=applyData(newPlayer(), row); p.id=nextId(list); list.push(p); }); savePlayers(list); return A({ ok:true, imported:(obj.players||[]).length, replaced:!!replace }); },
};

// ----------------------------------------------------------------- card database (data/cards.json)
// Accent folding: type the plain-English lookalike and it still matches (Mbappe -> Mbappé,
// Ozil -> Özil, Odegaard -> Ødegaard, Piatek -> Piątek, etc.).
const FOLD = { "ø":"o","ł":"l","đ":"d","ð":"d","þ":"th","ı":"i","ß":"ss","æ":"ae","œ":"oe","ħ":"h","ŧ":"t","ĸ":"k","ŀ":"l" };
function fold(s) {
  s = String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  let out = "";
  for (const ch of s) out += (FOLD[ch] !== undefined ? FOLD[ch] : ch);
  return out;
}
let _cards = null, _cardsPromise = null;
function loadCards() {
  if (_cards) return Promise.resolve(_cards);
  if (_cardsPromise) return _cardsPromise;
  _cardsPromise = fetch("data/cards.json")
    .then((r) => (r.ok ? r.json() : { cards: [] }))
    .then((d) => { _cards = (d.cards || []).map((c) => { c._f = fold(c.n); return c; }); _cards._meta = { count: d.count, season: d.season, updated: d.updated }; return _cards; })
    .catch(() => { _cards = []; return _cards; });
  return _cardsPromise;
}
function searchCards(query, limit) {
  limit = limit || 40;
  const f = fold(query).trim();
  if (f.length < 2 || !_cards) return [];
  const hits = [];
  for (const c of _cards) { const i = c._f.indexOf(f); if (i >= 0) hits.push([i, c]); }
  hits.sort((a, b) => (a[0] - b[0]) || (b[1].o - a[1].o) || a[1].n.localeCompare(b[1].n));
  return hits.slice(0, limit).map((x) => x[1]);
}
// Convert a card into a player body the editor can use (stats already mapped, GK-aware).
function cardToPlayer(card) {
  const body = { name: card.n, ovr: card.o, positions: (card.p || []).slice(), variant: card.v || "", is_gk: !!card.gk };
  MAIN_STATS.forEach((s, i) => { body[s] = card.s[i]; });
  return body;
}
window.API.searchCards = (q) => loadCards().then(() => searchCards(q, 40));
window.API.cardCount = () => loadCards().then(() => (_cards && _cards._meta ? _cards._meta.count : (_cards ? _cards.length : 0)));
window.API.cardToPlayer = cardToPlayer;

// ----------------------------------------------------------------- sample squad (for first-time visitors)
const SAMPLE = [
  ["Aria Fox",88,2,12,92,90,78,89,34,74,["ST","CF"],[["Rapid",true],["Clinical Finisher",false]]],
  ["Kofi Mensah",86,1,8,90,84,74,88,30,70,["ST"],[["Finesse Expert",false]]],
  ["Luca Ferrari",85,3,15,82,62,88,86,40,66,["CAM","CM"],[["Bullet Pass",true]]],
  ["Diego Santos",84,1,6,88,55,80,85,48,62,["RW","RM"],[["Technical",false]]],
  ["Yuki Tanaka",83,2,10,89,52,78,84,45,60,["LW","LM"],[["Trickster",false]]],
  ["Omar Haddad",85,2,11,70,60,84,80,82,78,["CDM","CM"],[["Anticipate",true]]],
  ["Ben Carter",84,1,7,72,45,80,76,80,80,["CM","CDM"],[["Guardian",false]]],
  ["Marco Rossi",86,3,14,74,40,70,66,88,86,["CB"],[["Bruiser",true]]],
  ["Sven Johansson",85,2,9,76,38,68,64,87,85,["CB"],[["Anticipate",false]]],
  ["Paulo Alves",83,1,5,84,42,76,74,78,72,["RB","RWB"],[["Bruiser",false]]],
  ["Tom Wright",82,1,4,85,40,74,73,77,70,["LB","LWB"],[]],
  ["Ivan Petrov",87,0,0,85,84,70,88,83,82,["GK"],[["Rush Out",false]]],
  ["Noah Kim",80,0,3,86,78,68,82,28,64,["ST"],[]],
  ["Ali Reza",81,1,6,68,50,82,78,76,70,["CM"],[["Tiki Taka",false]]],
  ["Jack Moss",79,0,2,70,36,66,62,82,80,["CB"],[]],
  ["Leo Duarte",80,1,5,82,44,74,72,74,68,["LB"],[]],
  ["Sam Pryce",78,0,1,80,40,70,76,40,60,["RW","LW"],[]],
];
function loadSample(replace) {
  let list = replace ? [] : loadPlayers();
  SAMPLE.forEach((r) => {
    const [name,ovr,rank,lvl,pac,sho,pas,dri,def,phy,pos,styles] = r;
    const cur = { pace:pac, shooting:sho, passing:pas, dribbling:dri, defending:def, physical:phy };
    const tb = DEFAULT_RULES.growth.training_boost; const off = lvl < tb.length ? tb[lvl] : tb[tb.length - 1];
    const base = {}; MAIN_STATS.forEach((s) => base[s] = cur[s] - off);
    const p = newPlayer();
    Object.assign(p, { name, ovr, rank, training_level:lvl }, cur);
    p.positions = pos; p.base_stats = base;
    p.playstyles = styles.map((x) => ({ name:x[0], plus:x[1] }));
    p.id = nextId(list); list.push(p);
  });
  savePlayers(list);
  return { ok:true, loaded: SAMPLE.length };
}

window.API.loadSample = (replace) => A(loadSample(replace));
window.API.clearAll = () => { savePlayers([]); return A({ ok:true }); };

// expose a few internals for optional Node cross-testing
window.__engine = { optimize, planUpgrades, planTrainingBudget, takeoverPlan, statesFromStore, bestSquadScore, potentialState,
  bestTeamOvr, teamOvrOf, trainStep, withTrainingLevel, xpToReach, foodXp, skillMainStats };
})();
