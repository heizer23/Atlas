BEGIN;

-- Sprint 07: rename quantity_g → base_quantity in foodtracker.food_logs.
-- base_quantity has a unified semantic: the quantity that the stored nutrition
-- values refer to. Always non-null after this migration.

-- Step 1: backfill legacy NULLs to 100 (placeholder; user corrects over time)
UPDATE foodtracker.food_logs
  SET quantity_g = 100
  WHERE quantity_g IS NULL;

-- Step 2: rename column
ALTER TABLE foodtracker.food_logs
  RENAME COLUMN quantity_g TO base_quantity;

-- Step 3: add NOT NULL constraint and DEFAULT 100
ALTER TABLE foodtracker.food_logs
  ALTER COLUMN base_quantity SET NOT NULL,
  ALTER COLUMN base_quantity SET DEFAULT 100;

-- Step 4: replace old constraint (named after the old column)
ALTER TABLE foodtracker.food_logs
  DROP CONSTRAINT food_logs_quantity_g_pos;

ALTER TABLE foodtracker.food_logs
  ADD CONSTRAINT food_logs_base_quantity_pos CHECK (base_quantity > 0);

COMMIT;
