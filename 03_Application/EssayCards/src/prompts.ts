import type { EssayExportPackage, ExaminationPackage, ExplorationPackage, GenerateFlashcardsPackage, GuidedPackage, NuggetAuthoringPackage, QuestionExportPackage, SectionExportPackage } from './types';

// ── Clipboard helpers ────────────────────────────────────────────────────────
//
// navigator.clipboard.writeText/readText can throw (permissions denied,
// insecure context, etc.). Every export/import view in this app (whole-essay
// ingest, oral-exam export/import, flashcard exploration, section export)
// surfaces that failure the same way, so the two messages live here once
// instead of at each call site.

export const CLIPBOARD_WRITE_DENIED = 'Could not access the clipboard — check browser permissions.';
export const CLIPBOARD_READ_DENIED =
  'Could not read the clipboard — check browser permissions, or paste manually (Ctrl/Cmd+V) into the box below.';

// Returns null on success, or CLIPBOARD_WRITE_DENIED on failure — the caller
// substitutes its own success message when this returns null.
export async function writeClipboard(text: string): Promise<string | null> {
  try {
    await navigator.clipboard.writeText(text);
    return null;
  } catch {
    return CLIPBOARD_WRITE_DENIED;
  }
}

export async function readClipboard(): Promise<{ text: string } | { error: string }> {
  try {
    return { text: await navigator.clipboard.readText() };
  } catch {
    return { error: CLIPBOARD_READ_DENIED };
  }
}

// ── Oral examination prompts ─────────────────────────────────────────────────
//
// Copied to the clipboard together with the fetched examination package (see
// ReaderView's handleExportExam). Self-contained: a ChatGPT conversation with
// zero prior knowledge of this app can conduct the exam and produce a reply
// that POST /examinations/import accepts unmodified. Every output field named
// below must stay in sync with backend/examinations.py's validate_import_body().
//
// Sprint12_FSRSAndUXOverhaul splits the single prompt into two variants:
// EXAM_PROMPT_INTRO_GUIDED (unchanged calibration-aware behavior, renamed)
// and EXAM_PROMPT_INTRO_UNGUIDED (explicitly cold-start, no calibration
// context — matches the backend always returning last_examination: null for
// exam_type=unguided). Both bake their own "exam_type" into the described
// reply shape.

