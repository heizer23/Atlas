"""Ghost Coach endpoints (10_test_spec.md) with a FAKE provider transport. No network call is ever made."""

import json
import logging

import httpx

from backend.config import COACH_CONSENT_VERSION, COACH_MAX_CALLS_PER_DAY
from tests.conftest import (
    DEVICE_1, FAKE_KEY, PLAN_ACCEPTED, PLAN_ACCEPTED_LINKED, PLAN_DISREGARDED, PLAN_INTERVAL, PLAN_RECOMMENDED,
    RUN_COACH_1, RUN_COACH_2, RUN_COMPLETE, RUN_GAP, TOKEN_1, VALID_PLAN, ai_answer, auth,
)
from tests.test_native_sync import NATIVE, batch, begin, finish, finish_body, put

COACH = "/api/runningtracker/coach"
UNKNOWN = "99999999-9999-9999-9999-999999999999"


def row(r):
    return r.json()["rows"][0]


def enable(client):
    r = client.patch(f"{COACH}/settings", json={"ai_enabled": True, "consent_version": COACH_CONSENT_VERSION})
    assert r.status_code == 200
    return r


def analyse(client, run=RUN_COACH_1, force=False):
    return client.post(f"{COACH}/runs/{run}/analysis" + ("?force=true" if force else ""))


def q(db_conn, sql, *params):
    with db_conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def err(r, status, code):
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code


# ── consent and settings ────────────────────────────────────────────────────

def test_ai_is_off_by_default(client):
    r = client.get(f"{COACH}/settings")
    s = row(r)
    assert r.json()["meta"]["total"] == 1
    assert s["ai_enabled"] is False and s["consent_current"] is False and s["consented_at"] is None
    assert s["key_configured"] is False and s["daily_cap"] == COACH_MAX_CALLS_PER_DAY
    assert s["consent_version_required"] == COACH_CONSENT_VERSION


def test_enabling_ai_requires_the_current_consent_version(client):
    for body in ({"ai_enabled": True}, {"ai_enabled": True, "consent_version": COACH_CONSENT_VERSION - 1}):
        err(client.patch(f"{COACH}/settings", json=body), 422, "CONSENT_VERSION_MISMATCH")
    assert row(client.get(f"{COACH}/settings"))["ai_enabled"] is False
    s = row(enable(client))
    assert s["ai_enabled"] is True and s["consent_current"] is True and s["consented_at"] is not None


def test_disabling_ai_clears_consent(client, provider, db_conn):
    enable(client)
    s = row(client.patch(f"{COACH}/settings", json={"ai_enabled": False, "consent_version": 99}))
    assert s["ai_enabled"] is False and s["consent_current"] is False and s["consented_at"] is None
    assert q(db_conn, "select consent_version, consented_at from runningtracker.coach_settings")[0] == {"consent_version": None, "consented_at": None}
    err(analyse(client), 403, "CONSENT_REQUIRED")
    err(client.patch(f"{COACH}/settings", json={"ai_enabled": None}), 422, "VALIDATION_ERROR")


def test_goal_text_null_versus_omitted(client):
    assert row(client.get(f"{COACH}/settings"))["goal_text"] == "Run a relaxed half marathon"
    assert row(client.patch(f"{COACH}/settings", json={"ai_enabled": False}))["goal_text"] == "Run a relaxed half marathon"
    assert row(client.patch(f"{COACH}/settings", json={"goal_text": "  Sub 2h  "}))["goal_text"] == "Sub 2h"
    assert row(client.patch(f"{COACH}/settings", json={"goal_text": None}))["goal_text"] is None
    client.patch(f"{COACH}/settings", json={"goal_text": "again"})
    assert row(client.patch(f"{COACH}/settings", json={"goal_text": "   "}))["goal_text"] is None
    assert client.patch(f"{COACH}/settings", json={"goal_text": "x" * 501}).status_code == 422
    assert client.patch(f"{COACH}/settings", json={"surprise": 1}).status_code == 422


