// Thin wrapper around the REST API.
const API = {
  async _json(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  },
  get(u) { return this._json("GET", u); },
  post(u, b) { return this._json("POST", u, b); },
  put(u, b) { return this._json("PUT", u, b); },
  del(u) { return this._json("DELETE", u); },

  meta() { return this.get("/api/meta"); },
  players() { return this.get("/api/players"); },
  createPlayer(p) { return this.post("/api/players", p); },
  updatePlayer(id, p) { return this.put(`/api/players/${id}`, p); },
  deletePlayer(id) { return this.del(`/api/players/${id}`); },
  duplicatePlayer(id) { return this.post(`/api/players/${id}/duplicate`); },
  squad(top = 5, potential = false) { return this.get(`/api/squad?top=${top}&potential=${potential ? "true" : "false"}`); },
  formationXi(f) { return this.get(`/api/formation-xi?formation=${encodeURIComponent(f)}`); },
  takeoverPlan(formation, targets) { return this.post("/api/takeover-plan", { formation, targets }); },
  upgrades(limit = 40) { return this.get(`/api/upgrades?limit=${limit}`); },
  trainingPlan(xp) { return this.get(`/api/training-plan?xp=${encodeURIComponent(xp)}`); },
  gaps() { return this.get("/api/gaps"); },
  bench(size = 7) { return this.get(`/api/bench?size=${size}`); },
  rule(name) { return this.get(`/api/rules/${name}`); },
  saveRule(name, data) { return this.put(`/api/rules/${name}`, data); },
  async importCsv(file, replace) {
    const fd = new FormData(); fd.append("file", file);
    const res = await fetch(`/api/import/csv?replace=${replace ? "true" : "false"}`, { method: "POST", body: fd });
    if (!res.ok) throw new Error("Import failed");
    return res.json();
  },
};
