"""
Flashcard exploration round trip — validation and DB core shared by
backend/routers/exploration.py.

Mirrors the shape already established by backend/examinations.py for the oral-
examination round trip, but for a single flashcard:

  build_exploration_package(cur, flashcard_id)
      Reads one flashcard plus just enough local context (its essay, its
      section, and the section body it was written from) into a small self-
      contained dict for pasting into ChatGPT. No DB writes. The complete essay
      is deliberately NOT included. EssayCards has no paragraph-level linkage
      between a card and its source text — the containing section
      (section_body_markdown) is the finest-grained context available.

  validate_import_body(body) -> (actions, error_response)
      Full structural validation of the JSON ChatGPT returns, before any
      database access. Accepts either {"actions": [...]} or a single bare
      action object. Returns the normalised action list or an ApiError.

  resolve_and_plan(cur, actions) -> (plan, error_response)
      Resolves every card_id / section_id the actions reference (rejecting the
      whole import if any does not exist or an anchor does not match), reads the
      pre-edit snapshots, and builds a plan describing exactly what an apply
      would do. Issues only SELECTs.

  execute_plan(cur, plan) -> result
      Writes the plan in the §12 order: insert the discussion, then per
      update_card insert a flashcard_revisions row and UPDATE the live card,
      then insert each new card (+ its flashcard_review_state row, matching the
      ingest convention). Caller owns the transaction (commit / rollback).

The JSON is transport only. Nothing here stores the returned blob verbatim —
it is decomposed into essaycards.flashcard_discussions / .flashcard_revisions /
.flashcards rows.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from platform_errorhandling import api_error

# update_card.changes may only carry these keys — never let an arbitrary column
# be written from the returned JSON.
_ALLOWED_CARD_CHANGES = ("question", "answer")

_ERR_PREFIX = "EssayCards could not import this exploration result. "
_ERR_SUFFIX = (
    " Nothing was saved. Fix the JSON and send the complete EssayCards return "
    "package again."
)


def _import_error(what: str, code: str = "VALIDATION_ERROR", status: int = 400) -> Any:
    """
    An ApiError whose message is a complete, copy-pasteable description of what
    was wrong — the user pastes it straight back to ChatGPT to get a corrected
    package.
    """
    return api_error(code, _ERR_PREFIX + what + _ERR_SUFFIX, status=status)


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


# ── Export ────────────────────────────────────────────────────────────────────

def build_exploration_package(cur: Any, flashcard_id: str) -> dict[str, Any] | None:
    """Returns the export package dict, or None if flashcard_id is not a valid
    id or does not exist. Read-only."""
    if not _is_uuid(flashcard_id):
        return None

    cur.execute(
        """
        select f.id, f.card_key, f.question, f.answer,
               f.section_id,
               s.anchor_slug   as section_anchor_slug,
               s.heading       as section_heading,
               s.body_markdown as section_body_markdown,
               f.essay_id, e.slug as essay_slug, e.title as essay_title
        from essaycards.flashcards f
        join essaycards.essay_sections s on s.id = f.section_id
        join essaycards.essays e        on e.id = f.essay_id
        where f.id = %s
        """,
        (flashcard_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    return {
        "export_version": 1,
        "card": {
            "card_id": str(row["id"]),
            "card_key": row["card_key"],
            "essay_slug": row["essay_slug"],
            "essay_title": row["essay_title"],
            "section_id": str(row["section_id"]),
            "section_anchor_slug": row["section_anchor_slug"],
            "section_heading": row["section_heading"],
            "question": row["question"],
            "answer": row["answer"],
        },
        "context": {
            # EssayCards has no card->paragraph link; the whole containing
            # section is the finest context that exists.
            "section_body_markdown": row["section_body_markdown"],
        },
    }


# ── Import validation (no DB) ────────────────────────────────────────────────

def validate_import_body(body: Any) -> tuple[list[dict[str, Any]] | None, Any]:
    """
    Returns (actions, None) on success, or (None, JSONResponse) with an
    ApiError on the first violation found. Never touches the database.

    Accepts {"actions": [ ... ]} or a single bare action object
    {"type": "...", ...}. A top-level "dry_run" key, if present, is ignored
    here — the router decides dry-run from the query string.
    """
    if not isinstance(body, dict):
        return None, _import_error("The top level must be a JSON object.")

    if "actions" in body:
        actions_raw = body["actions"]
        if not isinstance(actions_raw, list) or not actions_raw:
            return None, _import_error('"actions" must be a non-empty array.')
    elif isinstance(body.get("type"), str):
        actions_raw = [body]
    else:
        return None, _import_error(
            'The object must contain an "actions" array (or be a single action '
            'object with a "type").'
        )

    actions: list[dict[str, Any]] = []
    saw_save_discussion = 0
    update_card_ids: set[str] = set()

    for idx, entry in enumerate(actions_raw):
        where = f"actions[{idx}]"
        if not isinstance(entry, dict):
            return None, _import_error(f"{where} must be an object.")

        atype = entry.get("type")
        if not isinstance(atype, str):
            return None, _import_error(f'{where} is missing a string "type".')

        if atype == "save_discussion":
            saw_save_discussion += 1
            err = _validate_save_discussion(where, entry)
            if err is not None:
                return None, err
            actions.append({"type": "save_discussion", **_clean_save_discussion(entry)})

        elif atype == "update_card":
            err = _validate_update_card(where, entry)
            if err is not None:
                return None, err
            card_id = entry["card_id"]
            if card_id in update_card_ids:
                return None, _import_error(
                    f"{where}: more than one update_card action targets card_id "
                    f"{card_id}. Merge them into a single update_card."
                )
            update_card_ids.add(card_id)
            actions.append(_clean_update_card(entry))

        elif atype == "create_card":
            err = _validate_create_card(where, entry)
            if err is not None:
                return None, err
            actions.append(_clean_create_card(entry))

        else:
            return None, _import_error(
                f'{where}: unknown action type "{atype}". Supported types are '
                "save_discussion, update_card and create_card."
            )

    if saw_save_discussion == 0:
        return None, _import_error(
            "Every returned result must contain exactly one save_discussion "
            "action so the outcome of the conversation is retained."
        )
    if saw_save_discussion > 1:
        return None, _import_error(
            f"Found {saw_save_discussion} save_discussion actions — there must "
            "be exactly one."
        )

    return actions, None


def _validate_save_discussion(where: str, entry: dict[str, Any]) -> Any:
    if not _is_uuid(entry.get("card_id")):
        return _import_error(
            f'{where} (save_discussion): "card_id" must be the flashcard\'s '
            "id, copied verbatim from card.card_id in the exploration package."
        )
    discussion = entry.get("discussion")
    if not isinstance(discussion, dict):
        return _import_error(f'{where} (save_discussion): "discussion" must be an object.')
    for field in ("exploration_question", "discussion_summary", "resolution"):
        if not _nonempty_str(discussion.get(field)):
            return _import_error(
                f'{where} (save_discussion): "discussion.{field}" is required '
                "and must be a non-empty string."
            )
    kg = discussion.get("knowledge_gap")
    if kg is not None and not isinstance(kg, str):
        return _import_error(
            f'{where} (save_discussion): "discussion.knowledge_gap" must be a '
            "string or null."
        )
    return None


def _clean_save_discussion(entry: dict[str, Any]) -> dict[str, Any]:
    d = entry["discussion"]
    kg = d.get("knowledge_gap")
    kg = kg.strip() if isinstance(kg, str) and kg.strip() else None
    return {
        "card_id": entry["card_id"],
        "discussion": {
            "exploration_question": d["exploration_question"].strip(),
            "discussion_summary": d["discussion_summary"].strip(),
            "resolution": d["resolution"].strip(),
            "knowledge_gap": kg,
        },
    }


def _validate_update_card(where: str, entry: dict[str, Any]) -> Any:
    if not _is_uuid(entry.get("card_id")):
        return _import_error(
            f'{where} (update_card): "card_id" must be the flashcard\'s id, '
            "copied verbatim from card.card_id in the exploration package."
        )
    changes = entry.get("changes")
    if not isinstance(changes, dict) or not changes:
        return _import_error(
            f'{where} (update_card): "changes" must be a non-empty object.'
        )
    bad_keys = [k for k in changes if k not in _ALLOWED_CARD_CHANGES]
    if bad_keys:
        return _import_error(
            f'{where} (update_card): "changes" may only contain '
            f'{", ".join(_ALLOWED_CARD_CHANGES)} — got {", ".join(sorted(bad_keys))}.'
        )
    for k, v in changes.items():
        if not _nonempty_str(v):
            return _import_error(
                f'{where} (update_card): "changes.{k}" must be a non-empty string.'
            )
    if not _nonempty_str(entry.get("reason")):
        return _import_error(
            f'{where} (update_card): "reason" is required and must be a non-empty '
            "string — it is kept as evidence about what makes a flashcard good "
            "or bad."
        )
    return None


def _clean_update_card(entry: dict[str, Any]) -> dict[str, Any]:
    changes = {k: entry["changes"][k].strip() for k in _ALLOWED_CARD_CHANGES if k in entry["changes"]}
    return {
        "type": "update_card",
        "card_id": entry["card_id"],
        "changes": changes,
        "reason": entry["reason"].strip(),
    }


def _validate_create_card(where: str, entry: dict[str, Any]) -> Any:
    if not _is_uuid(entry.get("section_id")):
        return _import_error(
            f'{where} (create_card): "section_id" must be the target section\'s '
            "id (by default card.section_id from the exploration package)."
        )
    if not _nonempty_str(entry.get("question")):
        return _import_error(
            f'{where} (create_card): "question" is required and must be a '
            "non-empty string."
        )
    if not _nonempty_str(entry.get("answer")):
        return _import_error(
            f'{where} (create_card): "answer" is required and must be a '
            "non-empty string."
        )
    anchor = entry.get("section_anchor_slug")
    if anchor is not None and not isinstance(anchor, str):
        return _import_error(
            f'{where} (create_card): "section_anchor_slug" must be a string or '
            "omitted."
        )
    return None


def _clean_create_card(entry: dict[str, Any]) -> dict[str, Any]:
    anchor = entry.get("section_anchor_slug")
    return {
        "type": "create_card",
        "section_id": entry["section_id"],
        "section_anchor_slug": anchor.strip() if isinstance(anchor, str) and anchor.strip() else None,
        "question": entry["question"].strip(),
        "answer": entry["answer"].strip(),
    }


# ── Resolve + plan (SELECT only) ─────────────────────────────────────────────

def resolve_and_plan(cur: Any, actions: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, Any]:
    """
    Resolve every id the actions reference and build a plan. Returns
    (plan, None) or (None, JSONResponse). Issues only SELECTs — safe to call
    inside a transaction that will be rolled back for a dry run.
    """
    save = next(a for a in actions if a["type"] == "save_discussion")
    updates = [a for a in actions if a["type"] == "update_card"]
    creates = [a for a in actions if a["type"] == "create_card"]

    # Every card referenced by save_discussion / update_card must exist.
    card_ids = {save["card_id"]} | {u["card_id"] for u in updates}
    cards: dict[str, dict[str, Any]] = {}
    for cid in card_ids:
        cur.execute(
            "select id, card_key, essay_id, section_id, question, answer "
            "from essaycards.flashcards where id = %s",
            (cid,),
        )
        row = cur.fetchone()
        if not row:
            return None, _import_error(
                f"No flashcard exists with card_id {cid}.", code="NOT_FOUND", status=404
            )
        cards[cid] = dict(row)

    # save_discussion snapshot — taken from the CURRENT card, before any edit.
    sc = cards[save["card_id"]]
    plan_save = {
        "card_id": save["card_id"],
        "card_key": sc["card_key"],
        "exploration_question": save["discussion"]["exploration_question"],
        "discussion_summary": save["discussion"]["discussion_summary"],
        "resolution": save["discussion"]["resolution"],
        "knowledge_gap": save["discussion"]["knowledge_gap"],
        "snapshot": {
            "question_at_time": sc["question"],
            "answer_at_time": sc["answer"],
            "section_id_at_time": str(sc["section_id"]),
        },
    }

    plan_updates = []
    for u in updates:
        cur_card = cards[u["card_id"]]
        old_q, old_a = cur_card["question"], cur_card["answer"]
        new_q = u["changes"].get("question", old_q)
        new_a = u["changes"].get("answer", old_a)
        plan_updates.append({
            "card_id": u["card_id"],
            "card_key": cur_card["card_key"],
            "changed_fields": sorted(u["changes"].keys()),
            "old": {"question": old_q, "answer": old_a},
            "new": {"question": new_q, "answer": new_a},
            "reason": u["reason"],
        })

    plan_creates = []
    for c in creates:
        cur.execute(
            "select id, essay_id, anchor_slug from essaycards.essay_sections where id = %s",
            (c["section_id"],),
        )
        row = cur.fetchone()
        if not row:
            return None, _import_error(
                f"No section exists with section_id {c['section_id']} for the "
                "create_card action.",
                code="NOT_FOUND",
                status=404,
            )
        if c["section_anchor_slug"] is not None and c["section_anchor_slug"] != row["anchor_slug"]:
            return None, _import_error(
                f"create_card section_anchor_slug \"{c['section_anchor_slug']}\" "
                f"does not match section_id {c['section_id']}, whose anchor is "
                f"\"{row['anchor_slug']}\"."
            )
        plan_creates.append({
            "section_id": c["section_id"],
            "section_anchor_slug": row["anchor_slug"],
            "essay_id": str(row["essay_id"]),
            "question": c["question"],
            "answer": c["answer"],
            "card_key": _new_card_key(cur, str(row["essay_id"])),
        })

    return {"save_discussion": plan_save, "update_card": plan_updates, "create_card": plan_creates}, None


def _new_card_key(cur: Any, essay_id: str) -> str:
    """A fresh author-visible key for a discussion-created card. flashcards has
    unique(essay_id, card_key); retry on the (vanishingly unlikely) collision."""
    for _ in range(10):
        key = f"disc-{secrets.token_hex(4)}"
        cur.execute(
            "select 1 from essaycards.flashcards where essay_id = %s and card_key = %s",
            (essay_id, key),
        )
        if not cur.fetchone():
            return key
    raise RuntimeError("could not allocate a unique card_key")  # pragma: no cover


def plan_to_public(plan: dict[str, Any]) -> dict[str, Any]:
    """The plan is already JSON-safe; kept as a seam in case internal fields are
    added later."""
    return plan


# ── Execute (writes; caller owns the transaction) ───────────────────────────

def execute_plan(cur: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """
    Apply the plan in the §12 order. Everything runs on the caller's cursor
    inside the caller's single transaction.
    """
    save = plan["save_discussion"]

    # 1. discussion row (pre-edit snapshots).
    cur.execute(
        """
        insert into essaycards.flashcard_discussions
            (card_id, section_id_at_time, question_at_time, answer_at_time,
             exploration_question, discussion_summary, resolution, knowledge_gap)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        returning id, created_at
        """,
        (
            save["card_id"],
            save["snapshot"]["section_id_at_time"],
            save["snapshot"]["question_at_time"],
            save["snapshot"]["answer_at_time"],
            save["exploration_question"],
            save["discussion_summary"],
            save["resolution"],
            save["knowledge_gap"],
        ),
    )
    drow = cur.fetchone()
    discussion_id = str(drow["id"])

    # 2. per update_card: revision row first, then the live card.
    revisions = []
    for u in plan["update_card"]:
        cur.execute(
            """
            insert into essaycards.flashcard_revisions
                (card_id, source_discussion_id, old_question, new_question,
                 old_answer, new_answer, reason)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                u["card_id"], discussion_id,
                u["old"]["question"], u["new"]["question"],
                u["old"]["answer"], u["new"]["answer"],
                u["reason"],
            ),
        )
        rev_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            update essaycards.flashcards
            set question = %s, answer = %s, updated_at = now()
            where id = %s
            """,
            (u["new"]["question"], u["new"]["answer"], u["card_id"]),
        )
        revisions.append({
            "id": rev_id,
            "card_id": u["card_id"],
            "card_key": u["card_key"],
            "changed_fields": u["changed_fields"],
        })

    # 3. new cards — plus a fresh review-state row, exactly like ingest.
    created_cards = []
    for c in plan["create_card"]:
        cur.execute(
            """
            insert into essaycards.flashcards (essay_id, section_id, card_key, question, answer)
            values (%s, %s, %s, %s, %s)
            returning id, created_at
            """,
            (c["essay_id"], c["section_id"], c["card_key"], c["question"], c["answer"]),
        )
        crow = cur.fetchone()
        cur.execute(
            "insert into essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at) "
            "values (%s, null, %s)",
            (crow["id"], crow["created_at"]),
        )
        created_cards.append({
            "id": str(crow["id"]),
            "card_key": c["card_key"],
            "section_id": c["section_id"],
            "section_anchor_slug": c["section_anchor_slug"],
        })

    return {
        "dry_run": False,
        "applied": True,
        "discussion_id": discussion_id,
        "revisions": revisions,
        "created_cards": created_cards,
        "preview": plan_to_public(plan),
    }
