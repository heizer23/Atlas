"""
FoodTracker — Sprint 06 tests

Covers: base_quantity (formerly quantity_g) intake scaling, entry detail/edit/copy,
report alcohol_g_total column, avg scope extension to week/month.

Sprint 07 note: quantity_g was renamed to base_quantity. Tests updated accordingly.

Traceability: scenario names map to Sprint06_Search_Scale_Averages/10_test_spec.md.
"""

import json
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _meal_body(base_quantity=None, kcal=165, protein_g=31, carbs_g=0, fat_g=3.6,
               alcohol_g=0, good_fat_g=0, meat_g=100, red_meat_g=0, sodium_mg=74):
    """Build a valid POST /api/food/meals body."""
    body = {
        "timestamp": "2026-04-14T12:00:00",
        "meal_type": "lunch",
        "items": [{"name": "chicken breast"}],
        "nutrition": {
            "calories_kcal": kcal,
            "protein_g":     protein_g,
            "carbs_g":       carbs_g,
            "fat_g":         fat_g,
            "alcohol_g":     alcohol_g,
            "good_fat_g":    good_fat_g,
            "meat_g":        meat_g,
            "red_meat_g":    red_meat_g,
            "sodium_mg":     sodium_mg,
        },
    }
    if base_quantity is not None:
        body["base_quantity"] = base_quantity
    return json.dumps(body)


# ── [Backend] Intake with base_quantity scales macros proportionally ──────────

def test_intake_with_quantity_g_scales_macros_proportionally(client):
    """POST /api/food/meals with base_quantity=200 and per-100g kcal=165 → stored kcal=330."""
    body = _meal_body(base_quantity=200, kcal=165, protein_g=31)
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["kcal"] == 330
    assert abs(row["protein_g"] - 62.0) < 0.5


# ── [Backend] Intake without base_quantity stores absolute values ─────────────

def test_intake_without_quantity_g_stores_absolute_values(client):
    """POST /api/food/meals without base_quantity stores kcal=500 directly."""
    body = _meal_body(kcal=500, protein_g=30)
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["kcal"] == 500


# ── [Backend] Intake with invalid base_quantity returns VALIDATION_ERROR ──────

def test_intake_with_invalid_quantity_g_returns_validation_error(client):
    """POST /api/food/meals with base_quantity=0 returns 422 VALIDATION_ERROR."""
    body = _meal_body(base_quantity=0)
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "base_quantity" in r.json()["error"]["detail"]["field"]


def test_intake_with_negative_quantity_g_returns_validation_error(client):
    """POST /api/food/meals with base_quantity=-50 returns 422 VALIDATION_ERROR."""
    body = _meal_body(base_quantity=-50)
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── [Backend] Cross-field checks apply to per-100g values before scaling ──────