# ── preview and egress ─────────────────────────────────────────────────────

def test_preview_is_byte_identical_to_what_is_sent_and_stored(client, provider, db_conn):
    r = client.get(f"{COACH}/analysis-preview", params={"run_id": RUN_COACH_1})   # no consent, no key needed, no call
    assert r.status_code == 200 and provider.requests == []
    preview = json.loads(row(r)["payload_json"])
    enable(client)
    assert analyse(client).status_code == 200
    sent = provider.user_content()
    assert json.loads(sent) == preview
    assert row(r)["byte_size"] == len(sent.encode())
    stored = q(db_conn, "select sent_payload from runningtracker.coach_analyses")[0]["sent_payload"]
    assert stored == preview
    err(client.get(f"{COACH}/analysis-preview", params={"run_id": UNKNOWN}), 404, "NOT_FOUND")
    err(client.get(f"{COACH}/analysis-preview", params={"run_id": RUN_GAP}), 409, "RUN_NOT_ANALYSABLE")


def test_request_to_provider_carries_the_key_only_in_the_header_and_never_follows_up_with_a_second_call(client, provider):
    enable(client)
    analyse(client)
    assert len(provider.requests) == 1
    req = provider.requests[0]
    assert req.headers["x-api-key"] == FAKE_KEY and req.url.host == "api.anthropic.com"
    body = json.loads(req.content)
    assert body["model"] == "fake-model" and FAKE_KEY not in req.content.decode()
    assert "SECRET" not in req.content.decode()


def test_key_never_appears_in_responses_logs_or_rows(client, provider, db_conn, caplog):
    caplog.set_level(logging.DEBUG)
    enable(client)
    texts = [client.get(f"{COACH}/settings").text, client.get(f"{COACH}/analysis-preview", params={"run_id": RUN_COACH_1}).text,
             analyse(client).text]
    provider.answer = lambda request: httpx.Response(500, text=f"boom {FAKE_KEY}")
    texts.append(analyse(client, force=True).text)
    assert row(client.get(f"{COACH}/settings"))["key_configured"] is True
    assert all(FAKE_KEY not in t for t in texts)
    assert FAKE_KEY not in caplog.text
    dump = json.dumps([dict(r, **{k: str(v) for k, v in r.items()}) for t in (
        "coach_settings", "coach_analyses", "coach_ai_calls", "coach_plans", "coach_profile_items")
        for r in q(db_conn, f"select * from runningtracker.{t}")], default=str)
    assert FAKE_KEY not in dump


def test_host_outside_the_allow_list_is_refused_without_a_call(client, provider, monkeypatch, db_conn):
    monkeypatch.setenv("RUNNINGTRACKER_COACH_API_URL", "https://evil.example.com/v1/messages")
    enable(client)
    assert row(client.get(f"{COACH}/settings"))["key_configured"] is False
    err(analyse(client), 503, "AI_NOT_CONFIGURED")
    assert provider.requests == [] and q(db_conn, "select count(*) as n from runningtracker.coach_ai_calls")[0]["n"] == 0
    monkeypatch.setenv("RUNNINGTRACKER_COACH_API_URL", "http://api.anthropic.com/v1/messages")  # not https
    err(analyse(client), 503, "AI_NOT_CONFIGURED")


# ── analysis ────────────────────────────────────────────────────────────

