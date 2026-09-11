"""Stage 2: property graph in SQLite. Every node/edge carries provenance + time."""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "graph.db"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def node_id(type_: str, name: str) -> str:
    return f"{type_}:{norm(name)}"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def parse_ref(ref: str) -> tuple[str, str]:
    """'Type:Name' -> (Type, Name). Name may itself contain ':'"""
    if ":" not in ref:
        raise ValueError(f"reference must be 'Type:Name', got {ref!r}")
    t, n = ref.split(":", 1)
    return t.strip(), n.strip()


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes(
  id TEXT PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL,
  attrs TEXT NOT NULL DEFAULT '{}', aliases TEXT NOT NULL DEFAULT '[]',
  source TEXT NOT NULL, confidence TEXT NOT NULL DEFAULT 'medium',
  extracted_at TEXT NOT NULL, valid_from TEXT, valid_to TEXT,
  merged_from TEXT NOT NULL DEFAULT '[]', conflicts TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS aliases(alias_key TEXT NOT NULL, node_id TEXT NOT NULL, PRIMARY KEY(alias_key, node_id));
CREATE TABLE IF NOT EXISTS edges(
  id INTEGER PRIMARY KEY, src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL,
  attrs TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL, confidence TEXT NOT NULL DEFAULT 'medium',
  extracted_at TEXT NOT NULL, valid_from TEXT, valid_to TEXT, evidence TEXT,
  UNIQUE(src, rel, dst));
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE TABLE IF NOT EXISTS staging(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, source TEXT NOT NULL,
  evidence TEXT, confidence TEXT, status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS candidates(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS review_queue(
  id INTEGER PRIMARY KEY, a TEXT NOT NULL, b TEXT NOT NULL, score REAL, reasons TEXT,
  status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, UNIQUE(a, b));
"""


def _j(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


class Store:
    def __init__(self, path: Path | str = DB_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # ---- helpers ----------------------------------------------------------
    @staticmethod
    def _node(r) -> dict:
        d = dict(r)
        for k in ("attrs", "aliases", "merged_from", "conflicts"):
            d[k] = json.loads(d[k])
        return d

    @staticmethod
    def _edge(r) -> dict:
        d = dict(r)
        d["attrs"] = json.loads(d["attrs"])
        return d

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---- nodes ------------------------------------------------------------
    def get(self, nid: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()
        return self._node(r) if r else None

    def resolve(self, type_: str, surface: str) -> dict | None:
        """Dictionary-first entity linking: canonical key, then alias table."""
        n = self.get(node_id(type_, surface))
        if n:
            return n
        rows = self.conn.execute(
            "SELECT n.* FROM aliases a JOIN nodes n ON n.id=a.node_id WHERE a.alias_key=? AND n.type=?",
            (norm(surface), type_),
        ).fetchall()
        return self._node(rows[0]) if rows else None

    def resolve_any(self, ref: str) -> dict | None:
        """Accepts 'Type:Name' or a bare name (searched across all types, must be unique)."""
        if ":" in ref:
            t, n = parse_ref(ref)
            return self.resolve(t, n)
        key = norm(ref)
        rows = self.conn.execute(
            "SELECT DISTINCT n.* FROM nodes n LEFT JOIN aliases a ON a.node_id=n.id "
            "WHERE n.id LIKE ? OR a.alias_key=?", (f"%:{key}", key)).fetchall()
        rows = [r for r in rows if r["id"].split(":", 1)[1] == key or True]
        if len(rows) == 1:
            return self._node(rows[0])
        if len(rows) > 1:
            raise ValueError(f"'{ref}' is ambiguous: " + ", ".join(r["id"] for r in rows))
        return None

    def upsert_node(self, type_: str, name: str, attrs: dict | None = None, aliases=(),
                    source: str = "manual", confidence: str = "medium",
                    valid_from: str | None = None, valid_to: str | None = None) -> dict:
        attrs = dict(attrs or {})
        existing = self.resolve(type_, name)
        ts = now()
        if existing is None:
            nid = node_id(type_, name)
            self.conn.execute(
                "INSERT INTO nodes(id,type,name,attrs,aliases,source,confidence,extracted_at,valid_from,valid_to)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (nid, type_, name, _j(attrs), _j(sorted(set(aliases))), source, confidence, ts, valid_from, valid_to))
            self._index_aliases(nid, [name, *aliases])
            return self.get(nid)
        # merge policy: same source may overwrite itself; a different source never silently
        # overwrites — the conflicting value is recorded with provenance (stage 8 rule).
        merged = dict(existing["attrs"])
        conflicts = dict(existing["conflicts"])
        for k, v in attrs.items():
            if k not in merged or merged[k] == v or existing["source"] == source:
                merged[k] = v
            else:
                conflicts.setdefault(k, [{"value": merged[k], "source": existing["source"]}])
                if not any(c["value"] == v for c in conflicts[k]):
                    conflicts[k].append({"value": v, "source": source, "seen_at": ts})
        all_aliases = sorted(set(existing["aliases"]) | set(aliases) - {existing["name"]})
        if norm(name) != norm(existing["name"]):
            all_aliases = sorted(set(all_aliases) | {name})
        self.conn.execute(
            "UPDATE nodes SET attrs=?, aliases=?, conflicts=?, extracted_at=?, "
            "confidence=CASE WHEN ?='high' THEN 'high' ELSE confidence END WHERE id=?",
            (_j(merged), _j(all_aliases), _j(conflicts), ts, confidence, existing["id"]))
        self._index_aliases(existing["id"], [name, *aliases])
        return self.get(existing["id"])

    def _index_aliases(self, nid: str, names) -> None:
        for a in names:
            if a:
                self.conn.execute("INSERT OR IGNORE INTO aliases(alias_key,node_id) VALUES(?,?)", (norm(a), nid))

    def nodes(self, type_: str | None = None) -> list[dict]:
        q, p = "SELECT * FROM nodes", ()
        if type_:
            q, p = q + " WHERE type=?", (type_,)
        return [self._node(r) for r in self.conn.execute(q + " ORDER BY type, name", p)]

    def delete_node(self, nid: str) -> None:
        self.conn.execute("DELETE FROM edges WHERE src=? OR dst=?", (nid, nid))
        self.conn.execute("DELETE FROM aliases WHERE node_id=?", (nid,))
        self.conn.execute("DELETE FROM nodes WHERE id=?", (nid,))

    def update_node_raw(self, nid: str, **cols) -> None:
        sets, vals = [], []
        for k, v in cols.items():
            sets.append(f"{k}=?")
            vals.append(_j(v) if isinstance(v, (dict, list)) else v)
        self.conn.execute(f"UPDATE nodes SET {', '.join(sets)} WHERE id=?", (*vals, nid))

    # ---- edges ------------------------------------------------------------
    def add_edge(self, src: str, rel: str, dst: str, attrs: dict | None = None, source: str = "manual",
                 confidence: str = "medium", evidence: str | None = None,
                 valid_from: str | None = None, valid_to: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO edges(src,rel,dst,attrs,source,confidence,extracted_at,valid_from,valid_to,evidence)"
            " VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(src,rel,dst) DO UPDATE SET"
            " attrs=excluded.attrs, source=excluded.source, confidence=excluded.confidence,"
            " extracted_at=excluded.extracted_at, evidence=COALESCE(excluded.evidence, edges.evidence),"
            " valid_from=COALESCE(excluded.valid_from, edges.valid_from), valid_to=excluded.valid_to",
            (src, rel, dst, _j(attrs or {}), source, confidence, now(), valid_from, valid_to, evidence))

    def edges(self, nid: str, rel: str | None = None, direction: str = "both") -> list[dict]:
        out = []
        if direction in ("out", "both"):
            q, p = "SELECT * FROM edges WHERE src=?", [nid]
            if rel:
                q += " AND rel=?"; p.append(rel)
            out += [self._edge(r) for r in self.conn.execute(q, p)]
        if direction in ("in", "both"):
            q, p = "SELECT * FROM edges WHERE dst=?", [nid]
            if rel:
                q += " AND rel=?"; p.append(rel)
            out += [self._edge(r) for r in self.conn.execute(q, p)]
        return out

    def all_edges(self) -> list[dict]:
        return [self._edge(r) for r in self.conn.execute("SELECT * FROM edges ORDER BY src, rel, dst")]

    def delete_edge(self, eid: int) -> None:
        self.conn.execute("DELETE FROM edges WHERE id=?", (eid,))

    def counts(self) -> dict:
        n = {r["type"]: r["c"] for r in self.conn.execute("SELECT type, COUNT(*) c FROM nodes GROUP BY type")}
        e = self.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        return {"nodes": n, "edges": e}

    # ---- staging (stage 7) ------------------------------------------------
    def stage(self, kind: str, payload: dict, source: str, evidence: str | None, confidence: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO staging(kind,payload,source,evidence,confidence,created_at) VALUES(?,?,?,?,?,?)",
            (kind, _j(payload), source, evidence, confidence, now()))
        return cur.lastrowid

    def staging_rows(self, status: str | None = "pending") -> list[dict]:
        q, p = "SELECT * FROM staging", ()
        if status:
            q, p = q + " WHERE status=?", (status,)
        rows = self.conn.execute(q + " ORDER BY id", p).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def staging_set(self, ids, status: str, note: str | None = None) -> None:
        for i in ids:
            self.conn.execute("UPDATE staging SET status=?, note=COALESCE(?, note) WHERE id=?", (status, note, i))

    def add_candidate(self, kind: str, text: str, source: str) -> None:
        self.conn.execute("INSERT INTO candidates(kind,text,source,created_at) VALUES(?,?,?,?)",
                          (kind, text, source, now()))

    def candidates(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM candidates ORDER BY kind, text")]

    # ---- fusion review queue (stage 8) --------------------------------------
    def enqueue_review(self, a: str, b: str, score: float, reasons: list[str]) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO review_queue(a,b,score,reasons,created_at) VALUES(?,?,?,?,?)",
            (a, b, score, _j(reasons), now()))

    def review_rows(self, status: str = "pending") -> list[dict]:
        rows = self.conn.execute("SELECT * FROM review_queue WHERE status=? ORDER BY score DESC", (status,))
        return [{**dict(r), "reasons": json.loads(r["reasons"])} for r in rows]

    def review_set(self, a: str, b: str, status: str) -> None:
        self.conn.execute("UPDATE review_queue SET status=? WHERE (a=? AND b=?) OR (a=? AND b=?)",
                          (status, a, b, b, a))