def test_cross_field_checks_apply_to_per_100g_values_before_scaling(client):
    """POST /api/food/meals with good_fat_g > fat_g in per-100g values returns 422."""
    # good_fat=20 > fat=15 in per-100g values
    body = _meal_body(base_quantity=150, fat_g=15, good_fat_g=20)
    r = client.post("/api/food/meals", content=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── [Backend] Entry detail GET includes base_quantity ────────────────────────

def test_entry_detail_get_includes_quantity_g(client):
    """GET /api/food/entries/fix-0001 returns base_quantity: 200.0."""
    r = client.get("/api/food/entries/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 200
    assert r.json()["base_quantity"] == 200.0


# ── [Backend] Entry detail GET returns base_quantity=100 for legacy row ───────

def test_entry_detail_get_returns_null_quantity_g_for_legacy_row(client):
    """GET /api/food/entries/fix-0002 returns base_quantity: 100.0 (backfilled legacy)."""
    r = client.get("/api/food/entries/00000000-0000-0000-0000-000000000002")
    assert r.status_code == 200
    assert r.json()["base_quantity"] == 100.0


# ── [Backend] PUT entry accepts and stores updated base_quantity ──────────────

def test_put_entry_accepts_and_stores_updated_quantity_g(client):
    """PUT /api/food/entries/fix-0001 with base_quantity=250 stores 250."""
    body = json.dumps({
        "logged_at":     "2026-04-10T12:00:00",
        "meal_type":     "lunch",
        "dish_name":     "chicken breast",
        "kcal":          413,
        "protein_g":     77.5,
        "carbs_g":       0.0,
        "fat_g":         9.0,
        "fiber_g":       0.0,
        "good_fat_g":    0.0,
        "meat_g":        250.0,
        "red_meat_g":    0.0,
        "sodium_mg":     185.0,
        "alcohol_g":     0.0,
        "confidence":    4,
        "base_quantity": 250,
    })
    r = client.put("/api/food/entries/00000000-0000-0000-0000-000000000001", content=body)
    assert r.status_code == 200
    # Verify stored value via GET
    r2 = client.get("/api/food/entries/00000000-0000-0000-0000-000000000001")
    assert r2.status_code == 200
    assert r2.json()["base_quantity"] == 250.0


# ── [Backend] Copy entry preserves base_quantity ─────────────────────────────

def test_copy_entry_preserves_quantity_g(client):
    """POST /api/food/entries/fix-0001/copy preserves base_quantity=200."""
    r = client.post("/api/food/entries/00000000-0000-0000-0000-000000000001/copy")
    assert r.status_code == 201
    assert r.json()["base_quantity"] == 200.0
    # macros preserved (not re-scaled)
    assert r.json()["kcal"] == 330


def test_copy_entry_with_null_quantity_g_preserves_null(client):
    """POST /api/food/entries/fix-0002/copy: base_quantity=100 preserved."""
    r = client.post("/api/food/entries/00000000-0000-0000-0000-000000000002/copy")
    assert r.status_code == 201
    assert r.json()["base_quantity"] == 100.0


# ── [Backend] Report includes alcohol_g_total in all scopes ───────────────────

def test_report_includes_alcohol_g_total_in_year_scope(client):
    """GET /api/food/report?scope=year includes alcohol_g_total in every row."""
    r = client.get("/api/food/report?scope=year&mode=daily")
    assert r.status_code == 200
    data = r.json()
    # Schema must include alcohol_g_total
    schema_keys = [c["key"] for c in data["schema"]]
    assert "alcohol_g_total" in schema_keys
    # All rows must have the field
    for row in data["rows"]:
        assert "alcohol_g_total" in row


def test_report_includes_alcohol_g_total_in_all_time_scope(client):
    """GET /api/food/report?scope=all_time includes alcohol_g_total."""
    r = client.get("/api/food/report?scope=all_time&mode=aggregated")
    assert r.status_code == 200
    schema_keys = [c["key"] for c in r.json()["schema"]]
    assert "alcohol_g_total" in schema_keys


# ── [Backend] Report includes avg columns for week and month scopes ───────────

def test_report_includes_avg_columns_for_week_scope(client):
    """GET /api/food/report?scope=week includes kcal_avg, protein_avg, alcohol_g_avg."""
    r = client.get("/api/food/report?scope=week&mode=daily")
    assert r.status_code == 200
    data = r.json()
    schema_keys = [c["key"] for c in data["schema"]]
    assert "kcal_avg" in schema_keys
    assert "protein_avg" in schema_keys
    assert "alcohol_g_avg" in schema_keys
    for row in data["rows"]:
        assert "kcal_avg" in row
        assert "protein_avg" in row
        assert "alcohol_g_avg" in row


def test_report_includes_avg_columns_for_month_scope(client):
    """GET /api/food/report?scope=month includes avg columns."""
    r = client.get("/api/food/report?scope=month&mode=daily")
    assert r.status_code == 200
    schema_keys = [c["key"] for c in r.json()["schema"]]
    assert "kcal_avg" in schema_keys
    assert "alcohol_g_avg" in schema_keys


# ── [Backend] Report does not include avg columns for all_time scope ──────────

def test_report_does_not_include_avg_columns_for_all_time_scope(client):
    """GET /api/food/report?scope=all_time does not include avg columns."""
    r = client.get("/api/food/report?scope=all_time&mode=aggregated")
    assert r.status_code == 200
    schema_keys = [c["key"] for c in r.json()["schema"]]
    assert "kcal_avg" not in schema_keys
    assert "protein_avg" not in schema_keys
    assert "alcohol_g_avg" not in schema_keys


# ── [Backend] alcohol_g_avg cumulative average is correct ────────────────────

def test_alcohol_g_avg_cumulative_average_is_correct(client, db_conn):
    """
    Two rows: day1 alcohol=10, day2 alcohol=20.
    Expected avg day1=10.0, day2=15.0 (cumulative over reported days).
    """
    # Use db_conn to insert directly with known dates within the last week
    # Sprint 07: base_quantity uses DEFAULT 100 (omitted from INSERT)
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO foodtracker.food_logs (
                id, logged_at, meal_type, dish_name,
                kcal, protein_g, carbs_g, fat_g, fiber_g, good_fat_g,
                meat_g, red_meat_g, sodium_mg, alcohol_g, confidence,
                standard, source_standard_id
            ) VALUES
            ('00000000-0000-0000-0000-000000000004', NOW() - INTERVAL '6 days', 'drink', 'beer',
             100, 0, 5, 0, 0, 0, 0, 0, 0, 10.0, 3, FALSE, NULL),
            ('00000000-0000-0000-0000-000000000005', NOW() - INTERVAL '5 days', 'drink', 'wine',
             120, 0, 3, 0, 0, 0, 0, 0, 0, 20.0, 3, FALSE, NULL)
        """)

    r = client.get("/api/food/report?scope=week&mode=daily")
    assert r.status_code == 200
    rows = r.json()["rows"]
    # Find the two rows with alcohol data
    alc_rows = [row for row in rows if row.get("alcohol_g_total", 0) > 0]
    assert len(alc_rows) >= 2
    # First reported day: avg = 10 / 1 = 10.0
    # Second reported day: avg = (10 + 20) / 2 = 15.0
    avgs = [row["alcohol_g_avg"] for row in alc_rows]
    assert avgs[0] == 10.0
    assert avgs[1] == 15.0