def test_analysis_happy_path(client, provider, db_conn):
    provider.answer = ai_answer(profile_updates=[{"key": "aerobic_endurance", "value": "Building steadily", "confidence": 0.99}],
                                previous_recommendation_effect="Followed it.")
    enable(client)
    r = analyse(client)
    a = row(r)
    assert r.status_code == 200 and r.json()["meta"]["total"] == 1
    assert a["assessment"] == "Solid steady run." and a["previous_effect"] == "Followed it." and a["plan_id"]
    assert a["plan_rejected_reason"] is None and a["model"] == "fake-model" and a["prompt_version"] == "v1"
    plan = q(db_conn, "select status, plan_type, analysis_id from runningtracker.coach_plans where id = %s", a["plan_id"])[0]
    assert plan["status"] == "recommended" and plan["plan_type"] == "easy_continuous"
    inferred = {r["key"]: r for r in q(db_conn, "select * from runningtracker.coach_profile_items where basis = 'inferred'")}
    assert inferred["aerobic_endurance"]["confidence"] == 0.9 and inferred["aerobic_endurance"]["value_text"] == "Building steadily"
    keys = {r["key"] for r in q(db_conn, "select key from runningtracker.coach_profile_items where basis = 'measured'")}
    assert {"natural_cadence_spm", "runs_per_week", "pr_longest_run_m"} <= keys
    assert [c["outcome"] for c in q(db_conn, "select outcome from runningtracker.coach_ai_calls")] == ["ok"]


def test_analysis_is_idempotent_unless_forced(client, provider, db_conn):
    enable(client)
    first = row(analyse(client))
    again = row(analyse(client))
    assert again == first and len(provider.requests) == 1
    provider.answer = ai_answer(assessment="Second opinion.")
    forced = row(analyse(client, force=True))
    assert len(provider.requests) == 2 and forced["assessment"] == "Second opinion." and forced["plan_id"] != first["plan_id"]
    assert q(db_conn, "select count(*) as n from runningtracker.coach_analyses")[0]["n"] == 1
    status = {r["id"]: r["status"] for r in q(db_conn, "select id::text, status from runningtracker.coach_plans")}
    assert status[first["plan_id"]] == "superseded" and status[forced["plan_id"]] == "recommended"


def test_analysis_check_order(client, provider, db_conn):
    err(analyse(client, UNKNOWN), 404, "NOT_FOUND")
    err(analyse(client, RUN_GAP), 409, "RUN_NOT_ANALYSABLE")
    with db_conn.cursor() as cur:
        cur.execute("update runningtracker.runs set moving_s = 100 where id = %s", (RUN_COACH_2,))
    err(analyse(client, RUN_COACH_2), 409, "RUN_NOT_ANALYSABLE")
    err(analyse(client), 403, "CONSENT_REQUIRED")
    enable(client)
    # key missing: remove it from the environment of this test
    import os
    key = os.environ.pop("RUNNINGTRACKER_COACH_API_KEY")
    try:
        err(analyse(client), 503, "AI_NOT_CONFIGURED")
    finally:
        os.environ["RUNNINGTRACKER_COACH_API_KEY"] = key
    with db_conn.cursor() as cur:
        cur.execute("insert into runningtracker.coach_ai_calls (run_id, outcome) select %s, 'ok' from generate_series(1, %s)",
                    (RUN_COACH_1, COACH_MAX_CALLS_PER_DAY))
    err(analyse(client), 429, "RATE_LIMITED")
    assert provider.requests == []


def test_provider_failure_leaves_no_analysis_and_a_retry_succeeds(client, provider, db_conn):
    enable(client)
    good = provider.answer
    for failing in (lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
                    lambda request: httpx.Response(500, text="oops"),
                    lambda request: httpx.Response(302, headers={"location": "https://evil.example.com/"})):
        provider.answer = failing
        err(analyse(client), 502, "AI_UNAVAILABLE")
    assert q(db_conn, "select count(*) as n from runningtracker.coach_analyses")[0]["n"] == 0
    assert [r["outcome"] for r in q(db_conn, "select outcome from runningtracker.coach_ai_calls")] == ["provider_error"] * 3
    assert len(provider.requests) == 3                                 # the redirect was not followed
    provider.answer = good
    assert analyse(client).status_code == 200


