

// ── Types ─────────────────────────────────────────────────────────────────────

export type SectionState = 'grey' | 'yellow' | 'green' | 'blue';
export type EssayState = 'grey' | 'yellow' | 'green' | 'blue' | 'violet';
export type RecallStatus = 'not_established' | 'current' | 'due';
export type SectionNextStep = 'guided_oral' | 'recall_due' | 'guided_next' | 'unguided_recall';
export type EssayNextStep = 'guided_essay_oral' | 'cards_learned' | 'section_unguided_orals' | 'unguided_essay_oral';

// GET /progress/sections row (Sprint14).
export interface SectionProgressRow {
  section_id: string;
  essay_id: string;
  heading: string;
  anchor_slug: string;
  order_index: number;
  state: SectionState;
  next_step: SectionNextStep | null;
  guided_passed: boolean;
  unguided_passed: boolean;
  guided_pass_source: 'exam' | 'grandfathered' | 'guided_level' | null;
  // Guided progression (Levels 1-6): highest learner-confirmed level; >= 5 suggests the unguided oral.
  guided_level: number;
  unguided_suggested: boolean;
  // Sprint16: next guided level to conduct (null at Level 6) and the independent recall dimension.
  next_guided_level: number | null;
  recall_status: RecallStatus;
  recall_next_due_at: string | null;
  recall_last_reviewed_at: string | null;
  recall_last_rating: 'again' | 'hard' | 'good' | 'easy' | null;
  guided_latest_score: number | null;
  unguided_latest_score: number | null;
  guided_passed_at: string | null;
  unguided_passed_at: string | null;
  cards_total: number;
  cards_established: number;
  is_locked: boolean;
}

export interface EssayRow {
  id: string;
  title: string;
  slug: string;
  category: string | null;
  sort_index: number;
  status: 'planned' | 'complete';
  progress_total: number;
  progress_established: number;
  open_count: number;
  // Sprint14 — derived essay traffic light (see CLAUDE.md "Section progression").
  essay_state: EssayState;
  essay_next_step: EssayNextStep | null;
  essay_guided_passed: boolean;
  essay_unguided_passed: boolean;
  essay_guided_latest_score: number | null;
  essay_unguided_latest_score: number | null;
  essay_guided_passed_at: string | null;
  essay_unguided_passed_at: string | null;
  cards_learned_count: number;
  sections_total: number;
  sections_unguided_passed_count: number;
  revalidation_pending_count: number;
  // Sprint16: essay-scope recall status and the number of due recall items (sections + essay).
  essay_recall_status: RecallStatus;
  essay_recall_next_due_at: string | null;
  recall_due_count: number;
}

// {nugget_key, title} — the light pair shape every nugget-reference field
// carries (never the full body_markdown, to keep list/overview responses
// lightweight). See CLAUDE.md "Nuggets" (Sprint09_Nuggets).
export interface NuggetRef {
  nugget_key: string;
  title: string;
}

export interface SectionRow {
  id: string;
  heading: string;
  anchor_slug: string;
  order_index: number;
  body_markdown: string;
  nuggets: NuggetRef[];
}

export interface EssayDetailRow extends EssayRow {
  main_spine_markdown: string;
  main_spine_nuggets: NuggetRef[];
  sections: SectionRow[];
}

export interface DueCardRow {
  id: string;
  flashcard_id: string;
  question: string;
  answer: string;
  essay_id: string;
  section_id: string;
  anchor_slug: string;
  next_due_at: string;
  is_new: boolean;
  is_recent: boolean;
  scheduled_interval_seconds: number;
  nugget_id: string | null;
  category: string | null;
  essay_title: string;
}

// GET /flashcards/{id}/grade-preview row.
export interface GradePreviewRow {
  grade: Grade;
  interval_seconds: number;
}

// Sprint12_FSRSAndUXOverhaul — GET /review-stats/activity and
// GET /review-stats/intervals row shapes.
export interface ActivityRow {
  date: string;
  reviews: number;
}

export interface IntervalBucketRow {
  bucket: string;
  label: string;
  count: number;
}

