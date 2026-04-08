-- Sprint 05: Add alcohol_g column to foodtracker.food_logs
-- alcohol_g tracks alcohol content in grams.
-- Defaults to 0 so all existing rows are unaffected.
-- Used as a derived "alcohol" pseudo-meal-type in the report (alcohol_g > 0).

ALTER TABLE foodtracker.food_logs
  ADD COLUMN IF NOT EXISTS alcohol_g NUMERIC(7,1) NOT NULL DEFAULT 0
  CONSTRAINT food_logs_alcohol_g_nonneg CHECK (alcohol_g >= 0);