def test_invalid_provider_output_is_rejected(client, provider, db_conn):
    enable(client)
    for bad in ("sorry, I cannot do that", {**ai_answer(), "extra": 1}, ai_answer(assessment=""), "[1, 2]"):
        provider.answer = bad
        err(analyse(client), 502, "AI_INVALID_RESPONSE")
    assert q(db_conn, "select count(*) as n from runningtracker.coach_analyses")[0]["n"] == 0
    assert {r["outcome"] for r in q(db_conn, "select outcome from runningtracker.coach_ai_calls")} == {"invalid_response"}
    provider.answer = "```json\n" + json.dumps(ai_answer()) + "\n```"          # a single code fence is tolerated
    assert analyse(client).status_code == 200


def test_invalid_plan_keeps_the_assessment(client, provider, db_conn):
    bad_plan = {**VALID_PLAN, "segments": [{"kind": "steady", "duration_s": 1800, "hr": {"min": 150, "max": 230}, "pace": None, "cadence": None}]}
    provider.answer = ai_answer(next_session=bad_plan)
    enable(client)
    a = row(analyse(client))
    assert a["plan_rejected_reason"] == "plan_bounds" and a["plan_id"] is None and a["assessment"]
    assert q(db_conn, "select count(*) as n from runningtracker.coach_plans where status = 'recommended' and id::text = %s", PLAN_RECOMMENDED)[0]["n"] == 1
    assert q(db_conn, "select count(*) as n from runningtracker.coach_plans")[0]["n"] == 5      # fixtures only
    provider.answer = ai_answer(next_session=None)                                              # "no session" is not a rejection
    a = row(analyse(client, force=True))
    assert a["plan_id"] is None and a["plan_rejected_reason"] is None


def test_interval_plans_stay_occasional(client, provider, db_conn):
    interval = {**VALID_PLAN, "type": "interval", "segments": [
        {"kind": "work", "duration_s": 120, "hr": None, "pace": None, "cadence": None},
        {"kind": "recovery", "duration_s": 120, "hr": None, "pace": None, "cadence": None},
        {"kind": "work", "duration_s": 120, "hr": None, "pace": None, "cadence": None}]}
    provider.answer = ai_answer(next_session=interval)
    enable(client)
    a = row(analyse(client))                                            # fix-plan-interval is one of the latest two plans
    assert a["plan_rejected_reason"] == "plan_interval_frequency" and a["plan_id"] is None
    with db_conn.cursor() as cur:
        cur.execute("update runningtracker.coach_plans set status = 'disregarded' where id = %s", (PLAN_INTERVAL,))
    a = row(analyse(client, force=True))
    assert a["plan_rejected_reason"] is None and a["plan_id"]


def test_inferred_profile_needs_enough_runs(client, provider, db_conn):
    updates = [{"key": "aerobic_endurance", "value": "ok", "confidence": 0.99}, {"key": "unknown_key", "value": "x", "confidence": 0.5}]
    provider.answer = ai_answer(profile_updates=updates)
    enable(client)
    with db_conn.cursor() as cur:   # leave RUN_COACH_1 and one more complete run: below COACH_MIN_RUNS_INFERRED
        cur.execute("delete from runningtracker.runs where id::text <> %s and started_at < '2026-03-12' and status = 'complete'", (RUN_COACH_1,))
        cur.execute("delete from runningtracker.coach_profile_items where basis = 'inferred'")
    assert row(analyse(client))["assessment"]
    assert q(db_conn, "select count(*) as n from runningtracker.coach_profile_items where basis = 'inferred'")[0]["n"] == 0


def test_inferred_profile_with_ten_runs_is_capped_and_filtered(client, provider, db_conn):
    updates = [{"key": "aerobic_endurance", "value": "ok", "confidence": 0.99}, {"key": "unknown_key", "value": "x", "confidence": 0.5}]
    provider.answer = ai_answer(profile_updates=updates)
    enable(client)
    assert row(analyse(client))["assessment"]                    # fixtures hold 9 runs with metrics: cap 0.2 + 0.1 * 9 -> 0.9
    items = {r["key"]: r for r in q(db_conn, "select * from runningtracker.coach_profile_items where basis = 'inferred'")}
    assert set(items) == {"aerobic_endurance"} and items["aerobic_endurance"]["confidence"] == 0.9
    assert items["aerobic_endurance"]["n_runs"] == 9


