"""
Derived learning progress (Sprint14_SectionProgressionAndRevalidation).

Single home of the Established / Learned thresholds and of EVERY progress
derivation: card state, the unlock predicate, section state and essay state.
Pure SQL-fragment builders — no database access of its own. Traffic-light
colors are never stored; they are computed at query time from
section_oral_state / essay_oral_state plus flashcard_review_state.review_interval.

Section state (highest satisfied wins):
  blue   unguided_passed
  green  guided_passed AND >= 1 card AND every card established (seen, interval >= 24h)
  yellow guided_passed
  grey   otherwise
Essay state (highest satisfied wins):
  violet essay unguided_passed
  blue   >= 1 section AND every section unguided_passed
  green  >= 1 card AND every card learned (interval >= 30 days)
  yellow essay guided_passed
  grey   otherwise
"""

from __future__ import annotations

ESTABLISHED_INTERVAL_SQL = "interval '24 hours'"
LEARNED_INTERVAL_SQL = "interval '30 days'"

# Expects flashcards aliased `f`. A card is unlocked iff its section has passed
# the guided section oral (derived; no per-card lock column).
UNLOCKED_SECTION_SQL = (
    "exists (select 1 from essaycards.section_oral_state sos "
    "where sos.section_id = f.section_id and sos.guided_passed)"
)

# Expects aliases f (flashcards) and frs (flashcard_review_state, may be null-joined).
CARD_STATE_SQL = f"""
case
  when not {UNLOCKED_SECTION_SQL} then 'locked'
  when frs.last_reviewed_at is null then 'new'
  when frs.review_interval >= {LEARNED_INTERVAL_SQL} then 'learned'
  when frs.review_interval >= {ESTABLISHED_INTERVAL_SQL} then 'established'
  else 'learning'
end
"""


def section_progress_sql() -> str:
    """
    One row per section (aliases e = essay, s = section). Callers append an
    optional WHERE and the ORDER BY. Columns match GET /progress/sections.
    """
    return f"""
    select
      s.id as section_id, s.essay_id, s.heading, s.anchor_slug, s.order_index,
      case
        when coalesce(sos.unguided_passed, false) then 'blue'
        when coalesce(sos.guided_passed, false) and cc.total > 0 and cc.established = cc.total then 'green'
        when coalesce(sos.guided_passed, false) then 'yellow'
        else 'grey'
      end as state,
      case
        when coalesce(sos.unguided_passed, false) then null
        when not coalesce(sos.guided_passed, false) then 'guided_oral'
        when cc.total > 0 and cc.established = cc.total then 'unguided_oral'
        else 'flashcards_established'
      end as next_step,
      coalesce(sos.guided_passed, false) as guided_passed,
      coalesce(sos.unguided_passed, false) as unguided_passed,
      sos.guided_pass_source,
      sos.guided_latest_score, sos.unguided_latest_score,
      sos.guided_passed_at, sos.unguided_passed_at,
      cc.total as cards_total, cc.established as cards_established,
      not coalesce(sos.guided_passed, false) as is_locked
    from essaycards.essay_sections s
    join essaycards.essays e on e.id = s.essay_id
    left join essaycards.section_oral_state sos on sos.section_id = s.id
    left join lateral (
      select count(*) as total,
             count(*) filter (
               where frs.last_reviewed_at is not null
                 and frs.review_interval >= {ESTABLISHED_INTERVAL_SQL}
             ) as established
      from essaycards.flashcards f
      left join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
      where f.section_id = s.id
    ) cc on true
    """


# Column list a query selects from the lateral fragment below (alias ep).
ESSAY_PROGRESS_SELECT = """
  ep.essay_state, ep.essay_next_step,
  ep.essay_guided_passed, ep.essay_unguided_passed,
  ep.essay_guided_latest_score, ep.essay_unguided_latest_score,
  ep.essay_guided_passed_at, ep.essay_unguided_passed_at,
  ep.cards_learned_count, ep.sections_total, ep.sections_unguided_passed_count,
  ep.revalidation_pending_count
"""


def essay_progress_lateral_sql() -> str:
    """
    LEFT JOIN LATERAL fragment (enclosing essays alias `e`, exposes alias `ep`).
    Select ESSAY_PROGRESS_SELECT from it.
    """
    return f"""
    left join lateral (
      select
        case
          when coalesce(eos.unguided_passed, false) then 'violet'
          when sc.n > 0 and sc.unguided_n = sc.n then 'blue'
          when cc.total > 0 and cc.learned = cc.total then 'green'
          when coalesce(eos.guided_passed, false) then 'yellow'
          else 'grey'
        end as essay_state,
        case
          when coalesce(eos.unguided_passed, false) then null
          when sc.n > 0 and sc.unguided_n = sc.n then 'unguided_essay_oral'
          when cc.total > 0 and cc.learned = cc.total then 'section_unguided_orals'
          when coalesce(eos.guided_passed, false) then 'cards_learned'
          else 'guided_essay_oral'
        end as essay_next_step,
        coalesce(eos.guided_passed, false) as essay_guided_passed,
        coalesce(eos.unguided_passed, false) as essay_unguided_passed,
        eos.guided_latest_score as essay_guided_latest_score,
        eos.unguided_latest_score as essay_unguided_latest_score,
        eos.guided_passed_at as essay_guided_passed_at,
        eos.unguided_passed_at as essay_unguided_passed_at,
        cc.learned as cards_learned_count,
        sc.n as sections_total,
        sc.unguided_n as sections_unguided_passed_count,
        cc.pending as revalidation_pending_count
      from (select 1) one
      left join essaycards.essay_oral_state eos on eos.essay_id = e.id
      cross join (
        select count(*) as total,
               count(*) filter (where frs.review_interval >= {LEARNED_INTERVAL_SQL}) as learned,
               count(*) filter (where frs.needs_revalidation) as pending
        from essaycards.flashcards f
        left join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
        where f.essay_id = e.id
      ) cc
      cross join (
        select count(*) as n, count(*) filter (where sos.unguided_passed) as unguided_n
        from essaycards.essay_sections s
        left join essaycards.section_oral_state sos on sos.section_id = s.id
        where s.essay_id = e.id
      ) sc
    ) ep on true
    """