export interface ReviewStatsSummaryRow {
  period: 'day' | 'week' | 'month';
  reviews: number;
  unique_cards: number;
  again_count: number;
  hard_count: number;
  good_count: number;
  easy_count: number;
  failures: number;
  recall_rate: number | null;
  new_count: number;
  orals_count: number;
  guided_orals_count: number;
  unguided_orals_count: number;
}

export interface ActivityDayRow {
  date: string;
  recalls: number;
  unique_cards_seen: number;
  first_cards_seen: number;
  recall_rate: number | null;
}

export interface ReviewResult {
  flashcard_id: string;
  last_reviewed_at: string | null;
  next_due_at: string;
  // Sprint14: null for a normal review.
  revalidation_outcome: 'preserved' | 'failed' | null;
}

export interface QueueStatRow {
  bucket: string;
  label: string;
  count: number;
}

export interface LastExamination {
  examined_at: string;
  score: number;
  feedback: string | null;
}

export interface ExaminationPackageSection {
  section_id: string;
  anchor_slug: string;
  heading: string;
  body_markdown: string;
  section_version: string;
  flashcards: { id: string; q: string; a: string }[];
  last_examination: LastExamination | null;
  nuggets?: { nugget_key: string; title: string; body_markdown: string }[];
}

export interface ExaminationPackage {
  essay_id: string;
  essay_slug: string;
  essay_title: string;
  // Sprint12_FSRSAndUXOverhaul — echoes the exam_type the package was
  // requested with.
  exam_type: 'guided' | 'unguided';
  // Sprint14: section-scope or whole-essay package, plus the backend-owned pass rule.
  scope: 'section' | 'essay';
  // Guided packages carry `scoring`; unguided (recall) packages carry `recall_grading` instead.
  scoring?: { score_max: number; pass_threshold_percent: number; min_passing_score: number };
  recall_grading?: {
    ratings: Record<'again' | 'hard' | 'good' | 'easy', string>;
    critical_rule: string;
    max_followups: number;
  };
  last_essay_examination?: LastExamination | null;
  sections: ExaminationPackageSection[];
}

// GET /sections/{id}/guided-package (guided progression, Levels 1-6).
export interface GuidedPackage {
  kind: 'guided_session';
  essay_slug: string;
  level: number;
  max_level: number;
  level_spec: { level: number; name: string; expectation: string; ai_behavior: string; advance_when: string };
  guided_progress: { completed_level: number };
  section: { section_id: string; anchor_slug: string; heading: string };
}

// GET /sections/{id}/guided-sessions row.
export interface GuidedSessionRow {
  id: string;
  session_at: string;
  level: number;
  recommendation: 'advance' | 'continue';
  learner_decision: 'advance' | 'stay';
  advanced_to: number | null;
  rationale: string;
  demonstrated: string;
  gaps_text: string;
}

export interface SectionExaminationRow {
  id: string;
  examined_at: string;
  score: number;
  // Sprint12_FSRSAndUXOverhaul
  exam_type: 'guided' | 'unguided';
  passed: boolean;
  question: string;
  answer_transcript: string;
  feedback: string | null;
  section_version_at: string;
}

// GET /essays/{id}/examinations row (Sprint14).
export interface EssayExaminationRow {
  id: string;
  examined_at: string;
  exam_type: 'guided' | 'unguided';
  score: number;
  passed: boolean;
  question: string;
  answer_transcript: string;
  feedback: string | null;
}

// ── Flashcard exploration (Sprint06) ────────────────────────────────────────

export interface ExplorationPackage {
  export_version: number;
  card: {
    card_id: string;
    card_key: string;
    essay_slug: string;
    essay_title: string;
    section_id: string;
    section_anchor_slug: string;
    section_heading: string;
    question: string;
    answer: string;
  };
  // Sprint09_Nuggets: a discriminated union — a nugget-linked card's context
  // is {nugget_body_markdown, nugget_key, nugget_title} INSTEAD OF
  // {section_body_markdown} (a replacement, not an addition). A legacy card
  // (no nugget) keeps the unchanged section-body shape.
  context:
    | { section_body_markdown: string }
    | { nugget_body_markdown: string; nugget_key: string | null; nugget_title: string | null };
}