def test_analysis_read_for_the_run_detail(client, provider):
    enable(client)
    analyse(client)
    one = client.get(f"{COACH}/runs/{RUN_COACH_1}/analysis")
    assert one.json()["meta"]["total"] == 1 and row(one)["assessment"] == "Solid steady run."
    none = client.get(f"{COACH}/runs/{RUN_COACH_2}/analysis")
    assert none.status_code == 200 and none.json()["meta"]["total"] == 0 and none.json()["rows"] == []
    err(client.get(f"{COACH}/runs/{UNKNOWN}/analysis"), 404, "NOT_FOUND")


# ── profile, plans ───────────────────────────────────────────────────────

def test_profile_read_order(client, db_conn):
    rows = client.get(f"{COACH}/profile").json()["rows"]
    assert [r["basis"] for r in rows] == ["measured", "inferred"]
    assert rows[0]["confidence"] is None and rows[1]["confidence"] == 0.5 and rows[0]["label"] == "Natural cadence"
    with db_conn.cursor() as cur:
        cur.execute("delete from runningtracker.coach_profile_items")
    empty = client.get(f"{COACH}/profile")
    assert empty.status_code == 200 and empty.json()["meta"]["total"] == 0


def test_next_session_selection(client, db_conn):
    r = client.get(f"{COACH}/next-session")
    assert row(r)["id"] == PLAN_ACCEPTED and row(r)["status"] == "accepted" and r.json()["meta"]["total"] == 1
    assert client.patch(f"{COACH}/plans/{PLAN_ACCEPTED}", json={"status": "disregarded"}).status_code == 200
    assert row(client.get(f"{COACH}/next-session"))["id"] == PLAN_RECOMMENDED
    with db_conn.cursor() as cur:
        cur.execute("update runningtracker.coach_plans set status = 'disregarded' where id = %s", (PLAN_RECOMMENDED,))
    assert client.get(f"{COACH}/next-session").json()["rows"] == []


def test_accept_a_plan_unchanged(client, db_conn):
    r = client.patch(f"{COACH}/plans/{PLAN_RECOMMENDED}", json={"status": "accepted"})
    assert row(r)["status"] == "accepted" and row(r)["decided_at"] is not None
    rec = q(db_conn, "select plan, active_plan from runningtracker.coach_plans where id = %s", PLAN_RECOMMENDED)[0]
    assert rec["active_plan"] == rec["plan"]
    status = {str(r["id"]): r["status"] for r in q(db_conn, "select id, status from runningtracker.coach_plans")}
    assert status[PLAN_ACCEPTED] == "superseded" and status[PLAN_ACCEPTED_LINKED] == "accepted"    # linked plan untouched


def test_modify_with_null_versus_omitted(client, db_conn):
    body = {"status": "accepted", "overrides": {"cadence": {"min": 170, "max": 180}, "pace": None}}
    r = client.patch(f"{COACH}/plans/{PLAN_RECOMMENDED}", json=body)
    pr = row(r)
    assert (pr["cad_min"], pr["cad_max"]) == (170, 180) and pr["pace_fast_s_per_km"] is None and (pr["hr_min"], pr["hr_max"]) == (130, 145)
    rec = q(db_conn, "select plan, active_plan from runningtracker.coach_plans where id = %s", PLAN_RECOMMENDED)[0]
    steady = next(s for s in rec["active_plan"]["segments"] if s["kind"] == "steady")
    assert steady["cadence"] == {"min": 170, "max": 180} and steady["pace"] is None
    original = next(s for s in rec["plan"]["segments"] if s["kind"] == "steady")
    assert original["pace"] == {"fast_s_per_km": 330, "slow_s_per_km": 390} and original["cadence"] == {"min": 165, "max": 175}
    again = client.patch(f"{COACH}/plans/{PLAN_RECOMMENDED}", json={"status": "accepted", "overrides": {"hr": {"min": 125, "max": 140}}})
    assert (row(again)["hr_min"], row(again)["cad_min"]) == (125, 170)      # re-modify keeps the earlier active values


