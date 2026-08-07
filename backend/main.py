"""FastAPI application: REST API + serves the browser GUI."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import analysis, csvio, db, rules as rules_mod, targets as targets_mod, upgrades as upgrades_mod
from .db import init_db
from .models import MAIN_STATS, player_from_dict
from .optimizer import optimize, solve_named
from .paths import DB_PATH, FRONTEND_DIR
from .scoring import player_to_state
from .serialize import formation_out, player_out

app = FastAPI(title="FC Mobile Squad Optimizer")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.middleware("http")
async def _no_cache(request, call_next):
    """This is a local app that updates in place, so never let the browser serve a stale
    HTML/JS/CSS file - always fetch the current version."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _states():
    return [player_to_state(p) for p in db.get_all()]


# ----------------------------------------------------------------------------
# Meta / rules
# ----------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    return {
        "positions": rules_mod.load("positions")["positions"],
        "formations": [f["name"] for f in rules_mod.load("formations")["formations"]],
        "playstyles": sorted(rules_mod.load("playstyles")["styles"].keys()),
        "main_stats": MAIN_STATS,
        "unverified_files": rules_mod.unverified_files(),
    }


@app.get("/api/rules")
def get_rules():
    return rules_mod.all_rules()


@app.get("/api/rules/{name}")
def get_rule(name: str):
    try:
        return rules_mod.load(name)
    except KeyError:
        raise HTTPException(404, f"Unknown rules file: {name}")


@app.put("/api/rules/{name}")
def put_rule(name: str, body: dict):
    try:
        rules_mod.save(name, body)
    except KeyError:
        raise HTTPException(404, f"Unknown rules file: {name}")
    return {"ok": True, "unverified_files": rules_mod.unverified_files()}


# ----------------------------------------------------------------------------
# Players CRUD
# ----------------------------------------------------------------------------
@app.get("/api/players")
def list_players():
    return [player_out(p) for p in db.get_all()]


@app.post("/api/players")
def create_player(body: dict):
    if not (body.get("name") or "").strip():
        raise HTTPException(400, "Name is required")
    p = player_from_dict(body)
    return player_out(db.create(p))


@app.get("/api/players/{player_id}")
def get_player(player_id: int):
    p = db.get(player_id)
    if not p:
        raise HTTPException(404, "Player not found")
    return player_out(p)


@app.put("/api/players/{player_id}")
def update_player(player_id: int, body: dict):
    p = db.get(player_id)
    if not p:
        raise HTTPException(404, "Player not found")
    player_from_dict(body, base=p)
    return player_out(db.update(player_id, p))


@app.delete("/api/players/{player_id}")
def delete_player(player_id: int):
    if not db.get(player_id):
        raise HTTPException(404, "Player not found")
    db.delete(player_id)
    return {"ok": True}


@app.post("/api/players/{player_id}/duplicate")
def duplicate_player(player_id: int):
    p = db.get(player_id)
    if not p:
        raise HTTPException(404, "Player not found")
    clone = player_from_dict(p.to_dict())
    clone.id = None
    clone.name = f"{p.name} (copy)"
    return player_out(db.create(clone))


# ----------------------------------------------------------------------------
# Optimiser outputs
# ----------------------------------------------------------------------------
@app.get("/api/squad")
def squad(top: int = 5, potential: bool = False):
    states = _states()
    if len(states) < 11:
        return {"enough_players": False, "have": len(states), "need": 11, "results": []}

    out = {"enough_players": True, "have": len(states), "potential": potential}
    if potential:
        from .optimizer import best_squad_score
        from .scoring import potential_state
        out["current_best_total"] = round(best_squad_score(states), 3)
        states = [potential_state(s) for s in states]

    results = optimize(states, top_n=top)
    out["results"] = [formation_out(r) for r in results]
    return out


@app.get("/api/upgrades")
def upgrade_plan(limit: int = 40):
    states = _states()
    if len(states) < 11:
        return {"enough_players": False, "have": len(states), "need": 11}
    plan = upgrades_mod.plan_upgrades(states, limit=limit)
    plan["enough_players"] = True
    return plan


@app.get("/api/training-plan")
def training_plan(xp: float = 0):
    states = _states()
    if len(states) < 11:
        return {"enough_players": False, "have": len(states), "need": 11}
    if xp <= 0:
        return {"enough_players": True, "xp_budget": 0, "steps": [], "needs_budget": True}
    plan = upgrades_mod.plan_training_budget(states, xp)
    plan["enough_players"] = True
    return plan


@app.get("/api/best-formations")
def best_formations():
    """The best formation for the current squad and for the fully-ranked-up (potential)
    squad - these can differ, which the Target planner surfaces."""
    states = _states()
    if len(states) < 11:
        return {"current": None, "potential": None}
    from .scoring import potential_state
    current = optimize(states, top_n=1)[0].formation
    potential = optimize([potential_state(s) for s in states], top_n=1)[0].formation
    return {"current": current, "potential": potential}


@app.get("/api/formation-xi")
def formation_xi(formation: str):
    states = _states()
    fr = solve_named(states, formation)
    if fr is None:
        raise HTTPException(404, f"Unknown formation: {formation}")
    return formation_out(fr)


@app.post("/api/takeover-plan")
def takeover_plan(body: dict):
    states = _states()
    if len(states) < 11:
        return {"enough_players": False, "have": len(states), "need": 11}
    formation = body.get("formation")
    targets = body.get("targets", {})
    plan = targets_mod.takeover_plan(states, formation, targets)
    plan["enough_players"] = True
    return plan


@app.get("/api/gaps")
def gaps():
    states = _states()
    if len(states) < 11:
        return {"enough_players": False, "have": len(states), "need": 11}
    report = analysis.gap_report(states)
    report["enough_players"] = True
    return report


@app.get("/api/bench")
def bench(size: int = 7):
    return {"bench": analysis.bench_view(_states(), size=size)}


# ----------------------------------------------------------------------------
# Import / export / backup
# ----------------------------------------------------------------------------
@app.get("/api/export/csv")
def export_csv():
    text = csvio.export_csv(db.get_all())
    return PlainTextResponse(
        text,
        headers={"Content-Disposition": "attachment; filename=fcmobile_players.csv"},
        media_type="text/csv",
    )


@app.post("/api/import/csv")
async def import_csv(file: UploadFile, replace: bool = False):
    raw = (await file.read()).decode("utf-8-sig")
    incoming = csvio.parse_csv(raw)
    if replace:
        db.delete_all()
    for p in incoming:
        db.create(p)
    return {"ok": True, "imported": len(incoming), "replaced": replace}


@app.get("/api/export/json")
def export_json():
    return {"players": [p.to_dict() for p in db.get_all()]}


@app.post("/api/import/json")
def import_json(body: dict, replace: bool = False):
    players = body.get("players", [])
    if replace:
        db.delete_all()
    count = 0
    for row in players:
        p = player_from_dict(row)
        p.id = None
        db.create(p)
        count += 1
    return {"ok": True, "imported": count, "replaced": replace}


@app.get("/api/backup/db")
def backup_db():
    if not DB_PATH.exists():
        raise HTTPException(404, "No database yet")
    return FileResponse(
        DB_PATH,
        filename="fcmobile_backup.sqlite3",
        media_type="application/octet-stream",
    )


# ----------------------------------------------------------------------------
# Static frontend (mounted last so it doesn't shadow /api routes)
# ----------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
