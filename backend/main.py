"""FastAPI application: REST API + serves the browser GUI."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from . import analysis, csvio, rules as rules_mod, upgrades as upgrades_mod
from .db import engine, init_db
from .models import MAIN_STATS, Player, PlayerCreate
from .optimizer import optimize
from .paths import DB_PATH, FRONTEND_DIR
from .scoring import player_to_state
from .serialize import formation_out, player_out

app = FastAPI(title="FC Mobile Squad Optimizer")


@app.on_event("startup")
def _startup() -> None:
    init_db()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _all_players(session: Session) -> list[Player]:
    return list(session.exec(select(Player).order_by(Player.name)).all())


def _states(session: Session):
    return [player_to_state(p) for p in _all_players(session)]


def _apply(player: Player, data: dict) -> None:
    for key in ("name", "ovr", "rank", "training_level", *MAIN_STATS,
                "positions", "rankup_positions", "playstyles",
                "growth_override", "skill_points", "notes"):
        if key in data and data[key] is not None:
            setattr(player, key, data[key])


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
    with Session(engine) as s:
        return [player_out(p) for p in _all_players(s)]


@app.post("/api/players")
def create_player(body: PlayerCreate):
    with Session(engine) as s:
        p = Player(**body.model_dump())
        s.add(p)
        s.commit()
        s.refresh(p)
        return player_out(p)


@app.get("/api/players/{player_id}")
def get_player(player_id: int):
    with Session(engine) as s:
        p = s.get(Player, player_id)
        if not p:
            raise HTTPException(404, "Player not found")
        return player_out(p)


@app.put("/api/players/{player_id}")
def update_player(player_id: int, body: dict):
    with Session(engine) as s:
        p = s.get(Player, player_id)
        if not p:
            raise HTTPException(404, "Player not found")
        _apply(p, body)
        s.add(p)
        s.commit()
        s.refresh(p)
        return player_out(p)


@app.delete("/api/players/{player_id}")
def delete_player(player_id: int):
    with Session(engine) as s:
        p = s.get(Player, player_id)
        if not p:
            raise HTTPException(404, "Player not found")
        s.delete(p)
        s.commit()
        return {"ok": True}


@app.post("/api/players/{player_id}/duplicate")
def duplicate_player(player_id: int):
    with Session(engine) as s:
        p = s.get(Player, player_id)
        if not p:
            raise HTTPException(404, "Player not found")
        data = p.model_dump(exclude={"id"})
        data["name"] = f"{p.name} (copy)"
        clone = Player(**data)
        s.add(clone)
        s.commit()
        s.refresh(clone)
        return player_out(clone)


# ----------------------------------------------------------------------------
# Optimiser outputs
# ----------------------------------------------------------------------------
@app.get("/api/squad")
def squad(top: int = 5):
    with Session(engine) as s:
        states = _states(s)
        if len(states) < 11:
            return {"enough_players": False, "have": len(states), "need": 11, "results": []}
        results = optimize(states, top_n=top)
        return {"enough_players": True, "have": len(states), "results": [formation_out(r) for r in results]}


@app.get("/api/upgrades")
def upgrade_plan(limit: int = 40):
    with Session(engine) as s:
        states = _states(s)
        if len(states) < 11:
            return {"enough_players": False, "have": len(states), "need": 11}
        plan = upgrades_mod.plan_upgrades(states, limit=limit)
        plan["enough_players"] = True
        return plan


@app.get("/api/gaps")
def gaps():
    with Session(engine) as s:
        states = _states(s)
        if len(states) < 11:
            return {"enough_players": False, "have": len(states), "need": 11}
        report = analysis.gap_report(states)
        report["enough_players"] = True
        return report


@app.get("/api/bench")
def bench(size: int = 7):
    with Session(engine) as s:
        states = _states(s)
        return {"bench": analysis.bench_view(states, size=size)}


# ----------------------------------------------------------------------------
# Import / export / backup
# ----------------------------------------------------------------------------
@app.get("/api/export/csv")
def export_csv():
    with Session(engine) as s:
        text = csvio.export_csv(_all_players(s))
    return PlainTextResponse(
        text,
        headers={"Content-Disposition": "attachment; filename=fcmobile_players.csv"},
        media_type="text/csv",
    )


@app.post("/api/import/csv")
async def import_csv(file: UploadFile, replace: bool = False):
    raw = (await file.read()).decode("utf-8-sig")
    incoming = csvio.parse_csv(raw)
    with Session(engine) as s:
        if replace:
            for p in _all_players(s):
                s.delete(p)
            s.commit()
        for p in incoming:
            s.add(p)
        s.commit()
    return {"ok": True, "imported": len(incoming), "replaced": replace}


@app.get("/api/export/json")
def export_json():
    with Session(engine) as s:
        data = [p.model_dump() for p in _all_players(s)]
    return {"players": data}


@app.post("/api/import/json")
def import_json(body: dict, replace: bool = False):
    players = body.get("players", [])
    with Session(engine) as s:
        if replace:
            for p in _all_players(s):
                s.delete(p)
            s.commit()
        for row in players:
            row.pop("id", None)
            s.add(Player(**row))
        s.commit()
    return {"ok": True, "imported": len(players), "replaced": replace}


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
