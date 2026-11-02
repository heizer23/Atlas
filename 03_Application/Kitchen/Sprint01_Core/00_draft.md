# Atlas Kitchen – Sprint 1 (Draft, condensed from the vision brief)

## Goal
Week plan -> shopping list -> stock check -> cook -> automatic inventory update -> eat. Prepared bases (e.g. Dal,
Bolognese) are inventory items that other recipes consume. Minimal manual stock keeping: stock follows activities,
occasional stocktakes correct drift.

## Layer / Component
03_Application / Kitchen (stock via StorageTracker, extended with units, batches and a movement ledger).

## Scope
A recipes (base / derived / favorite, derived can reference bases) · B week plan (7 days, 2 cook sessions, swap/move)
· C shopping list (buy vs. probably-have, confirm/correct, purchases update stock) · D cook = backflush, idempotent
· E eat = book base portions + extras; skipped/moved meals book nothing.

## Out of Scope
Consumption statistics, AI nutrition correction, preference learning, shelf-life forecasting, full nutrient DB,
full Foodtracker integration (model must allow it later).

## Acceptance
1 plan with Dal+Bolognese · 2 consolidated list · 3 check/correct stock · 4 cook 6 Dal as new inventory item · 5 raw
ingredients booked · 6 two portions with eggs+spinach · 7 two with chicken · 8 two left in inventory · 9 move a meal
without movement · 10 whole flow on the mobile Atlas UI.
Automated: `Kitchen/tests/test_acceptance.py` (1-9). Manual: 10.
