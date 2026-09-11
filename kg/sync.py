"""Push the graph's catalog to a commerce / payment platform. THE GRAPH IS THE SOURCE OF TRUTH.
Flow: snapshot(graph) -> adapter.fetch(platform) -> diff -> print plan -> human approves -> adapter.apply
-> external ids written back to seeds/14_platform_ids.yaml -> kg ingest.
Credentials: adapters read their API key from the environment at runtime; nothing here stores or prints one."""
from __future__ import annotations

import csv
import dataclasses
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

from . import serve
from .store import ROOT, Store

RUO_LINE = "For Research Use Only — Not for Human Consumption."
SYNC_STATUSES = ("active", "coming_soon")   # draft / discontinued never leave the graph
PLATFORM_IDS_SEED = ROOT / "seeds" / "14_platform_ids.yaml"


@dataclass
class CatalogItem:
    sku: str
    name: str
    family: str            # variant grouping: the peptide or blend name ("BPC-157", "BPC-157 / TB-500")
    variant: str           # what distinguishes the SKU inside the family ("5mg")
    price_usd: float
    status: str            # active | coming_soon
    quantity: float
    form: str = ""
    size_mg: float | None = None
    slug: str = ""
    description: str = ""
    external_id: str | None = None
    extra: dict = field(default_factory=dict)

    def key(self) -> str:
        return self.sku


COMPARED = ("name", "family", "variant", "price_usd", "status", "quantity", "form", "size_mg", "slug", "description")


def snapshot(store: Store) -> list[CatalogItem]:
    """Every sellable Product as a platform-neutral catalog item, with stock from the ledger."""
    stock = {r["product"]: r["on_hand"] for r in serve.stock(store)}
    items = []
    for p in store.nodes("Product"):
        a = p["attrs"]
        if a.get("status") not in SYNC_STATUSES or not a.get("sku"):
            continue
        peptides = [store.get(e["dst"]) for e in store.edges(p["id"], "CONTAINS", "out")]
        family = " / ".join(x["name"] for x in peptides) or p["name"]
        size_tag = f"{a['size_mg']:g}mg" if a.get("size_mg") else f"{a.get('size_ml', ''):g}ml"
        variant = p["name"].replace(family, "").strip() if family in p["name"] else size_tag
        variant = variant or size_tag
        summaries = [x["attrs"].get("summary") for x in peptides if x["attrs"].get("summary")]
        size = f"{a.get('size_mg')} mg" if a.get("size_mg") else f"{a.get('size_ml')} ml"
        purity = f", tested to a purity specification of {a['purity_spec'].replace('>=', '≥')}" if a.get("purity_spec") else ""
        comp_edges = store.edges(p["id"], "CONTAINS", "out")
        composition = ""
        if len(comp_edges) > 1:
            parts = sorted(((store.get(e["dst"])["name"], e["attrs"].get("amount_mg")) for e in comp_edges), key=lambda x: -(x[1] or 0))
            composition = "Composition per vial: " + ", ".join(f"{n} {m} mg" if m else n for n, m in parts) + "."
        summaries = [composition] + summaries if composition else summaries
        desc = " ".join(summaries + [f"Supplied as {a.get('form', 'lyophilized powder')}, {size} per vial{purity}.", RUO_LINE])
        items.append(CatalogItem(
            sku=a["sku"], name=p["name"], family=family, variant=variant, price_usd=float(a.get("price_usd", 0)),
            status=a["status"], quantity=float(stock.get(p["name"], 0)), form=a.get("form", ""),
            size_mg=a.get("size_mg") or a.get("size_ml"), slug=a.get("slug", ""), description=desc, external_id=a.get("external_id"),
            extra={"display_name": a.get("display_name")} if a.get("display_name") else {}))
    return sorted(items, key=lambda i: (i.family, i.size_mg or 0))


@dataclass
class Plan:
    create: list[CatalogItem] = field(default_factory=list)
    update: list[tuple[CatalogItem, CatalogItem, dict]] = field(default_factory=list)   # (local, remote, changed fields)
    orphan: list[CatalogItem] = field(default_factory=list)   # on the platform, not in the graph: reported, NEVER deleted
    unchanged: int = 0

    def empty(self) -> bool:
        return not (self.create or self.update)