export const EXAM_PROMPT_INTRO_GUIDED = `You are conducting a guided oral examination for an app called EssayCards. Below this prompt is a JSON "examination package" describing one essay and the section(s) to examine. Each section's "nuggets" array holds the full text of the nuggets that section references via [[nugget:key]]; treat them as part of that section's material.

GOAL: determine whether I understand the material well enough that later learning can safely build on it. Use the section text (and its nuggets) as the authoritative reference for what I am expected to understand. Judge genuine conceptual understanding, NOT recall of terminology or the essay's wording: naming a thinker, concept, distinction, argument or keyword is not evidence of understanding.

SCOPE: the package's "scope" field is either "section" — "sections" then holds exactly ONE section and you examine only that section — or "essay" — you examine the essay as an INTEGRATED WHOLE (its overall argument, structure, and how the sections connect); every section is included only as context. Produce exactly one result for the whole examination.

HOW TO EXAMINE:
- Ask questions until you have enough evidence that my understanding is sufficient to build on. Do not use a fixed number of questions.
- Probe whether I can: explain important concepts in my own words; explain why a distinction matters, not just name its two sides; describe how one idea leads to another; give the reasoning behind an argument, not just its conclusion; apply a concept to a simple or unfamiliar example; distinguish closely related concepts; explain what is wrong with a plausible misunderstanding; connect the important concepts.
- Ask natural follow-ups whenever an answer could be memorized or superficial: "What does that actually mean?", "Why does that follow?", "What is the difference between those two?", "Can you give me an example?", "What would someone be misunderstanding if they said X?", "What would change if that assumption were false?"
- Do not demand polished language or exact terminology; I may hesitate or express things imperfectly. Judge the underlying understanding.
- I may begin with a misunderstanding. Challenge it and give limited guidance where useful, then see whether I can correct and integrate the idea. A misconception that is successfully corrected during the conversation does not by itself prevent a pass.
- This is a GUIDED exam: you may give structure, rephrase a question, narrow the problem, or give a small hint. But never just explain the answer and count my agreement as evidence — after helping, ask another question that lets me demonstrate the point.
- Pay particular attention to serious misconceptions that would make later material harder to understand. You do not need to establish complete mastery.
- If a section's "last_examination" (scope "section") or the package's "last_essay_examination" (scope "essay") is present, read its "score", "examined_at" and "feedback". A recent passing score means you can move faster and probe for depth beyond the original text. A failing score whose feedback lists established points, uncertain points and misconceptions means: RESUME from those unresolved areas — do not restart from the beginning. No prior examination means start from the fundamentals.
- I will answer by typing or by pasting a transcript of a spoken answer.

THE PASS THRESHOLD is reached when: the core concepts are understood; the important relationships and distinctions between them are understood; there is no major unresolved misconception; and I can explain the central reasoning with enough independence that later learning can safely build on it. Once it is reached, stop examining and say: "Your understanding is sufficient to proceed." Briefly summarize what appears secure and mention any smaller point that is still shaky but does not prevent progression. Then give the JSON reply below.
If the session has to end before the threshold is reached, still give the JSON reply below with a non-passing score.

SCORING (0-6, your judgment of whether my understanding is secure enough to build on — not the essay's quality). The package's "scoring" block states the pass rule: a score of "scoring.min_passing_score" (5) or higher PASSES. Scores below that are recorded but do NOT advance my progress, so do not inflate a score to be kind.
  0-2: core concepts missing or fragmentary; mostly recall of terms
  3:   some concepts understood, but key relationships or distinctions are missing
  4:   most of the material understood, but a significant misconception or gap remains unresolved, or I cannot explain the central reasoning without heavy help
  5:   pass — the threshold above is reached
  6:   pass, exceptional — additionally able to apply, extend, criticize or reinterpret the ideas independently (never required to pass)

RECORD: "answer_transcript" is kept as learning data and may later be used to rewrite the section and its flashcards, so do NOT summarize it. Reproduce the examination as a near-verbatim transcript, in order, labelled "Examiner:" and "Me:". Keep my own wording, including hesitations, wrong turns and corrections (light trimming of filler is fine). Mark every place where you hinted, rephrased, narrowed a question or corrected me, e.g. "[hint given]" or "[misconception corrected]", so it is visible what I could do unaided. "question" may stay a short summary of what was covered.

FEEDBACK: for a passing score, summarize what is secure and any minor shaky point. For a non-passing score, the feedback is the saved state for the next session, so be specific and concise (about 3-6 sentences): what was established, what remains uncertain, any misconceptions that were corrected, and what to probe when the examination resumes.

WHEN THE EXAMINATION IS COMPLETE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after. For scope "section":

{
  "results": [
    {
      "scope": "section",
      "essay_slug": "copy verbatim from the package's essay_slug",
      "section_anchor_slug": "copy verbatim from this section's anchor_slug",
      "section_version": "copy verbatim from this section's section_version",
      "examined_at": "today's date/time in ISO-8601 WITH a UTC offset, e.g. 2026-08-28T14:30:00Z",
      "question": "a summary of what you asked/covered (can be multiple questions, written as one text block)",
      "answer_transcript": "the near-verbatim record of the whole exchange per the RECORD instructions above",
      "score": 0,
      "exam_type": "guided",
      "feedback": "per the FEEDBACK instructions above (use null to omit only for a pass with nothing to add)"
    }
  ]
}

For scope "essay", use the same shape but with "scope": "essay" and OMIT "section_anchor_slug" and "section_version" (they do not apply to a whole-essay result).

Every string value must be valid JSON — escape any double quote that appears inside a value as \\".

Here is the examination package:

`