export interface ExplorePreview {
  save_discussion: {
    card_id: string;
    card_key: string;
    exploration_question: string;
    discussion_summary: string;
    resolution: string;
    knowledge_gap: string | null;
    snapshot: { question_at_time: string; answer_at_time: string; section_id_at_time: string };
  };
  update_card: {
    card_id: string;
    card_key: string;
    changed_fields: string[];
    old: { question: string; answer: string };
    new: { question: string; answer: string };
    reason: string;
  }[];
  create_card: {
    section_id: string;
    section_anchor_slug: string;
    essay_id: string;
    question: string;
    answer: string;
    card_key: string;
  }[];
}

export interface ExploreImportResult {
  dry_run: boolean;
  applied: boolean;
  discussion_id?: string;
  revisions?: { id: string; card_id: string; card_key: string; changed_fields: string[] }[];
  created_cards?: { id: string; card_key: string; section_id: string; section_anchor_slug: string }[];
  preview: ExplorePreview;
}

// ── Single-section export/import ────────────────────────────────────────────
//
// Same shape as the POST /essays/ingest payload (see IngestView / STUB_PROMPT
// below) — pre-filled from the essay's CURRENT sections, ALL of them, in
// order. POST /essays/ingest assigns each section's order_index from its
// array position, not from any value in the payload, so a partial payload
// would silently reorder the essay on reimport; carrying every section keeps
// an unedited reply's order_index identical to what is already stored. See
// backend/routers/essays.py::export_section.
//
// "Export section" (revise the focus section's own content) and "Insert
// section" (splice a blank-template new section right after the focus one,
// client-side, before copying) both use this same package — only the prompt
// and whether a placeholder is spliced in differ. Both reimport through the
// existing "Add / Update Essay" (IngestView -> POST /essays/ingest); there is
// no separate import endpoint for either.

export interface SectionExportPackage {
  export_version: number;
  focus_section_id: string;
  title: string;
  slug: string;
  category: string | null;
  sort_index: number;
  status: string;
  // Sprint09_Nuggets additions: the essay's main spine narrative — a
  // top-level field on POST /essays/ingest, same optional-key/round-trip
  // convention as category/sort_index/status, so an unedited reimport of
  // this package preserves it and an edited one updates it — plus its
  // resolved nuggets (read-only, server-computed) and the focus section's
  // FULL {nugget_key, title, body_markdown} nugget context (richer than the
  // light `nuggets` pairs every section also carries).
  main_spine_markdown: string;
  main_spine_nuggets: NuggetRef[];
  focus_section_nuggets: { nugget_key: string; title: string; body_markdown: string }[];
  // Only present when exported with ?include_examinations=true ("Improve section").
  focus_section_examinations?: {
    examined_at: string;
    score: number;
    passed: boolean;
    question: string;
    answer_transcript: string;
    feedback: string | null;
  }[];
  // Present with focus_section_examinations: the oral pass rule, from backend/oral_state.py.
  focus_section_scoring?: { score_max: number; pass_threshold_percent: number; min_passing_score: number };
  sections: {
    section_id: string;
    heading: string;
    anchor_slug: string;
    body_markdown: string;
    cards: { id: string; q: string; a: string }[];
    nuggets: NuggetRef[];
  }[];
}

// ── Single-essay export (Sprint08_QuestionLevelsAndStructure) ──────────────
//
// Sibling of SectionExportPackage — same shape, minus focus_section_id: "any
// number of sections, revise whichever I direct" rather than one named
// section. Reimports through the existing POST /essays/ingest via IngestView.

export interface EssayExportPackage {
  export_version: number;
  title: string;
  slug: string;
  category: string | null;
  sort_index: number;
  status: string;
  main_spine_markdown: string;
  main_spine_nuggets: NuggetRef[];
  sections: {
    section_id: string;
    heading: string;
    anchor_slug: string;
    body_markdown: string;
    cards: { id: string; q: string; a: string }[];
    nuggets: NuggetRef[];
  }[];
}

