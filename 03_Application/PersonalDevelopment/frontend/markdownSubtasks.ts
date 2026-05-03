/**
 * PersonalDevelopment — markdownSubtasks.ts
 *
 * Pure functions for parsing and updating the ## Potential Subtasks section
 * in task.description. No React dependency — unit-testable in isolation.
 *
 * Unchecked line format:  - [ ] <title>
 * Activated line format:  - [x] <title> → task: <uuid>
 */

import type { UncheckedSubtask, ActivatedSubtask } from './types';

export const POTENTIAL_SUBTASKS_HEADING = '## Potential Subtasks';

/**
 * Parse the ## Potential Subtasks section from a task description.
 *
 * Returns empty arrays if the section is absent or the description is null/undefined.
 * Lines not matching either format are ignored.
 */
export function parseSubtasks(description: string | null | undefined): {
  unchecked: UncheckedSubtask[];
  activated: ActivatedSubtask[];
} {
  if (!description) {
    return { unchecked: [], activated: [] };
  }

  const lines = description.split('\n');
  const headingIdx = lines.findIndex(
    (line) => line.trim() === POTENTIAL_SUBTASKS_HEADING,
  );

  if (headingIdx === -1) {
    return { unchecked: [], activated: [] };
  }

  const unchecked: UncheckedSubtask[] = [];
  const activated: ActivatedSubtask[] = [];

  for (let i = headingIdx + 1; i < lines.length; i++) {
    const line = lines[i];

    // Stop at next heading
    if (line.startsWith('## ') || line.startsWith('# ')) {
      break;
    }

    // Activated: - [x] <title> → task: <uuid>
    const activatedMatch = line.match(/^- \[x\] (.+?) → task: (.+)$/);
    if (activatedMatch) {
      activated.push({ lineText: activatedMatch[1].trim(), taskId: activatedMatch[2].trim() });
      continue;
    }

    // Unchecked: - [ ] <title>
    const uncheckedMatch = line.match(/^- \[ \] (.+)$/);
    if (uncheckedMatch) {
      unchecked.push({ lineText: uncheckedMatch[1].trim() });
    }
  }

  return { unchecked, activated };
}

/**
 * Replace the first matching unchecked line '- [ ] <lineText>' with the
 * activated form '- [x] <lineText> → task: <taskId>'.
 *
 * Returns the description unchanged if the line is not found.
 */
export function activateSubtaskLine(
  description: string,
  lineText: string,
  taskId: string,
): string {
  const target = `- [ ] ${lineText}`;
  const replacement = `- [x] ${lineText} → task: ${taskId}`;

  const idx = description.indexOf(target);
  if (idx === -1) {
    return description;
  }

  return description.slice(0, idx) + replacement + description.slice(idx + target.length);
}
