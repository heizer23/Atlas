/**
 * Chronicle — local type definitions.
 *
 * These types reflect the named contracts declared in 20_design/architecture.json.
 * They are Chronicle-private — do not export from AtlasShell or platform-ui.
 */

/** CalendarEventViewRow — one row from shared_views.calendar_event_view */
export interface CalendarEventRow {
  date:         string;   // ISO date string YYYY-MM-DD
  application:  string;   // e.g. 'workout', 'food'
  source_label: string;   // e.g. 'Workout Days', 'Protein Intake'
  label:        string;
  value:        number;   // 1..100; missing day = frontend renders as 0
  selected:     boolean;
  detail:       string | null;
  deep_link:    string | null;
}

/** SourceListRow — distinct (application, source_label, selected) from the view */
export interface SourceListRow {
  application:  string;
  source_label: string;
  selected:     boolean;
}