// ── Question overview + single-question export/upsert ──────────────────────
//
// QuestionRow is one flat GET /essays/{id}/questions row — QuestionOverviewView
// groups these by section then by level client-side, the same pattern
// EssayListView already uses to group essays by category from a flat row list.

export interface QuestionRow {
  id: string;
  card_key: string;
  question: string;
  answer: string;
  level: number;
  section_id: string;
  section_anchor_slug: string;
  section_heading: string;
  section_order_index: number;
  // Sprint09_Nuggets: the row's own section's referenced nuggets (duplicated
  // per row within the same section — Datasets are flat by contract), and
  // the card's current nugget assignment (nullable).
  section_nuggets: NuggetRef[];
  nugget_id: string | null;
  // Sprint14: derived lock/maturity state.
  is_locked: boolean;
  card_state: 'locked' | 'new' | 'learning' | 'established' | 'learned';
  needs_revalidation: boolean;
}

// GET /flashcards/{id}/export — essay_slug/essay_title/section_* are
// READ-ONLY CONTEXT for an AI conversation; POST /flashcards/upsert has no
// field to write any of them back to (see buildQuestionUpsertBody below).
export interface QuestionExportPackage {
  export_version: number;
  essay_slug: string;
  essay_title: string;
  section_id: string;
  section_anchor_slug: string;
  section_heading: string;
  section_body_markdown: string;
  card: { id: string; level: number; q: string; a: string; nugget_id: string | null };
}

// ── Nuggets (Sprint09_Nuggets) ───────────────────────────────────────────────

export interface NuggetListRow {
  id: string;
  nugget_key: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface NuggetDetailRow extends NuggetListRow {
  body_markdown: string;
}

export interface NuggetFlashcardRow {
  id: string;
  card_key: string;
  question: string;
  answer: string;
  level: number;
  essay_id: string;
  section_id: string;
}

export interface NuggetSectionRow {
  section_id: string;
  anchor_slug: string;
  heading: string;
  order_index: number;
  essay_id: string;
  essay_title: string;
  essay_slug: string;
}

export interface NuggetAuthoringPackage {
  export_version: number;
  essay: { slug: string; title: string; main_spine_markdown: string };
  section: { id: string; anchor_slug: string; heading: string; body_markdown: string };
  nugget: { id: string; nugget_key: string; title: string; body_markdown: string } | null;
  connected_nuggets: NuggetRef[];
}

export interface NuggetUpsertResult {
  id: string;
  nugget_key: string;
  title: string;
  created: boolean;
}

export interface GenerateFlashcardsPackage {
  export_version: number;
  nugget: { nugget_key: string; title: string; body_markdown: string };
  existing_flashcards: { id: string; card_key: string; question: string; answer: string; level: number }[];
  context: { essay_slug: string; section_id: string };
}

export interface QuestionUpsertResult {
  flashcard_id: string;
  card_id: string;
  essay_id: string;
  section_id: string;
  level: number;
  created: boolean;
}

export interface Dataset<T> {
  meta: { object_type: string; total: number };
  rows: T[];
}

export type Grade = 'again' | 'hard' | 'good' | 'easy';

// GET /recall/due row (Sprint16): one due oral-recall item (section or whole essay).
export interface RecallDueRow {
  id: string;
  scope: 'section' | 'essay';
  essay_id: string;
  section_id: string | null;
  essay_title: string;
  category: string | null;
  section_heading: string | null;
  anchor_slug: string | null;
  last_reviewed_at: string | null;
  next_due_at: string;
  last_rating: 'again' | 'hard' | 'good' | 'easy' | null;
  review_count: number;
  lapse_count: number;
}

// GET /recall/reviews row.
export interface RecallReviewRow {
  id: string;
  reviewed_at: string;
  rating: 'again' | 'hard' | 'good' | 'easy';
  next_due_at: string;
  question: string;
  answer_transcript: string;
  feedback: string | null;
  evidence: string;
}
