/**
 * PersonalDevelopment — domain type definitions.
 * Used across all Learning tile frontend files.
 */

export interface TrainingUnitRow {
  id: string;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  labels: { id: string; name: string }[];
  last_child_completed_at: string | null;
  completed_child_count: number;
  total_child_count: number;
  actual_duration_minutes: number | null;
  completed_at: string | null;
}

export interface ChildTaskRow {
  id: string;
  title: string;
  status: string;
  priority: string;
  actual_duration_minutes: number | null;
  completed_at: string | null;
  task_type: string;
}

export interface UncheckedSubtask {
  lineText: string;
}

export interface ActivatedSubtask {
  lineText: string;
  taskId: string;
}
