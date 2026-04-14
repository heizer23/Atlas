-- FoodTracker Sprint 07 test fixtures
-- IDs use deterministic UUIDs for readability.
-- Sprint 07: quantity_g renamed to base_quantity; NULLs replaced with 100 (NOT NULL after migration).
-- fix-0001: scaled-chicken — 200g chicken breast (macros scaled from per-100g)
-- fix-0002: absolute-salad — direct absolute values, base_quantity=100 (legacy placeholder)
-- fix-0003: wine — alcohol entry with alcohol_g set, base_quantity=100

INSERT INTO foodtracker.food_logs (
    id, logged_at, meal_type, dish_name,
    kcal, protein_g, carbs_g, fat_g, fiber_g, good_fat_g,
    meat_g, red_meat_g, sodium_mg, alcohol_g, confidence, notes,
    standard, source_standard_id, base_quantity
) VALUES
-- fix-0001: scaled-chicken — 200g of chicken breast (stored macros are scaled from per-100g)
-- per-100g: kcal=165, protein=31, carbs=0, fat=3.6 → at 200g: kcal=330, protein=62, fat=7.2
(
    '00000000-0000-0000-0000-000000000001',
    '2026-04-10T12:00:00',
    'lunch',
    'chicken breast',
    330, 62.0, 0.0, 7.2, 0.0, 0.0,
    200.0, 0.0, 148.0, 0.0, 4, NULL,
    FALSE, NULL, 200.0
),
-- fix-0002: absolute-salad — direct absolute values; base_quantity=100 (legacy placeholder)
(
    '00000000-0000-0000-0000-000000000002',
    '2026-04-10T19:00:00',
    'dinner',
    'caesar salad',
    450, 12.0, 20.0, 30.0, 3.0, 10.0,
    0.0, 0.0, 600.0, 0.0, 3, 'dressing included',
    FALSE, NULL, 100.0
),
-- fix-0003: wine — alcohol entry with alcohol_g set; base_quantity=100
(
    '00000000-0000-0000-0000-000000000003',
    '2026-04-11T20:00:00',
    'drink',
    'glass of wine',
    120, 0.1, 3.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 5.0, 14.0, 3, NULL,
    FALSE, NULL, 100.0
);