def test_invalid_overrides_are_rejected(client):
    for overrides in ({"hr": {"min": 150, "max": 230}}, {"cadence": {"min": 175, "max": 165}}, {"speed": 1}):
        err(client.patch(f"{COACH}/plans/{PLAN_RECOMMENDED}", json={"status": "accepted", "overrides": overrides}), 422, "PLAN_INVALID")
    assert row(client.patch(f"{COACH}/plans/{PLAN_RECOMMENDED}", json={"status": "disregarded"}))["status"] == "disregarded"
    err(client.patch(f"{COACH}/plans/{PLAN_RECOMMENDED}", json={"status": "disregarded", "overrides": {}}), 422, "VALIDATION_ERROR")


def test_clearing_hr_on_an_hr_controlled_plan_is_rejected(client, db_conn):
    plan = {**VALID_PLAN, "type": "hr_controlled"}
    with db_conn.cursor() as cur:
        cur.execute("update runningtracker.coach_plans set plan = %s::jsonb, plan_type = 'hr_controlled' where id = %s",
                    (json.dumps(plan), PLAN_RECOMMENDED))
    err(client.patch(f"{COACH}/plans/{PLAN_RECOMMENDED}", json={"status": "accepted", "overrides": {"hr": None}}), 422, "PLAN_INVALID")
    assert client.get(f"{COACH}/plans").json()["rows"][0]["status"] in ("completed", "recommended")


def test_forbidden_transitions(client):
    for plan, status in ((PLAN_DISREGARDED, "accepted"), (PLAN_INTERVAL, "disregarded"), (PLAN_ACCEPTED_LINKED, "accepted"),
                         (PLAN_ACCEPTED_LINKED, "disregarded")):
        err(client.patch(f"{COACH}/plans/{plan}", json={"status": status}), 409, "INVALID_TRANSITION")
    err(client.patch(f"{COACH}/plans/{UNKNOWN}", json={"status": "accepted"}), 404, "NOT_FOUND")
    err(client.patch(f"{COACH}/plans/not-a-uuid", json={"status": "accepted"}), 404, "NOT_FOUND")


def test_plan_history_list(client):
    rows = client.get(f"{COACH}/plans").json()["rows"]
    assert [r["id"] for r in rows] == [PLAN_INTERVAL, PLAN_RECOMMENDED, PLAN_ACCEPTED, PLAN_ACCEPTED_LINKED, PLAN_DISREGARDED]
    assert rows[0]["outcome_summary"].startswith("completed") and rows[1]["summary"].startswith("Easy continuous - 40 min")
    assert len(client.get(f"{COACH}/plans", params={"limit": 1}).json()["rows"]) == 1
    for limit in (0, 51):
        assert client.get(f"{COACH}/plans", params={"limit": limit}).status_code == 422


# ── native plan transport and the finish hook ──────────────────────────────

def test_phone_fetches_the_active_plan(client):
    url = f"{NATIVE}/coach/next-plan"
    r = client.get(url, headers=auth(TOKEN_1))
    assert r.status_code == 200 and r.json()["plan_id"] == PLAN_ACCEPTED and r.json()["schema_version"] == 1
    assert r.json()["plan"]["segments"][1]["hr"] == {"min": 130, "max": 145}
    err(client.get(url), 401, "DEVICE_UNAUTHORIZED")
    err(client.get(url, headers={**auth(TOKEN_1), "cf-connecting-ip": "1.2.3.4"}), 403, "NATIVE_ROUTE_FORBIDDEN")
    client.patch(f"{COACH}/plans/{PLAN_ACCEPTED}", json={"status": "disregarded"})
    assert client.get(url, headers=auth(TOKEN_1)).json() == {"plan_id": None, "schema_version": None, "plan": None}


