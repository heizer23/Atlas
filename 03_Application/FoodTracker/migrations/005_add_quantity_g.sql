-- Sprint 06: Add quantity_g column to foodtracker.food_logs
-- quantity_g stores the consumed quantity in grams when the entry was logged
-- using per-100g reference values. NULL means the entry was logged with direct
-- absolute macro values (existing behavior).

ALTER TABLE foodtracker.food_logs
  ADD COLUMN IF NOT EXISTS quantity_g NUMERIC(7,1) DEFAULT NULL
  CONSTRAINT food_logs_quantity_g_pos CHECK (quantity_g IS NULL OR quantity_g > 0);