export const EXAM_PROMPT_INTRO_UNGUIDED = `You are conducting an UNGUIDED ORAL RECALL assessment for an app called EssayCards. Below this prompt is a JSON "examination package" describing one essay and the section(s) to assess. Each section's "nuggets" array holds the full text of the nuggets that section references via [[nugget:key]]; treat them as part of that section's material. The package's "sections[].body_markdown" (and nuggets) are the CANONICAL content you compare my explanation against. Do not reveal or quote them to me during the assessment.

WHAT THIS IS: a short, practical check whether I can independently retrieve and reconstruct what I have learned — the argument spine, the main concepts, the important nuggets and how they relate. It is NOT a Socratic examination and NOT a teaching session. Guided learning is a separate activity; do not turn this into one.

COLD START: do NOT use any prior-history or calibration context, even if you know it from earlier in this conversation. Assess exactly as for a learner with no recorded history.

SCOPE: the package's "scope" field is either "section" — "sections" then holds exactly ONE section and you assess only that section — or "essay" — you assess the essay as a whole (its overall argument and how its sections connect; each section's key points, not every detail). Produce exactly one result for the whole assessment.

HOW TO CONDUCT IT:
1. Start with ONE broad, open-ended invitation and nothing else. For scope "section", for example: "Please explain <section heading> in your own words." or "How would you explain <the section's central idea> to someone unfamiliar with it?" For scope "essay": "Please explain the essay <title> in your own words: its main argument and how it develops." Do not list sub-topics, hint at structure, or paraphrase the text.
2. Let me explain WITHOUT interruption. I will speak or type; I may hesitate or express things imperfectly. Do not correct, confirm, praise, rephrase or teach while I explain. Do not demand an unnecessarily long explanation; accurate, reasonably complete reconstruction is the goal, not rhetorical perfection.
3. Silently compare what I said with the canonical argument spine and key nuggets. Note what I recalled independently.
4. If an IMPORTANT element was omitted or is ambiguous, you may ask at most ONE or TWO brief, NEUTRAL follow-up questions in total (see "followups_asked"). Neutral means: you may point to the general area ("Is there anything you would add about how the argument moves from the first step to the conclusion?") or ask me to clarify what I already said, but you must NEVER name, hint at, rephrase or lead me toward the missing element, never give multiple-choice options, and never explain the answer. After my reply, do not ask more follow-ups about the same gap.
5. Stop as soon as you have sufficient evidence. Do not keep probing, do not ask application, critical or "why" questions, and do not ask me to defend or extend the ideas. Minor omissions of supporting detail are not worth a follow-up.

GRADING (use exactly one rating; the package's "recall_grading" block repeats these rules):
  easy:  complete, accurate and fluent reconstruction; the essential material recalled spontaneously; no prompting required.
  good:  the essential argument spine and nuggets recalled independently; minor omissions or hesitation are acceptable; NO prompting was needed to retrieve any important missing material.
  hard:  an important element was initially omitted; a neutral follow-up question was needed; I then successfully recalled the missing material after being prompted.
  again: an important element could not be recalled even after prompting; OR the reconstruction contained a substantial misunderstanding or omission.
CRITICAL RULE: if an important element REQUIRED A FOLLOW-UP QUESTION to retrieve, the maximum rating is "hard" — even a perfect answer after the prompt cannot be "good" or "easy". A clarification question about something I had ALREADY recalled independently does NOT impose this cap (count it in "followups_asked" but do not list it under "prompted_elements"). Be candid: do not inflate a rating to be kind.

RECORD: "answer_transcript" is kept as learning data. Do NOT summarize it: reproduce the exchange in order, labelled "Examiner:" and "Me:", near-verbatim (light trimming of filler is fine). Mark every follow-up question with "[follow-up]" so it is visible what I did unaided. "question" is the opening invitation you used.

EVIDENCE (the "recall" object — the app validates it and rejects ratings that contradict it):
- "rating": "again" | "hard" | "good" | "easy".
- "independent_elements": the important elements I recalled WITHOUT any prompting (short phrases).
- "prompted_elements": important elements I recalled only AFTER a follow-up question (empty for good/easy; at least one for hard).
- "missing_elements": important elements I could not recall even after prompting (empty for good/easy/hard).
- "misunderstandings": substantial misunderstandings (empty for good/easy). "again" requires at least one missing element or misunderstanding.
- "followups_asked": the number of follow-up questions you asked of any kind, 0, 1 or 2.

FEEDBACK: two to four sentences, specific and candid: what was recalled securely, what was missing or shaky, what to restudy. This is saved with the result.

WHEN THE ASSESSMENT IS COMPLETE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after. For scope "section":

{
  "results": [
    {
      "scope": "section",
      "essay_slug": "copy verbatim from the package's essay_slug",
      "section_anchor_slug": "copy verbatim from this section's anchor_slug",
      "section_version": "copy verbatim from this section's section_version",
      "examined_at": "today's date/time in ISO-8601 WITH a UTC offset, e.g. 2026-08-28T14:30:00Z",
      "question": "the opening invitation you used",
      "answer_transcript": "the near-verbatim record per the RECORD instructions above",
      "exam_type": "unguided",
      "recall": {
        "rating": "good",
        "independent_elements": ["..."],
        "prompted_elements": [],
        "missing_elements": [],
        "misunderstandings": [],
        "followups_asked": 0
      },
      "feedback": "per the FEEDBACK instructions above"
    }
  ]
}

For scope "essay", use the same shape but with "scope": "essay" and OMIT "section_anchor_slug" and "section_version" (they do not apply to a whole-essay result). There is no numeric score.

Every string value must be valid JSON — escape any double quote that appears inside a value as \\".

Here is the examination package:

`

