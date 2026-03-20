-- Migration: move existing data from public.food_logs to foodtracker.food_logs.
-- Safe to run when public.food_logs does not exist (the DO block checks first).
BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'food_logs'
  ) THEN
    INSERT INTO foodtracker.food_logs
      SELECT * FROM public.food_logs
      ON CONFLICT (id) DO NOTHING;

    DROP TABLE public.food_logs;

    RAISE NOTICE 'Migrated public.food_logs -> foodtracker.food_logs and dropped source table.';
  ELSE
    RAISE NOTICE 'public.food_logs does not exist, nothing to migrate.';
  END IF;
END
$$;

COMMIT;