def run_and_finish(client, plan_id=None, run=None, n=40):
    from tests.conftest import NEW_RUN
    run = run or NEW_RUN
    assert begin(client, run).status_code == 200
    put(client, run, batch(n // 2, n // 2))
    body = finish_body(n, n // 2, n // 2)
    if plan_id is not None:
        body["coach_plan_id"] = plan_id
    return finish(client, run, body)


def test_finish_links_the_plan_and_stores_the_outcome(client, db_conn):
    from tests.conftest import NEW_RUN
    r = run_and_finish(client, PLAN_ACCEPTED)
    assert r.status_code == 200 and r.json()["result"] == "complete"
    plan = q(db_conn, "select status, run_id::text as run_id, outcome from runningtracker.coach_plans where id = %s", PLAN_ACCEPTED)[0]
    assert plan["status"] == "completed" and plan["run_id"] == NEW_RUN
    o = plan["outcome"]
    assert o["planned_s"] == 2400 and o["completed"] is False and o["in_range"] == {"hr": None, "pace": None, "cadence": None}
    assert q(db_conn, "select count(*) as n from runningtracker.coach_profile_items where basis = 'measured'")[0]["n"] >= 5
    # replay: same answer, still one linked plan, same outcome
    body = finish_body(40, 20, 20)
    body["coach_plan_id"] = PLAN_ACCEPTED
    r2 = finish(client, NEW_RUN, body)
    assert r2.status_code == 200 and r2.json() == r.json()
    again = q(db_conn, "select outcome from runningtracker.coach_plans where run_id::text = %s", NEW_RUN)
    assert len(again) == 1 and again[0]["outcome"] == o


def test_finish_ignores_unknown_or_unusable_plan_ids(client, db_conn):
    from tests.conftest import NEW_RUN
    for bad in ("not-a-uuid", UNKNOWN, PLAN_DISREGARDED, PLAN_ACCEPTED_LINKED, PLAN_RECOMMENDED):
        run = NEW_RUN[:-1] + str(["not-a-uuid", UNKNOWN, PLAN_DISREGARDED, PLAN_ACCEPTED_LINKED, PLAN_RECOMMENDED].index(bad) + 2)
        r = run_and_finish(client, bad, run)
        assert r.status_code == 200 and r.json()["result"] == "complete"
    linked = q(db_conn, "select id::text, status, run_id::text as run_id from runningtracker.coach_plans order by id")
    by_id = {p["id"]: p for p in linked}
    assert by_id[PLAN_DISREGARDED]["status"] == "disregarded" and by_id[PLAN_DISREGARDED]["run_id"] is None
    assert by_id[PLAN_RECOMMENDED]["run_id"] is None and by_id[PLAN_ACCEPTED_LINKED]["run_id"] == RUN_COACH_2
    assert run_and_finish(client, None, NEW_RUN[:-1] + "9").status_code == 200       # old body without the key


def test_coach_hook_errors_never_break_finish(client, monkeypatch, db_conn, caplog):
    from backend import coach_store
    monkeypatch.setattr(coach_store, "refresh_measured_profile", lambda conn: 1 / 0)
    caplog.set_level(logging.WARNING)
    r = run_and_finish(client, PLAN_ACCEPTED)
    assert r.status_code == 200 and r.json()["result"] == "complete"
    assert "coach finish hook failed: ZeroDivisionError" in caplog.text
    assert q(db_conn, "select status from runningtracker.runs where id = 'a1000000-0000-0000-0000-000000000001'")[0]["status"] == "complete"


def test_existing_behavior_unchanged_without_coaching(client):
    runs = client.get("/api/runningtracker/runs")
    assert runs.status_code == 200 and client.get(f"/api/runningtracker/runs/{RUN_COMPLETE}").status_code == 200
    r = run_and_finish(client)
    assert r.status_code == 200 and r.json()["result"] == "complete"
    assert client.post(f"{NATIVE}/runs/a1000000-0000-0000-0000-000000000001/finish", headers=auth(TOKEN_1),
                       json={**finish_body(40, 20, 20), "surprise": 1}).status_code == 422   # extra keys still forbidden
