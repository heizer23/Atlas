"""Sprint 1.1: article master export, recipe import preview, assignment, activation, draft guards."""
import json
import os

import httpx

ST = os.environ.get("STORAGETRACKER_URL", "http://atlas-storagetracker-test:8000") + "/api"
K = "/api/kitchen"


def items():
    return httpx.get(f"{ST}/items", params={"kind": "ingredient"}).json()["rows"]


def new_article(name, unit, qty=0):
    r = httpx.post(f"{ST}/items", json={"name": name, "item_type": "consumable", "quantity": qty, "unit": unit})
    return r.json()["rows"][0]


def preview(client, payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    r = client.post(f"{K}/recipes/import/preview", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()["rows"][0]


def recipe_json(lines, **kw):
    rec = {"name": "Test soup", "kind": "favorite", "servings": 2, "ingredients": lines, "steps": ["cook"]}
    rec.update(kw)
    return {"format": "atlas.kitchen.recipe", "version": 1, "recipe": rec}


def save(client, prev, assignments=None):
    """Save the previewed recipe the way the UI does (POST /recipes with article ids)."""
    r = dict(prev["recipe"])
    lines = []
    for i, ln in enumerate(r["ingredients"]):
        ln = dict(ln)
        if assignments and i in assignments:
            ln["item_id"] = assignments[i]
        lines.append({k: ln[k] for k in ("name", "qty", "unit", "item_id", "base_recipe_id")})
    r["ingredients"] = lines
    for k in ("yield_unit",):
        r.pop(k, None)
    return client.post(f"{K}/recipes", json=r)


# 1 export master incl. zero stock, no batches
def test_master_includes_zero_stock_and_excludes_batches(client):
    httpx.post(f"{ST}/items", json={"name": "Dal 2030", "item_type": "consumable", "kind": "batch", "quantity": 3,
                                    "unit": "portions"})
    new_article("Zero stock item", "g", 0)
    rows = client.get(f"{K}/ingredients").json()["rows"]
    names = {r["name"] for r in rows}
    assert "Zero stock item" in names and "Red lentils" in names and "Dal 2030" not in names
    z = next(r for r in rows if r["name"] == "Zero stock item")
    assert z["unit"] == "g" and z["quantity"] == 0 and z["id"]


# 2 example JSON is importable as-is
def test_example_round_trips(client):
    ex = client.get(f"{K}/recipes/import-example").json()["rows"][0]["example"]
    p = preview(client, ex)
    assert p["ok"] and not p["errors"] and p["recipe"]["name"] == ex["recipe"]["name"]
    lines = ex["recipe"]["ingredients"]
    master = {r["id"]: r for r in client.get(f"{K}/ingredients").json()["rows"]}
    skus = ex["existing_skus"]  # full list for ChatGPT, incl. zero stock, no batches
    assert {s_["item_id"] for s_ in skus} == set(master) and len(skus) == len(master)
    assert all(set(s_) == {"item_id", "name", "unit"} and s_["name"] == master[s_["item_id"]]["name"] for s_ in skus)
    real = [l for l in lines if l["item_id"]]
    assert len(real) == 2 and all(master[l["item_id"]]["name"] == l["name"] and master[l["item_id"]]["unit"] == l["unit"]
                                  for l in real)
    assert p["unresolved"] == 1 and p["status_if_saved"] == "draft"
    assert save(client, p).status_code == 201


# 3 only known ids -> active
def test_known_ids_import_active(client):
    a, b = new_article("Reis", "g"), new_article("Wasser", "ml")
    p = preview(client, recipe_json([{"item_id": a["id"], "name": "egal", "qty": 100, "unit": "g"},
                                     {"item_id": b["id"], "qty": 300, "unit": "ml"}]))
    assert p["unresolved"] == 0 and p["status_if_saved"] == "active"
    assert {l["line_status"] for l in p["recipe"]["ingredients"]} == {"matched"}
    r = save(client, p)
    assert r.status_code == 201 and r.json()["rows"][0]["status"] == "active"


# 4-7 two unknown ingredients: assign one, create the other, then activate
def test_unknown_assign_create_activate(client):
    garam = new_article("Garam Masala", "g")
    p = preview(client, recipe_json([{"name": "garam masala", "qty": 2, "unit": "g"},
                                     {"name": "Frischer Ginger", "qty": 20, "unit": "g"}]))
    assert p["unresolved"] == 2
    assert p["recipe"]["ingredients"][0]["suggestions"][0]["id"] == garam["id"]  # exact name, case-insensitive
    # draft save keeps the recipe out of planning
    draft = save(client, p).json()["rows"][0]
    assert draft["status"] == "draft"
    assert client.post(f"{K}/plans/suggest", json={"week_start": "2031-01-06"}).status_code == 201
    pid = client.get(f"{K}/plans").json()["rows"][0]["id"]
    r = client.post(f"{K}/plans/{pid}/meals", json={"recipe_id": draft["id"], "day": "2031-01-06"})
    assert r.status_code == 409
    # explicit create of the second article (never automatic)
    n_before = len(items())
    c = client.post(f"{K}/ingredients", json={"name": "Frischer Ginger", "unit": "g"})
    assert c.status_code == 201 and len(items()) == n_before + 1
    assert c.json()["rows"][0]["quantity"] == 0
    assert client.post(f"{K}/ingredients", json={"name": "fresh  ginger", "unit": "g"}).status_code == 409
    # complete -> active (a repeated save under the same name is refused, so this is a renamed copy)
    p["recipe"]["name"] = "Test soup complete"
    done = save(client, p, {0: garam["id"], 1: c.json()["rows"][0]["id"]}).json()["rows"][0]
    assert done["status"] == "active"
    # editing a draft into completeness via PATCH also activates
    r2 = client.post(f"{K}/recipes", json={"name": "Draft2", "kind": "favorite", "servings": 1,
                     "ingredients": [{"name": "X", "qty": 1, "unit": "g"}]}).json()["rows"][0]
    assert r2["status"] == "draft"
    r3 = client.patch(f"{K}/recipes/{r2['id']}", json={"ingredients": [
        {"name": "X", "qty": 1, "unit": "g", "item_id": garam["id"]}]}).json()["rows"][0]
    assert r3["status"] == "active"


# 8/9 imported recipe in plan + shopping + cooking books via article ids
def test_imported_recipe_plans_shops_and_cooks_by_id(client):
    a = new_article("Import rice", "g", 100)
    p = preview(client, recipe_json([{"item_id": a["id"], "qty": 300, "unit": "g"}], name="Import dish", kind="base",
                                     servings=3, shelf_life_days=2))
    rid = save(client, p).json()["rows"][0]["id"]
    plan = client.post(f"{K}/plans/suggest", json={"week_start": "2031-02-03", "cook_sessions": 0}).json()["rows"][0]
    for m in plan["meals"]:
        client.delete(f"{K}/meals/{m['id']}")
    mid = client.post(f"{K}/plans/{plan['id']}/meals",
                      json={"recipe_id": rid, "day": "2031-02-03", "kind": "cook"}).json()["rows"][0]["id"]
    shop = client.get(f"{K}/plans/{plan['id']}/shopping").json()["rows"][0]
    line = next(l for l in shop["buy"] if l["item_id"] == a["id"])
    assert line["to_buy"] == 200 and line["name"] == "Import rice"
    # rename article: recipe link survives (identity is the id)
    httpx.patch(f"{ST}/items/{a['id']}", json={"name": "Import rice (renamed)"})
    shop = client.get(f"{K}/plans/{plan['id']}/shopping").json()["rows"][0]
    assert next(l for l in shop["buy"] if l["item_id"] == a["id"])["name"] == "Import rice (renamed)"
    client.post(f"{K}/shopping/purchase", json={"item_id": a["id"], "qty": 200})
    assert client.post(f"{K}/meals/{mid}/cooked").status_code == 200
    q = httpx.get(f"{ST}/items/{a['id']}").json()["rows"][0]["quantity"]
    assert q == 0
    mv = httpx.get(f"{ST}/items/{a['id']}/movements").json()["rows"]
    assert {m["reason"] for m in mv} >= {"purchase", "cook Import dish"}


def test_draft_recipe_cannot_cook_or_be_planned(client):
    p = preview(client, recipe_json([{"name": "Nowhere", "qty": 1, "unit": "g"}], name="Draftbase", kind="base"))
    draft = save(client, p).json()["rows"][0]
    assert draft["status"] == "draft"
    plan = client.post(f"{K}/plans/suggest", json={"week_start": "2031-03-03", "cook_sessions": 0}).json()["rows"][0]
    assert client.post(f"{K}/plans/{plan['id']}/meals",
                       json={"recipe_id": draft["id"], "day": "2031-03-03", "kind": "cook"}).status_code == 409


# 10 repeated import: no silent duplicate, no overwrite
def test_repeated_import_flags_existing_name(client):
    a = new_article("Dup rice", "g")
    payload = recipe_json([{"item_id": a["id"], "qty": 1, "unit": "g"}], name="Dup dish")
    first = preview(client, payload)
    assert first["name_exists"] is False
    rid = save(client, first).json()["rows"][0]["id"]
    again = preview(client, payload)
    assert again["name_exists"] is True
    assert save(client, again).status_code == 409
    rows = client.get(f"{K}/recipes").json()["rows"]
    assert sum(1 for r in rows if r["name"] == "Dup dish") == 1
    assert client.get(f"{K}/recipes/{rid}").json()["rows"][0]["ingredients"][0]["item_id"] == a["id"]


# no stock movements from import / creating articles
def test_import_creates_no_movements(client):
    a = new_article("Mvtest", "g", 5)
    p = preview(client, recipe_json([{"item_id": a["id"], "qty": 1, "unit": "g"}], name="Mv dish"))
    save(client, p)
    client.post(f"{K}/ingredients", json={"name": "New article", "unit": "g"})
    assert httpx.get(f"{ST}/items/{a['id']}/movements").json()["rows"] == []
    new = next(i for i in items() if i["name"] == "New article")
    assert httpx.get(f"{ST}/items/{new['id']}/movements").json()["rows"] == []


# error cases
def test_syntax_and_structure_errors(client):
    p = preview(client, '{"recipe": ')
    assert p["ok"] is False and "Invalid JSON" in p["errors"][0]["message"]
    p = preview(client, {"format": "atlas.kitchen.ingredient_master", "version": 1, "items": []})
    assert p["ok"] is False and "ingredient master" in p["errors"][0]["message"]
    p = preview(client, recipe_json([{"qty": -1, "unit": "g", "name": "a"}, {"qty": 1, "name": "b"}],
                                    kind="bogus", servings=0))
    paths = {e["path"] for e in p["errors"]}
    assert {"recipe.kind", "recipe.servings", "recipe.ingredients[0].qty", "recipe.ingredients[1].unit"} <= paths
    p = preview(client, recipe_json([{"item_id": "abc", "qty": 1, "unit": "g", "name": "a"}]))
    assert any(e["path"].endswith("item_id") for e in p["errors"])


def test_unknown_id_and_unit_mismatch(client):
    a = new_article("Flour", "g")
    ghost = 999999
    p = preview(client, recipe_json([{"item_id": ghost, "name": "Ghost", "qty": 1, "unit": "g"},
                                     {"item_id": a["id"], "qty": 1, "unit": "kg"}]))
    st_ = [l["line_status"] for l in p["recipe"]["ingredients"]]
    assert st_ == ["unknown_id", "unit_mismatch"] and p["unresolved"] == 2
    # saving an unknown id is rejected; a unit mismatch saves as draft (never converted)
    bad = save(client, p)
    assert bad.status_code == 400
    ok = client.post(f"{K}/recipes", json={"name": "Mismatch", "kind": "favorite", "servings": 1,
                     "ingredients": [{"name": "Flour", "qty": 1, "unit": "kg", "item_id": a["id"]}]})
    assert ok.status_code == 201 and ok.json()["rows"][0]["status"] == "draft"
    assert ok.json()["rows"][0]["ingredients"][0]["line_status"] == "unit_mismatch"


def test_base_recipe_reference(client):
    p = preview(client, recipe_json([{"base_recipe": "dal", "qty": 2}, {"base_recipe": "Does not exist", "qty": 1}],
                                    name="Derived dish", kind="derived"))
    lines = p["recipe"]["ingredients"]
    assert lines[0]["line_status"] == "base" and lines[0]["base_recipe_id"]
    assert lines[1]["line_status"] == "unknown_base"


def test_legacy_recipes_active_with_article_ids(client):
    rows = client.get(f"{K}/recipes").json()["rows"]
    assert rows and all(r["status"] == "active" for r in rows)
    dal = next(r for r in rows if r["name"] == "Dal")
    ings = client.get(f"{K}/recipes/{dal['id']}").json()["rows"][0]["ingredients"]
    assert all(i["item_id"] and i["line_status"] == "matched" for i in ings)