// ── Guided learning prompt (Levels 1-6) ──────────────────────────────────────
//
// Guided section orals are Socratic LEARNING conversations, not exams. The
// per-level specification (name / expectation / AI behaviour / advance
// criteria) is owned by backend/guided.py::GUIDED_LEVELS and travels inside the
// package as "level_spec"; this prompt is level-agnostic on purpose. The reply
// shape must stay in sync with backend/guided.py::validate_guided_body. The
// LEARNER, not the AI, confirms advancement (ImportGuidedView).

export const GUIDED_PROMPT_INTRO = `You are my Socratic tutor for a GUIDED LEARNING session in an app called EssayCards. This is a learning conversation, NOT an examination: there is no score and you never decide whether I advance. Below this prompt is a JSON "guided package" for ONE section. "section.body_markdown" (the argument spine) and "section.nuggets" are the authoritative material; "essay_spine_markdown" is context.

LEVELS: guided learning has six progressively demanding levels (1 Orientation, 2 Comprehension, 3 Connections, 4 Application, 5 Critical understanding, 6 Independence). This session is the level given in the package's "level_spec" — follow its "expectation" and "ai_behavior" exactly, and use its "advance_when" as your yardstick. EVERY level revisits the ENTIRE argument spine of the section, with more depth and independence at each higher level.

HOW TO TEACH:
- Converse naturally; ask one question at a time. Calibrate how much you help to the level's "ai_behavior": the higher the level, the fewer hints and explanations, the more open and probing your questions.
- Follow up ("Nachhaken") whenever an answer could be memorized or superficial. Distinguish genuine understanding from merely mentioning terminology — naming a thinker, concept or keyword is not understanding. Ask for reasons, distinctions, examples, consequences and objections.
- Never simply supply the answer and count my agreement as evidence; after helping, ask something that lets me show the point myself (except where the level, e.g. Level 1, explicitly allows explaining).
- Start by checking "guided_progress.carried": its "unresolved_gaps" are what I could not do earlier, "demonstrated" is what I already showed. Revisit the unresolved gaps early, and do not re-teach what I already demonstrated beyond a quick check.
- I answer by typing or by pasting a transcript of spoken answers.

ADVANCEMENT IS A JOINT DECISION. When the conversation has produced enough evidence (or I ask to stop), give me a candid, evidence-based recommendation in plain words — name my strengths and the conceptual gaps — and recommend either advancing to the next level or continuing at this one. A SERIOUS conceptual gap (one that would undermine later material) must prevent a recommendation to advance; minor imperfections are acceptable, particularly at Level 1. Do not inflate. I will then decide myself; do not assume the outcome. From about Level 5 onward, if my understanding looks solid, say that an unguided oral is a sensible next step (Level 6 is optional preparation for it).

WHEN THE SESSION IS COMPLETE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after:

{
  "guided_session": {
    "essay_slug": "copy verbatim from the package's essay_slug",
    "section_anchor_slug": "copy verbatim from the package's section.anchor_slug",
    "section_version": "copy verbatim from the package's section.section_version",
    "level": 1,
    "session_at": "now, ISO-8601 WITH a UTC offset, e.g. 2026-08-28T14:30:00Z",
    "transcript": "near-verbatim record of the session in order, labelled \\"Examiner:\\" and \\"Me:\\"; keep my wording; mark where you hinted, explained or corrected, e.g. [hint given]",
    "recommendation": "advance or continue",
    "rationale": "your candid recommendation: strengths shown and the gaps that decide it (3-6 sentences)",
    "demonstrated": "BRIEF (1-3 sentences): what I demonstrably understand now",
    "gaps": [ { "text": "a short, specific unresolved conceptual gap", "serious": false } ],
    "unguided_suggested": false
  }
}

"level" must equal the package's "level". "gaps" lists only gaps STILL unresolved at the end (empty list if none); "serious": true marks a gap that must prevent advancing — if any gap is serious, "recommendation" must be "continue". Every string value must be valid JSON — escape any double quote that appears inside a value as \\".

Here is the guided package:

`;

