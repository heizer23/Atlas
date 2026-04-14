"""
Sprint 07 — Base Quantity Reuse
Tests for: quantity_g → base_quantity rename in intake, entry detail, PUT edit, and copy.
Run inside atlas-food-tracker-test: docker exec atlas-food-tracker-test pytest tests/test_sprint07.py -v

Scenarios from 10_test_spec.md:
- [Backend] Intake with base_quantity scales macros proportionally
- [Backend] Intake without base_quantity stores absolute values with base_quantity 100
- [Backend] Intake with invalid base_quantity returns VALIDATION_ERROR
- [Backend] Entry detail GET returns base_quantity as non-null float
- [Backend] Entry detail GET returns base_quantity 100 for legacy-backfilled row
- [Backend] PUT entry accepts and stores updated base_quantity
- [Backend] PUT entry without base_quantity defaults to 100
- [Backend] Copy entry preserves base_quantity
"""

import json
import pytest

# ── Helpers ────────────────────────────────────────────────────────────────────

def _minimal_body(**overrides) -> str:
    """Minimal valid POST /api/food/meals body."""
    base: dict = {
        "timestamp": "2026-04-14T12:00:00",
        "meal_type": "lunch",
        "items": [{"name": "test dish"}],
        "nutrition": {
            "calories_kcal": 500,
            "protein_g":     30,
            "carbs_g":       40,
            "fat_g":         20,
        },
    }
    base.update(overrides)
    return json.dumps(base)


def _minimal_put_body(**overrides) -> str:
    """Minimal valid PUT /api/food/entries/{id} body."""
    base: dict = {
        "logged_at":  "2026-04-14T12:00:00",
        "meal_type":  "lunch",
        "dish_name":  "test dish",
        "kcal":       500,
        "protein_g":  30.0,
        "carbs_g":    40.0,
        "fat_g":      20.0,
    }
    base.update(overrides)
    return json.dumps(base)


# ── Intake scenarios ───────────────────────────────────────────────────────────

def test_intake_with_base_quantity_scales_macros_proportionally(client):
    """Intake with base_quantity: 200 scales macros from per-100g values."""
    body = json.dumps({
        "timestamp":    "2026-04-14T12:00:00",
        "meal_type":    "lunch",
        "base_quantity": 200,
        "items":        [{"name": "chicken breast"}],
        "nutrition": {
            "calories_kcal": 165,
            "protein_g":     31,
            "carbs_g":       0,
            "fat_g":         3.6,
        },
    })
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["kcal"] == 330
    assert row["protein_g"] == 62.0


def test_intake_without_base_quantity_stores_absolute_with_base_quantity_100(client):
    """Intake without base_quantity: macros stored as-is; base_quantity=100 stored."""
    body = _minimal_body()  # no base_quantity
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["kcal"] == 500

    # Verify base_quantity=100 was stored by fetching the detail
    entry_id = row["id"]
    r2 = client.get(f"/api/food/entries/{entry_id}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["base_quantity"] == 100.0


def test_intake_with_invalid_base_quantity_returns_validation_error(client):
    """base_quantity=0 is invalid; should return VALIDATION_ERROR 422."""
    body = json.dumps({
        "timestamp":    "2026-04-14T12:00:00",
        "meal_type":    "lunch",
        "base_quantity": 0,
        "items":        [{"name": "test dish"}],
        "nutrition": {
            "calories_kcal": 100,
            "protein_g":     10,
            "carbs_g":       10,
            "fat_g":         5,
        },
    })
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["detail"]["field"] == "base_quantity"


def test_intake_with_negative_base_quantity_returns_validation_error(client):
    """base_quantity=-1 is also invalid."""
    body = json.dumps({
        "timestamp":    "2026-04-14T12:00:00",
        "meal_type":    "lunch",
        "base_quantity": -1,
        "items":        [{"name": "test dish"}],
        "nutrition": {
            "calories_kcal": 100,
            "protein_g":     10,
            "carbs_g":       10,
            "fat_g":         5,
        },
    })
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 422
    assert r.json()["error"]["detail"]["field"] == "base_quantity"


# ── Entry detail scenarios ─────────────────────────────────────────────────────

def test_entry_detail_returns_base_quantity_as_non_null_float(client):
    """GET /api/food/entries/:id returns base_quantity as a float for fix-0001."""
    r = client.get("/api/food/entries/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 200
    detail = r.json()
    assert "base_quantity" in detail
    assert detail["base_quantity"] == 200.0
    assert "quantity_g" not in detail


def test_entry_detail_returns_base_quantity_100_for_legacy_backfilled_row(client):
    """GET /api/food/entries/:id returns base_quantity=100 for fix-0002 (legacy placeholder)."""
    r = client.get("/api/food/entries/00000000-0000-0000-0000-000000000002")
    assert r.status_code == 200
    detail = r.json()
    assert detail["base_quantity"] == 100.0


# ── PUT edit scenarios ────────────────────────────────────────────────────────

def test_put_entry_accepts_and_stores_updated_base_quantity(client):
    """PUT /api/food/entries/:id with base_quantity: 250 stores 250.0."""
    entry_id = "00000000-0000-0000-0000-000000000001"
    body = _minimal_put_body(
        logged_at="2026-04-10T12:00:00",
        dish_name="chicken breast updated",
        kcal=413,
        protein_g=77.5,
        carbs_g=0,
        fat_g=9.0,
        base_quantity=250,
    )
    r = client.put(f"/api/food/entries/{entry_id}", content=body)
    assert r.status_code == 200

    # Confirm stored value via GET
    r2 = client.get(f"/api/food/entries/{entry_id}")
    assert r2.status_code == 200
    assert r2.json()["base_quantity"] == 250.0


def test_put_entry_without_base_quantity_defaults_to_100(client):
    """PUT body missing base_quantity should default to 100."""
    entry_id = "00000000-0000-0000-0000-000000000001"
    body = _minimal_put_body(
        logged_at="2026-04-10T12:00:00",
        dish_name="chicken breast",
        kcal=330,
        protein_g=62.0,
        carbs_g=0.0,
        fat_g=7.2,
        # no base_quantity field
    )
    r = client.put(f"/api/food/entries/{entry_id}", content=body)
    assert r.status_code == 200

    r2 = client.get(f"/api/food/entries/{entry_id}")
    assert r2.status_code == 200
    assert r2.json()["base_quantity"] == 100.0


# ── Copy entry scenario ────────────────────────────────────────────────────────

def test_copy_entry_preserves_base_quantity(client):
    """POST /api/food/entries/:id/copy: new entry has same base_quantity as source."""
    source_id = "00000000-0000-0000-0000-000000000001"
    r = client.post(f"/api/food/entries/{source_id}/copy")
    assert r.status_code == 201
    copied = r.json()
    assert copied["base_quantity"] == 200.0
    # Same macro values as source
    assert copied["kcal"] == 330
    assert copied["protein_g"] == 62.0