def diff(local: list[CatalogItem], remote: list[CatalogItem], compared: tuple[str, ...] = COMPARED) -> Plan:
    plan = Plan()
    remote_by = {r.key(): r for r in remote}
    for l in local:
        r = remote_by.pop(l.key(), None)
        if r is None:
            plan.create.append(l)
            continue
        changed = {f: (getattr(r, f), getattr(l, f)) for f in compared if _neq(getattr(r, f), getattr(l, f))}
        if changed:
            plan.update.append((l, r, changed))
        else:
            plan.unchanged += 1
    plan.orphan = list(remote_by.values())
    return plan


def _neq(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > 1e-9
    return (a or "") != (b or "")


def plan_text(plan: Plan, platform: str) -> str:
    lines = [f"# Sync plan -> {platform}: create {len(plan.create)}, update {len(plan.update)}, unchanged {plan.unchanged}, orphans {len(plan.orphan)}"]
    for i in plan.create:
        lines.append(f"CREATE  {i.sku:<16} {i.name:<28} ${i.price_usd:<8.2f} qty {i.quantity:g}  [{i.status}]")
    for l, r, ch in plan.update:
        lines.append(f"UPDATE  {l.sku:<16} " + "; ".join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in ch.items()))
    for o in plan.orphan:
        lines.append(f"ORPHAN  {o.sku:<16} exists on {platform} but not in the graph — left untouched; add it to seeds or archive it on the platform yourself")
    if plan.empty():
        lines.append("Nothing to apply.")
    return "\n".join(lines)


# ---- adapters ---------------------------------------------------------------
class Adapter(Protocol):
    name: str
    def fetch(self) -> list[CatalogItem]: ...
    def apply(self, plan: Plan) -> dict[str, str]: ...   # returns {sku: external_id} for created/updated items


class FileAdapter:
    """Platform stand-in: keeps the 'remote' catalog in a JSON file. Use it to rehearse a sync, or export
    CSV for a platform's bulk-import screen when there is no API."""
    name = "file"

    def __init__(self, path: Path | None = None):
        self.path = Path(path or ROOT / "data" / "catalog.file.json")

    def fetch(self) -> list[CatalogItem]:
        if not self.path.exists():
            return []
        return [CatalogItem(**d) for d in json.loads(self.path.read_text())]

    def apply(self, plan: Plan) -> dict[str, str]:
        current = {i.sku: i for i in self.fetch()}
        ids = {}
        for i in plan.create:
            i.external_id = i.external_id or f"file_{i.sku.lower()}"
            current[i.sku] = i; ids[i.sku] = i.external_id
        for l, r, _ in plan.update:
            l.external_id = r.external_id or l.external_id
            current[l.sku] = l; ids[l.sku] = l.external_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([dataclasses.asdict(i) for i in current.values()], indent=2))
        return ids