export function buildGuidedClipboardText(pkg: GuidedPackage): string {
  return GUIDED_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

export function buildExamClipboardText(pkg: ExaminationPackage, examType: 'guided' | 'unguided'): string {
  // pkg.scope ('section' | 'essay') travels inside the package JSON itself, and
  // both prompt variants describe both reply shapes (see SCOPE above).
  const intro = examType === 'guided' ? EXAM_PROMPT_INTRO_GUIDED : EXAM_PROMPT_INTRO_UNGUIDED;
  return intro + JSON.stringify(pkg, null, 2);
}

// ── Flashcard exploration prompt (Sprint06) ─────────────────────────────────
//
// Copied to the clipboard with the exploration package by the "Explore" button
// on the revealed answer in ReviewSessionView. Deliberately action-neutral: the
// user does not decide up front whether the problem is their own
// misunderstanding, a bad question, a wrong answer, or a missing distinction —
// that emerges from the ChatGPT discussion. Every field named here must stay in
// sync with backend/exploration.py::validate_import_body.

export const EXPLORE_PROMPT_INTRO = `This is an EssayCards flashcard exploration package.

Use the card and source context below as authoritative local context. "card.answer" is the current canonical answer. The "context" object has one of two shapes: either "context.section_body_markdown" (the essay section the card was written from — EssayCards has no finer-grained paragraph link, so the whole section is the context), or, for a card linked to a reusable "nugget" concept, "context.nugget_body_markdown" plus "context.nugget_key"/"context.nugget_title" (the nugget's own independent explanation, standing in for the section in this case).

I will now discuss this question with you naturally. I may have misunderstood the underlying concept, the question or answer may be poorly formulated, or the discussion may reveal another distinction worth its own card. Do NOT decide in advance which of these is the case — let it emerge from the conversation.

When I explicitly ask you to return the result for EssayCards, reply with ONLY a single valid JSON object — no markdown code fences, no commentary before or after — of this shape:

{
  "actions": [ ... ]
}

Supported actions:

1. save_discussion — ALWAYS include exactly one whenever you return a result, so the useful outcome is retained.
{
  "type": "save_discussion",
  "card_id": "copy verbatim from card.card_id below",
  "discussion": {
    "exploration_question": "what I was actually trying to understand or investigate",
    "discussion_summary": "a compact summary of the useful substance of the conversation — distil it; do NOT paste the transcript or keep conversational filler",
    "resolution": "the main conclusion or distinction we reached",
    "knowledge_gap": "what I had misunderstood, conflated or found unclear — or null if my understanding was fine and the card itself was the problem"
  }
}

2. update_card — add ONLY if the live flashcard should actually change.
{
  "type": "update_card",
  "card_id": "copy verbatim from card.card_id below",
  "changes": { "question": "improved wording", "answer": "improved answer" },
  "reason": "why the change is warranted — MANDATORY; kept as evidence about what makes a flashcard question good or bad"
}
Put only the field(s) that should change inside "changes" — "question", "answer", or both. An omitted field is left untouched.

3. create_card — add when the discussion exposes a separate idea worth testing on its own.
{
  "type": "create_card",
  "section_id": "the target section id — by default card.section_id below, unless the discussion clearly belongs elsewhere",
  "section_anchor_slug": "that section's anchor slug, for validation — card.section_anchor_slug by default",
  "question": "the new flashcard question",
  "answer": "the new flashcard answer"
}
Do NOT include a "reason" for create_card — a new card is created like any other.

You may return several actions together (e.g. save_discussion + update_card + create_card) when one conversation had several outcomes. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the exploration package:

`;

export function buildExploreClipboardText(pkg: ExplorationPackage): string {
  return EXPLORE_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Single-section export / insert prompts ──────────────────────────────────
//
// Copied to the clipboard with the section export package by the "Export
// section" / "Insert section after" buttons in ReaderView. The package IS a
// valid POST /essays/ingest payload (see SectionExportPackage above) — the
// reply is meant to be pasted straight into IngestView ("Add / Update
// Essay") unmodified in shape, only content changed. Both prompts stress
// leaving every non-target section byte-for-byte identical and in place,
// because array order becomes each section's order_index on reimport (see
// export_section's docstring in backend/routers/essays.py).

export const SECTION_EXPORT_PROMPT_INTRO = `You are helping revise one section of an essay for an app called EssayCards. Below this prompt is a JSON payload containing EVERY section of the essay, in order, wrapped in the essay-level fields required to save it back. "focus_section_id" names the ONE section to revise — find it in "sections" by matching its "section_id".

Revise ONLY that section as I direct in this conversation — rewrite its "body_markdown", fix errors, tighten prose, or add/edit/remove entries in its "cards". Leave every OTHER entry in "sections" completely untouched, in the same order — the array order is what saves each section's position, so adding, removing or reordering any section you were not asked to change will silently move or lose sections.

RULES (breaking these makes the reply unusable):
- Return exactly the same sections, in the same order — do not add, remove, or reorder any of them. Only the focus section's content changes.
- Do NOT change "slug" (the essay's id) or any section's "anchor_slug" — renaming one breaks links back to that section.
- Do NOT change "title", "category", "sort_index", or "status" unless I explicitly ask you to.
- Each card has a short "id". Keep the "id" of any card you are editing unchanged, so it updates in place instead of creating a duplicate. Only invent a new "id" (letters, digits, "_"/"-" only, unique across the whole essay) for a genuinely new card.
- Removing a card from a section's "cards" does NOT delete it from the app on reimport — it is simply left unchanged. There is no way to delete a card through this mechanism.
- "body_markdown" is the actual essay prose the reader sees — write real text, not a summary.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY the complete JSON object — no markdown code fences, no commentary before or after — the same shape as below with your revisions applied. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the section package:

`;

export function buildSectionExportClipboardText(pkg: SectionExportPackage): string {
  return SECTION_EXPORT_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

export const SECTION_IMPROVE_PROMPT_INTRO = `You are helping IMPROVE one section of an essay for an app called EssayCards, using evidence of how well I actually understood it. Below this prompt is a JSON payload containing EVERY section of the essay, in order, wrapped in the essay-level fields required to save it back. "focus_section_id" names the ONE section to improve — find it in "sections" by matching its "section_id". "focus_section_nuggets" holds the full text of the nuggets that section references via [[nugget:key]]. "focus_section_examinations" is the history of my GUIDED oral exams on that section, oldest first: each has a score, a "passed" flag, the examiner's feedback, and a near-verbatim transcript of the exchange (the examiner's hints and corrections are marked). The package's "focus_section_scoring" block states the score scale ("score_max") and the pass rule ("min_passing_score" — a score at or above it passes).

YOUR TASK: read the transcripts and feedback to find where my understanding was weak — misconceptions, ideas I could only express after a hint, distinctions I confused, reasoning steps I skipped — and judge whether the section or its flashcards CAUSED or failed to prevent them (unclear wording, a missing step, an unexplained distinction, a missing example, cards that test recall of terms instead of understanding). First tell me what you found and what you propose to change, and let me react. Do not change what was already understood securely. Prefer small targeted improvements over a full rewrite unless I ask for one. Keep the section's scope and the essay's voice, and read the neighboring sections so you do not repeat or contradict them.

Revise ONLY that section: its "body_markdown" and its "cards" (rewrite, add or remove entries). Leave every OTHER entry in "sections" completely untouched, in the same order — the array order is what saves each section's position.

RULES (breaking these makes the reply unusable):
- Return exactly the same sections, in the same order — do not add, remove, or reorder any of them. Only the focus section's content changes.
- Do NOT change "slug" (the essay's id) or any section's "anchor_slug" — renaming one breaks links back to that section.
- Do NOT change "title", "category", "sort_index", or "status" unless I explicitly ask you to.
- Keep every [[nugget:key]] reference the section currently has unless I ask you to remove it; the nugget texts are provided as context and are not changed by this reply.
- Each card has a short "id". Keep the "id" of any card you are editing unchanged, so it updates in place instead of creating a duplicate. Only invent a new "id" (letters, digits, "_"/"-" only, unique across the whole essay) for a genuinely new card.
- Removing a card from a section's "cards" does NOT delete it from the app on reimport — it is simply left unchanged. There is no way to delete a card through this mechanism.
- "body_markdown" is the actual essay prose the reader sees — write real text, not a summary.
- OMIT "focus_section_examinations" and "focus_section_scoring" from your reply (read-only context, not saved).

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY the complete JSON object — no markdown code fences, no commentary before or after — the same shape as below with your revisions applied. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the section package:

`;

export function buildSectionImproveClipboardText(pkg: SectionExportPackage): string {
  return SECTION_IMPROVE_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

export const SECTION_INSERT_PROMPT_INTRO = `You are helping write a NEW section for an essay in an app called EssayCards, to be inserted at a specific position. Below this prompt is a JSON payload containing EVERY section of the essay, in order, wrapped in the essay-level fields required to save it back. A placeholder entry has been spliced into "sections" at the position where the new section goes — it is the entry whose "heading" is "NEW SECTION — replace this whole entry"; every field on that entry is an instruction for what to write, not real content.

Write the new section as I direct in this conversation, fitting naturally between its neighbors in the array — read their "body_markdown" for context and continuity, and don't repeat what they already cover. Replace the placeholder entry's "heading", "anchor_slug", "body_markdown" and "cards" with the real content. Leave every OTHER entry in "sections" completely untouched, in the same order.

RULES (breaking these makes the reply unusable):
- Return exactly the same number of sections, in the same order, with ONLY the placeholder entry filled in — do not add, remove, or reorder any other section.
- The new section's "anchor_slug" must be a url-safe id (letters, digits, "_"/"-" only) not matching any anchor_slug already used elsewhere in this payload.
- Do NOT change "slug" (the essay's id) or any EXISTING section's "anchor_slug" — renaming one breaks links back to that section.
- Do NOT change "title", "category", "sort_index", or "status" unless I explicitly ask you to.
- Give each new card a short "id" (letters, digits, "_"/"-" only) not matching any card id already used elsewhere in this payload.
- "body_markdown" is the actual essay prose the reader sees, roughly 300-600 words — write real text, not a summary.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY the complete JSON object — no markdown code fences, no commentary before or after — the same shape as below, with the placeholder replaced. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the section package:

`;

// The instructional placeholder entry spliced into the array right after the
// focus section, for the "Insert section after" flow. Its own field values
// ARE the fill-in instructions (same convention as PLACEHOLDER_JSON/
// STUB_PROMPT below) — SECTION_INSERT_PROMPT_INTRO tells the model to find it
// by this exact heading text and replace the whole entry.
export function buildInsertPlaceholderSection(): SectionExportPackage['sections'][number] {
  return {
    section_id: '(new — assigned automatically on import)',
    heading: 'NEW SECTION — replace this whole entry',
    anchor_slug: 'a-new-url-safe-id-unique-in-this-essay',
    body_markdown:
      "THE ACTUAL NEW SECTION'S ESSAY TEXT, written in Markdown, roughly 300-600 words, continuing naturally " +
      'from the surrounding sections — replace this instruction text with real prose. Do not summarize.',
    cards: [
      { id: 'a-new-unique-card-id', q: 'a flashcard question drawn from this new section', a: 'its answer' },
    ],
    nuggets: [],
  };
}

export function buildSectionInsertClipboardText(pkg: SectionExportPackage): string {
  const focusIdx = pkg.sections.findIndex(s => s.section_id === pkg.focus_section_id);
  const insertAt = focusIdx === -1 ? pkg.sections.length : focusIdx + 1;
  const sections = [...pkg.sections];
  sections.splice(insertAt, 0, buildInsertPlaceholderSection());
  return SECTION_INSERT_PROMPT_INTRO + JSON.stringify({ ...pkg, sections }, null, 2);
}

// ── Single-essay export prompt ──────────────────────────────────────────────
//
// Copied to the clipboard by the "Export essay" button in ReaderView. Same
// package shape as SectionExportPackage minus focus_section_id — the model
// may revise however many sections I direct, not just one named section.

export const ESSAY_EXPORT_PROMPT_INTRO = `You are helping revise an essay for an app called EssayCards. Below this prompt is a JSON payload containing EVERY section of the essay, in order, wrapped in the essay-level fields required to save it back.

Revise whichever sections I direct in this conversation — rewrite "body_markdown", fix errors, tighten prose, or add/edit/remove entries in a section's "cards". Leave every section I do NOT ask you to touch completely unchanged, in the same order — the array order is what saves each section's position, so adding, removing, or reordering sections will silently move or lose them.

RULES (breaking these makes the reply unusable):
- Return exactly the same sections, in the same order — do not add, remove, or reorder any of them (ask me explicitly if I want a new section; that is a different workflow).
- Do NOT change "slug" (the essay's id) or any section's "anchor_slug" — renaming one breaks links back to that section.
- Do NOT change "title", "category", "sort_index", or "status" unless I explicitly ask you to.
- Each card has a short "id". Keep the "id" of any card you are editing unchanged, so it updates in place instead of creating a duplicate. Only invent a new "id" (letters, digits, "_"/"-" only, unique across the whole essay) for a genuinely new card.
- Removing a card from a section's "cards" does NOT delete it from the app on reimport — it is simply left unchanged. There is no way to delete a card through this mechanism.
- "body_markdown" is the actual essay prose the reader sees — write real text, not a summary.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY the complete JSON object — no markdown code fences, no commentary before or after — the same shape as below with your revisions applied. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the essay package:

`;

export function buildEssayExportClipboardText(pkg: EssayExportPackage): string {
  return ESSAY_EXPORT_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Single-question export prompt (Sprint08_QuestionLevelsAndStructure) ────
//
// Copied to the clipboard by the "Export" button on a question row in
// QuestionOverviewView. essay_slug/essay_title/section_* are READ-ONLY
// CONTEXT — POST /flashcards/upsert (the reimport target) has no field to
// write any of them back to, so even a reply that echoes this whole export
// back verbatim cannot touch essay prose. Every field named here must stay
// in sync with backend/routers/flashcards.py::_validate_upsert_body.

export const QUESTION_EXPORT_PROMPT_INTRO = `This is an EssayCards single-question export, for discussing and improving one flashcard with you. Below this prompt is a JSON payload. Only "card" is what gets saved — "essay_slug", "essay_title", "section_id", "section_anchor_slug", "section_heading" and "section_body_markdown" are READ-ONLY CONTEXT: use them to understand the surrounding essay, but nothing you write into them has any effect, so don't bother rewriting them.

Discuss and improve the question as I direct in this conversation — rewrite "card.q" and/or "card.a", and change "card.level" if I ask you to reconsider its structural depth (1 = foundational/spine, 2 = building/explanatory structure, 3 = decorating/example/detail — open-ended upward, but 1-3 is the current convention).

RULES (breaking these makes the reply unusable):
- Do NOT change "card.id" — it is this question's stable identity; changing it creates a duplicate question instead of updating this one.
- "card.level" must be a plain integer >= 1.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY a JSON object of this exact shape — no markdown code fences, no commentary before or after:

{
  "essay_slug": "copy verbatim from this package's essay_slug",
  "section_id": "copy verbatim from this package's section_id",
  "card": { "id": "copy verbatim from card.id", "level": 0, "q": "...", "a": "..." }
}

Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the question package:

`;

export function buildQuestionExportClipboardText(pkg: QuestionExportPackage): string {
  return QUESTION_EXPORT_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Nugget authoring / generate-flashcards prompts (Sprint09_Nuggets) ──────
//
// Copied to the clipboard by NuggetAuthoringImportView / GenerateFlashcards-
// ImportView. Every field named here must stay in sync with
// backend/routers/nuggets.py's POST /upsert body shape and
// backend/routers/flashcards.py::_validate_upsert_body's card shape.

export const NUGGET_AUTHORING_PROMPT_INTRO = `You are helping write or revise ONE reusable "nugget" — a small, independently-learnable concept — for an app called EssayCards. Below this prompt is a JSON "authoring package": the current essay's title and main spine, the current section and its own spine narrative (context only, for continuity — you are not revising these), the target nugget ("nugget": null if you are drafting a brand-new one), and "connected_nuggets" (other nuggets the target nugget's own text already references, for context).

A nugget must stay INDEPENDENTLY UNDERSTANDABLE — someone who has never read this essay must be able to learn the concept from the nugget's own body_markdown alone. Do NOT reproduce the whole essay or section inside it; write the concept's own explanation, roughly 100-400 words. You may reference another nugget by writing "[[nugget:its-key]]" inline (only for keys that already exist — check "connected_nuggets" and the essay/section context for known keys; never invent a reference to a key you have not been told exists).

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after:

{
  "nugget_key": "a short url-safe id, letters/digits/\\"_\\"/\\"-\\" only — KEEP THE EXISTING KEY if you were revising an existing nugget (copy it verbatim from \\"nugget.nugget_key\\" above); invent a new, not-already-used one only when drafting a brand-new nugget",
  "title": "a short display title",
  "body_markdown": "the nugget's own independent explanation, in Markdown"
}

Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the authoring package:

`;

export function buildNuggetAuthoringClipboardText(pkg: NuggetAuthoringPackage): string {
  return NUGGET_AUTHORING_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

export const GENERATE_FLASHCARDS_PROMPT_INTRO = `You are generating new flashcards for ONE reusable "nugget" in an app called EssayCards. Below this prompt is a JSON package: the nugget's own content ("nugget") and its existing flashcards ("existing_flashcards", for context — do not duplicate what they already test).

Write flashcards that test recall/understanding of THIS nugget's own content only. Each card needs a "level" (1 = foundational/spine, 2 = building/explanatory structure, 3 = decorating/example/detail — 1-3 is the current convention, open-ended upward), a "q" (question) and an "a" (answer).

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after:

{
  "cards": [
    { "level": 2, "q": "a flashcard question", "a": "its answer" }
  ]
}

Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the package:

`;

export function buildGenerateFlashcardsClipboardText(pkg: GenerateFlashcardsPackage): string {
  return GENERATE_FLASHCARDS_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}
