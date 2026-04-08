BEGIN;

CREATE SCHEMA IF NOT EXISTS foodtracker;

CREATE TABLE IF NOT EXISTS foodtracker.food_logs (
  id UUID PRIMARY KEY,

  logged_at TIMESTAMP NOT NULL,
  meal_type TEXT NOT NULL,
  dish_name TEXT NOT NULL,

  -- Environmental tracking
  meat_g NUMERIC(7,1) NOT NULL DEFAULT 0,
  red_meat_g NUMERIC(7,1) NOT NULL DEFAULT 0,

  -- Energy
  kcal NUMERIC(7,0) NOT NULL DEFAULT 0,

  -- Macros
  protein_g NUMERIC(7,1) NOT NULL DEFAULT 0,
  carbs_g   NUMERIC(7,1) NOT NULL DEFAULT 0,
  fiber_g   NUMERIC(7,1) NOT NULL DEFAULT 0,
  fat_g     NUMERIC(7,1) NOT NULL DEFAULT 0,
  good_fat_g NUMERIC(7,1) NOT NULL DEFAULT 0,

  -- Micro (minimal)
  sodium_mg NUMERIC(7,0) NOT NULL DEFAULT 0,

  -- Quality indicator
  confidence SMALLINT NOT NULL DEFAULT 3,

  -- Alcohol tracking (Sprint 05)
  -- Tracks alcohol content in grams. Default 0; used to derive the "alcohol"
  -- pseudo-meal-type column in reports (entries where alcohol_g > 0).
  alcohol_g NUMERIC(7,1) NOT NULL DEFAULT 0,

  -- Optional context
  notes TEXT,

  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- Constraints
  CHECK (meat_g >= 0),
  CHECK (red_meat_g >= 0),
  CHECK (red_meat_g <= meat_g),

  CHECK (kcal >= 0),

  CHECK (protein_g >= 0),
  CHECK (carbs_g >= 0),
  CHECK (fiber_g >= 0),
  CHECK (fat_g >= 0),
  CHECK (good_fat_g >= 0),
  CHECK (good_fat_g <= fat_g),

  CHECK (sodium_mg >= 0),

  CHECK (confidence BETWEEN 1 AND 5),

  CONSTRAINT food_logs_alcohol_g_nonneg CHECK (alcohol_g >= 0)
);

CREATE INDEX IF NOT EXISTS idx_food_logs_logged_at ON foodtracker.food_logs (logged_at);
CREATE INDEX IF NOT EXISTS idx_food_logs_meal_type ON foodtracker.food_logs (meal_type);

COMMIT;
