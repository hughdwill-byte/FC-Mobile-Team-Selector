/* Player-card image generator.
 * Draws a 1024x1408 FC Mobile-style card for a player: the promo/season is themed with the
 * matching event key art (docs/img/events/<key>.jpg, from the s8nag archive), with the player's
 * name, OVR, position, rank and six stats overlaid. No player photo is available, so the card is
 * the themed background + the numbers. Exposes window.CardArt.
 */
(function () {
"use strict";

const W = 1024, H = 1408;

// Theme key -> accent colour. Backgrounds live at img/events/<key>.jpg. Aliases resolve in themeKey().
const THEMES = {
  toty:{accent:"#f5c542"}, tots:{accent:"#21e6c1"}, twg:{accent:"#3ad42e"},
  footyverse:{accent:"#ff5ec7"}, ragnarok:{accent:"#8fe3ff"}, neon:{accent:"#c6ff2e"},
  ucl:{accent:"#3b82f6"}, laliga:{accent:"#ff5a3c"}, ballondor:{accent:"#e9c46a"},
  gloriouseras:{accent:"#d4af37"}, dreamchasers:{accent:"#4de1ff"}, captains:{accent:"#ffb703"},
  cappedlegends:{accent:"#c77dff"}, anniversary:{accent:"#ff67c0"}, winter:{accent:"#7fd8ff"},
  festive:{accent:"#ff4d4d"}, carniball:{accent:"#ff8fab"}, flashback:{accent:"#ffd166"},
  trickortreat:{accent:"#ff7b00"}, heroes:{accent:"#ef4444"}, centurions:{accent:"#ffd166"},
  euro:{accent:"#5b7bff"}, halloflegends:{accent:"#d4af37"}, mls:{accent:"#ef4444"},
  champions:{accent:"#f1c40f"}, retro:{accent:"#f4a261"}, aquainferno:{accent:"#ff6b35"},
  worldcup:{accent:"#06d6a0"},
};
// Base promo code (letters only, after stripping season digits/suffixes) -> theme key.
const CODE_TO_THEME = {
  TOTY:"toty", TOTS:"tots", TWG:"twg", FV:"footyverse", FOOTYVERSE:"footyverse",
  RAGNAROK:"ragnarok", RA:"ragnarok", NEON:"neon", UTOTS:"tots", UCL:"ucl", UCLLP:"ucl", UECL:"ucl", UCLRTTF:"ucl",
  UEFADC:"dreamchasers", UEFA:"ucl", LALIGA:"laliga", BO:"ballondor", GE:"gloriouseras",
  CAP:"captains", CAPP:"cappedlegends", ANN:"anniversary", ANS:"anniversary",
  WW:"winter", FF:"festive", FB:"flashback", FBC:"flashback",
  CARNIVAL:"carniball", CARNIBALL:"carniball", TRICKORTREAT:"trickortreat", CHA:"champions",
  VS:"aquainferno", MLS:"mls", HEROES:"heroes", CENTURIONS:"centurions", EURO:"euro",
  HALLOFLEGENDS:"halloflegends", RETRO:"retro", WORLDCUP:"worldcup", WC:"worldcup", PATCHWC:"worldcup",
};
const SUFFIXES = new Set(["LIVE","ICON","MM","UT","LC","POP","ROCK","RTTF","WINNER","MOTM","V2","LP"]);

function themeKey(variant) {
  const raw = String(variant || "").toUpperCase().replace(/[^A-Z0-9 ]/g, " ").trim();
  if (!raw) return null;
  const tokens = raw.split(/\s+/).filter((t) => !SUFFIXES.has(t));
  for (const tok of tokens) {
    const code = tok.replace(/[0-9]/g, "");           // strip season digits (TOTS26 -> TOTS)
    if (CODE_TO_THEME[code]) return CODE_TO_THEME[code];
  }
  return null;
}
// Resolve a player's theme: matched promo, else a tier by OVR so every card still looks intentional.
function resolveTheme(player) {
  const key = themeKey(player.variant);
  if (key && THEMES[key]) return { key, accent: THEMES[key].accent, img: "img/events/" + key + ".jpg", label: promoLabel(player.variant) };
  const ovr = Number(player.ovr) || 0;
  const tier = ovr >= 100 ? "#f5c542" : ovr >= 85 ? "#d9dde3" : "#cd7f4b"; // gold / silver / bronze
  return { key: null, accent: tier, img: null, label: promoLabel(player.variant) };
}
function promoLabel(variant) {
  const v = String(variant || "").trim();
  if (!v) return "";
  return v.replace(/\bLIVE\b/i, "").replace(/\s+/g, " ").trim();
}

const _imgCache = {};
function loadImage(src) {
  if (_imgCache[src]) return _imgCache[src];
  _imgCache[src] = new Promise((resolve) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => resolve(null);
    im.src = src;
  });
  return _imgCache[src];
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
function fitText(ctx, text, maxW, startPx, weight, family) {
  let px = startPx;
  do { ctx.font = `${weight} ${px}px ${family}`; if (ctx.measureText(text).width <= maxW) break; px -= 2; } while (px > 12);
  return px;
}
// cover-crop an image to fill a box
function drawCover(ctx, im, x, y, w, h) {
  const ir = im.width / im.height, br = w / h;
  let sw, sh, sx, sy;
  if (ir > br) { sh = im.height; sw = sh * br; sx = (im.width - sw) / 2; sy = 0; }
  else { sw = im.width; sh = sw / br; sx = 0; sy = (im.height - sh) / 2; }
  ctx.drawImage(im, sx, sy, sw, sh, x, y, w, h);
}

const OUT_LABELS = ["PAC","SHO","PAS","DRI","DEF","PHY"];
const GK_LABELS  = ["DIV","HAN","KIC","REF","POS","PHY"];
const STAT_KEYS  = ["pace","shooting","passing","dribbling","defending","physical"];

async function renderCard(player) {
  const isGk = (player.positions || []).includes("GK") || player.is_gk;
  const theme = resolveTheme(player);
  const accent = theme.accent;
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d");
  const FAM = "'Roboto','Segoe UI',system-ui,sans-serif";

  // ---- background
  ctx.fillStyle = "#0b0f14"; ctx.fillRect(0, 0, W, H);
  const bg = theme.img ? await loadImage(theme.img) : null;
  if (bg) drawCover(ctx, bg, 0, 0, W, H);
  else { const g = ctx.createLinearGradient(0, 0, W, H); g.addColorStop(0, "#1a2230"); g.addColorStop(1, "#0b0f14"); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }

  // legibility gradient (darker top-left for OVR block, darker bottom for stats)
  let g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "rgba(6,10,16,.72)"); g.addColorStop(0.32, "rgba(6,10,16,.20)");
  g.addColorStop(0.58, "rgba(6,10,16,.35)"); g.addColorStop(1, "rgba(6,10,16,.94)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

  // accent frame
  ctx.strokeStyle = accent; ctx.lineWidth = 8; roundRect(ctx, 22, 22, W - 44, H - 44, 34); ctx.stroke();
  ctx.strokeStyle = "rgba(255,255,255,.15)"; ctx.lineWidth = 2; roundRect(ctx, 34, 34, W - 68, H - 68, 26); ctx.stroke();

  // ---- top-left: OVR + position
  ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  const ovr = (player.ovr === "" || player.ovr == null) ? "--" : Math.round(Number(player.ovr));
  ctx.fillStyle = "#fff"; ctx.font = `800 172px ${FAM}`;
  ctx.shadowColor = "rgba(0,0,0,.55)"; ctx.shadowBlur = 18; ctx.shadowOffsetY = 4;
  ctx.fillText(String(ovr), 70, 210);
  ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  const pos = (player.positions && player.positions[0]) || (isGk ? "GK" : "");
  ctx.fillStyle = accent; ctx.font = `800 60px ${FAM}`;
  ctx.fillText(pos, 78, 270);

  // rank pips (0-5)
  const rank = Math.max(0, Math.min(5, Math.round(Number(player.rank) || 0)));
  for (let i = 0; i < 5; i++) {
    const cx = 82 + i * 46, cy = 320, r = 15;
    ctx.beginPath(); ctx.moveTo(cx, cy - r); ctx.lineTo(cx + r, cy); ctx.lineTo(cx, cy + r); ctx.lineTo(cx - r, cy); ctx.closePath();
    if (i < rank) { ctx.fillStyle = accent; ctx.fill(); } else { ctx.strokeStyle = "rgba(255,255,255,.5)"; ctx.lineWidth = 3; ctx.stroke(); }
  }

  // ---- promo label (top-right)
  if (theme.label) {
    ctx.textAlign = "right"; ctx.font = `700 34px ${FAM}`;
    const lw = ctx.measureText(theme.label).width;
    ctx.fillStyle = "rgba(6,10,16,.55)"; roundRect(ctx, W - 88 - lw - 28, 74, lw + 28, 52, 12); ctx.fill();
    ctx.fillStyle = accent; ctx.fillText(theme.label, W - 90, 111);
    ctx.textAlign = "left";
  }

  // ---- name
  const name = (player.name || "Player").toUpperCase();
  ctx.textAlign = "center";
  const npx = fitText(ctx, name, W - 160, 92, 800, FAM);
  ctx.fillStyle = "#fff"; ctx.font = `800 ${npx}px ${FAM}`;
  ctx.shadowColor = "rgba(0,0,0,.6)"; ctx.shadowBlur = 14; ctx.shadowOffsetY = 3;
  ctx.fillText(name, W / 2, 900);
  ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  // accent underline
  ctx.strokeStyle = accent; ctx.lineWidth = 5;
  ctx.beginPath(); ctx.moveTo(W / 2 - 140, 928); ctx.lineTo(W / 2 + 140, 928); ctx.stroke();

  // ---- stats grid (2 cols x 3 rows)
  const labels = isGk ? GK_LABELS : OUT_LABELS;
  const colX = [W * 0.30, W * 0.70], rowY = [1050, 1170, 1290];
  ctx.textAlign = "center";
  for (let i = 0; i < 6; i++) {
    const col = i % 2, row = (i / 2) | 0;
    const x = colX[col], y = rowY[row];
    let v = player[STAT_KEYS[i]];
    v = (v === "" || v == null || isNaN(Number(v))) ? "--" : Math.round(Number(v));
    ctx.fillStyle = accent; ctx.font = `800 62px ${FAM}`; ctx.fillText(String(v), x, y);
    ctx.fillStyle = "rgba(255,255,255,.82)"; ctx.font = `700 30px ${FAM}`; ctx.fillText(labels[i], x, y + 36);
  }

  // ---- credit (these backgrounds are EA event key art)
  ctx.textAlign = "center"; ctx.fillStyle = "rgba(255,255,255,.5)"; ctx.font = `500 20px ${FAM}`;
  ctx.fillText("Art: EA SPORTS FC Mobile event key art", W / 2, H - 54);

  return canvas;
}

function download(canvas, filename) {
  const a = document.createElement("a");
  a.href = canvas.toDataURL("image/png");
  a.download = (filename || "card") + ".png";
  document.body.appendChild(a); a.click(); a.remove();
}

window.CardArt = { renderCard, resolveTheme, themeKey, download, THEMES };
})();
