"""
Unit tests for the markdownSubtasks parsing/update contract.

These tests mirror the TypeScript markdownSubtasks.ts logic in Python
to verify the parse and update behavior independently.

Scenarios from 10_test_spec.md:
- Markdown Parsing — Section Absent
- Markdown Parsing — Unchecked Lines
- Markdown Parsing — Mixed Checked And Unchecked
- Markdown Parsing — Empty Section
- Markdown Update — Activate A Line
- Markdown Update — Line Not Found Is No-Op
"""

import re


# ── Python equivalent of markdownSubtasks.ts ──────────────────────────────────

POTENTIAL_SUBTASKS_HEADING = "## Potential Subtasks"


def parse_subtasks(description):
    """Parse ## Potential Subtasks section. Returns (unchecked, activated)."""
    if not description:
        return [], []

    lines = description.split("\n")
    try:
        heading_idx = next(
            i for i, line in enumerate(lines)
            if line.strip() == POTENTIAL_SUBTASKS_HEADING
        )
    except StopIteration:
        return [], []

    unchecked = []
    activated = []

    for line in lines[heading_idx + 1:]:
        if line.startswith("## ") or line.startswith("# "):
            break

        # Activated: - [x] <title> → task: <uuid>
        m = re.match(r"^- \[x\] (.+?) → task: (.+)$", line)
        if m:
            activated.append({"lineText": m.group(1).strip(), "taskId": m.group(2).strip()})
            continue

        # Unchecked: - [ ] <title>
        m = re.match(r"^- \[ \] (.+)$", line)
        if m:
            unchecked.append({"lineText": m.group(1).strip()})

    return unchecked, activated


def activate_subtask_line(description, line_text, task_id):
    """Replace first matching '- [ ] <lineText>' with activated form."""
    target = f"- [ ] {line_text}"
    replacement = f"- [x] {line_text} → task: {task_id}"
    idx = description.find(target)
    if idx == -1:
        return description
    return description[:idx] + replacement + description[idx + len(target):]


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_markdown_parsing_section_absent():
    """Markdown Parsing — Section Absent"""
    description = "A training unit with no subtasks section"
    unchecked, activated = parse_subtasks(description)
    assert unchecked == []
    assert activated == []


def test_markdown_parsing_unchecked_lines():
    """Markdown Parsing — Unchecked Lines"""
    description = "## Potential Subtasks\n- [ ] Session 1\n- [ ] Session 2"
    unchecked, activated = parse_subtasks(description)
    assert len(unchecked) == 2
    assert unchecked[0]["lineText"] == "Session 1"
    assert unchecked[1]["lineText"] == "Session 2"
    assert activated == []


def test_markdown_parsing_mixed_checked_and_unchecked():
    """Markdown Parsing — Mixed Checked And Unchecked"""
    description = "## Potential Subtasks\n- [x] Session 1 → task: abc-123\n- [ ] Session 2"
    unchecked, activated = parse_subtasks(description)
    assert len(unchecked) == 1
    assert unchecked[0]["lineText"] == "Session 2"
    assert len(activated) == 1
    assert activated[0]["lineText"] == "Session 1"
    assert activated[0]["taskId"] == "abc-123"


def test_markdown_parsing_empty_section():
    """Markdown Parsing — Empty Section"""
    description = "## Potential Subtasks\n\nNo lines below"
    unchecked, activated = parse_subtasks(description)
    assert unchecked == []
    assert activated == []


def test_markdown_parsing_null_description():
    """parse_subtasks with null/None description returns empty arrays."""
    unchecked, activated = parse_subtasks(None)
    assert unchecked == []
    assert activated == []


def test_markdown_update_activate_a_line():
    """Markdown Update — Activate A Line"""
    description = "Intro\n\n## Potential Subtasks\n- [ ] Session 1\n- [ ] Session 2"
    result = activate_subtask_line(description, "Session 1", "new-uuid-123")
    assert "- [x] Session 1 → task: new-uuid-123" in result
    assert "- [ ] Session 2" in result
    assert "- [ ] Session 1" not in result


def test_markdown_update_line_not_found_is_noop():
    """Markdown Update — Line Not Found Is No-Op"""
    description = "## Potential Subtasks\n- [ ] Session 1"
    result = activate_subtask_line(description, "Session 99", "some-uuid")
    assert result == description