class KashuAdapter:
    """Kashu Pay (white-label TagadaPay) product catalog. One Kashu product per SKU, one variant, USD price in cents.
    Kashu has no stock quantity and ignores inStock, so availability is the product's `active` flag:
    active = the graph says active AND on hand > 0. Kashu cannot edit a variant after creation, so a price change
    deletes and recreates that SKU's product (safe: checkout is direct S2S and never references Kashu product ids).
    Name, description and active are updated in place. Credentials come from web/.dev.vars; nothing is printed."""
    name = "kashu"
    compare = ("name", "price_usd", "status", "description")
    BASE = "https://api.tagada.io/api/public/v1"

    def __init__(self, store_id: str | None = None):
        env = {}
        for line in (ROOT / "web" / ".dev.vars").read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1); env[k.strip()] = v.strip()
        self.key = env.get("TAGADA_API_KEY") or ""
        self.store_id = store_id or env.get("TAGADA_CATALOG_STORE_ID") or ""
        if not self.key or not self.store_id:
            raise SystemExit("kashu adapter needs TAGADA_API_KEY and TAGADA_CATALOG_STORE_ID (or --store) in web/.dev.vars")

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        import urllib.request, urllib.error
        req = urllib.request.Request(self.BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"authorization": f"Bearer {self.key}", "accept": "application/json", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Kashu {method} {path} failed ({e.code}): {e.read().decode()[:300]}")

    @staticmethod
    def title(it: CatalogItem) -> str:
        disp = it.extra.get("display_name")
        if not disp:
            return it.name
        return f"{disp} {it.variant} ({it.family})" if " / " in it.family else f"{disp} {it.variant}"   # "KLOW 80mg (BPC-157 / …)", "NAD+ (buffered) 500mg"

    def project(self, it: CatalogItem) -> CatalogItem:
        """Local item as Kashu would hold it."""
        return dataclasses.replace(it, name=self.title(it), status="active" if (it.status == "active" and it.quantity > 0) else "inactive")

    def fetch(self) -> list[CatalogItem]:
        out, page = [], 1
        while True:
            d = self._call("POST", "/products/list", {"storeId": self.store_id, "page": page, "per_page": 100, "includeVariants": True})
            for p in d.get("items", []):
                v = (p.get("variants") or [{}])[0]
                sku = v.get("sku") or ""
                if not sku.startswith("EP-"):
                    continue          # never touch products this sync did not create
                amount = ((v.get("prices") or [{}])[0].get("currencyOptions") or {}).get("USD", {}).get("amount", 0)
                out.append(CatalogItem(sku=sku, name=p["name"], family="", variant=v.get("name", ""), price_usd=amount / 100,
                                       status="active" if p.get("active") else "inactive", quantity=0,
                                       description=p.get("description") or "", external_id=p["id"]))
            if not (d.get("pagination") or {}).get("hasNext"):
                return out
            page += 1

    def _create(self, it: CatalogItem) -> str:
        body = {"storeId": self.store_id, "name": it.name, "description": it.description, "active": it.status == "active",
                "isShippable": True, "isTaxable": True, "unitLabel": "vial",
                "variants": [{"name": it.variant or it.name, "sku": it.sku, "active": True, "default": True,
                              "prices": [{"currencyOptions": {"USD": {"amount": round(it.price_usd * 100)}}, "recurring": False, "default": True}]}]}
        return self._call("POST", "/products/create", body)["id"]

    def apply(self, plan: Plan) -> dict[str, str]:
        ids = {}
        for it in plan.create:
            ids[it.sku] = self._create(it)
        for l, r, changed in plan.update:
            if "price_usd" in changed:
                self._call("POST", "/products/delete", {"productIds": [r.external_id]})
                ids[l.sku] = self._create(l)
            else:
                self._call("PUT", f"/products/{r.external_id}", {"updatedData": {"name": l.name, "description": l.description, "active": l.status == "active"}})
                ids[l.sku] = r.external_id
        return ids


ADAPTERS: dict[str, type] = {"file": FileAdapter, "kashu": KashuAdapter}


def get_adapter(name: str, store: str | None = None) -> Adapter:
    if name not in ADAPTERS:
        raise SystemExit(f"no adapter '{name}'. Available: {', '.join(ADAPTERS)}. Add one in kg/sync.py (fetch + apply).")
    return ADAPTERS[name](store) if name == "kashu" else ADAPTERS[name]()


def plan_for(adapter, local: list[CatalogItem]) -> Plan:
    projected = [adapter.project(i) for i in local] if hasattr(adapter, "project") else local
    return diff(projected, adapter.fetch(), getattr(adapter, "compare", COMPARED))


# ---- export for bulk import screens ------------------------------------------
def export_csv(items: list[CatalogItem]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sku", "name", "family", "variant", "price_usd", "quantity", "status", "form", "size_mg", "slug", "description"])
    for i in items:
        w.writerow([i.sku, i.name, i.family, i.variant, f"{i.price_usd:.2f}", f"{i.quantity:g}", i.status, i.form, i.size_mg or "", i.slug, i.description])
    return buf.getvalue()


# ---- write-back --------------------------------------------------------------
def write_back_ids(ids: dict[str, str], platform: str, store: Store, path: Path = PLATFORM_IDS_SEED) -> int:
    """Record platform ids as a generated seed file (so ingest stays the only write path into the graph)."""
    existing = {}
    if path.exists():
        for it in (yaml.safe_load(path.read_text()) or {}).get("items", []):
            existing[it["name"]] = it["attrs"]
    sku_to_name = {p["attrs"].get("sku"): p["name"] for p in store.nodes("Product")}
    for sku, ext in ids.items():
        name = sku_to_name.get(sku)
        if name and ext:
            existing[name] = {"external_id": str(ext), "platform": platform}
    doc = {"type": "Product", "source": f"kg sync ({platform}) — generated, do not edit", "confidence": "high",
           "items": [{"name": n, "attrs": a} for n, a in sorted(existing.items())]}
    path.write_text("# GENERATED by `kg sync apply`. Platform ids for Product nodes. Safe to delete and regenerate.\n"
                    + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return len(existing)
