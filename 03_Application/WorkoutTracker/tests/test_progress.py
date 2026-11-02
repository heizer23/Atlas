"""Pure statistics: streaks, ranking, monthly counts, frequency, last-year comparison, celebration."""

import datetime as dt

from backend import progress as p

D = dt.date


def days(*iso):
    return {D.fromisoformat(i) for i in iso}


def run(start, n):
    s = D.fromisoformat(start)
    return {s + dt.timedelta(days=i) for i in range(n)}


def test_streaks_across_new_year_and_current_flag():
    ds = run("2026-12-29", 6)  # 29 Dec .. 3 Jan
    r = p.find_streaks(ds, D(2027, 1, 3))
    assert len(r) == 1 and r[0]["length"] == 6 and r[0]["current"]
    # alive until the end of tomorrow: ended yesterday still current; two days ago is broken
    assert p.find_streaks(ds, D(2027, 1, 4))[0]["current"]
    assert not p.find_streaks(ds, D(2027, 1, 5))[0]["current"]


def test_same_day_session_never_changes_distinct_days():
    ds = run("2026-05-01", 3)
    assert p.snapshot(ds | days("2026-05-03"), D(2026, 5, 3)) == p.snapshot(ds, D(2026, 5, 3))


def test_ranking_ties_current_first_then_recent_and_ranks_positional():
    ds = run("2026-01-01", 3) | run("2026-02-01", 3) | run("2026-03-01", 3) | run("2026-03-10", 1)
    ranked = p.rank_streaks(p.find_streaks(ds, D(2026, 3, 3)))
    assert [r["start"] for r in ranked] == ["2026-03-01", "2026-02-01", "2026-01-01", "2026-03-10"]
    assert ranked[0]["current"] and [r["rank"] for r in ranked] == [1, 2, 3, 4]


def test_ten_day_qualification_and_crossing_celebrated_once():
    before = run("2026-05-01", 9)
    after = before | days("2026-05-10")
    c = p.celebration(before, after, D(2026, 5, 10), D(2026, 5, 10))
    assert c["changed"] and c["crossed_champions"]
    assert c["after"]["current"]["length"] == 10
    # day eleven and a repeat on day ten do not celebrate again
    assert not p.celebration(after, after | days("2026-05-11"), D(2026, 5, 11), D(2026, 5, 11))["crossed_champions"]
    assert not p.celebration(after, after, D(2026, 5, 10), D(2026, 5, 10))["crossed_champions"]


def test_second_session_same_day_is_not_progress():
    ds = run("2026-05-01", 4)
    c = p.celebration(ds, ds, D(2026, 5, 4), D(2026, 5, 4))
    assert not c["changed"] and c["note"] == "Today already counts."
    assert c["before"] == c["after"]


def test_backdated_completion_is_not_celebrated():
    assert p.celebration(days("2026-05-01"), days("2026-05-01", "2026-04-20"), D(2026, 4, 20), D(2026, 5, 4)) is None


def test_finishing_today_extends_yesterdays_streak():
    before = run("2026-05-01", 4)
    c = p.celebration(before, before | days("2026-05-05"), D(2026, 5, 5), D(2026, 5, 5))
    assert c["before"]["current"]["length"] == 4 and c["after"]["current"]["length"] == 5


def test_new_streak_after_gap_starts_at_one():
    before = run("2026-05-01", 4)
    c = p.celebration(before, before | days("2026-05-07"), D(2026, 5, 7), D(2026, 5, 7))
    assert c["before"]["current"]["length"] == 0 and c["after"]["current"]["length"] == 1


def test_this_year_includes_streaks_crossing_new_year_with_full_length():
    ds = run("2025-12-28", 8) | days("2026-03-01") | days("2025-06-01")
    s = p.snapshot(ds, D(2026, 3, 1))
    assert [r["length"] for r in s["ranking_year"]] == [8, 1]
    assert [r["length"] for r in s["ranking"]] == [8, 1, 1]


def test_monthly_counts_distinct_days_and_future_months_empty():
    s = p.snapshot(days("2026-02-03", "2026-02-04", "2025-02-10"), D(2026, 2, 20))
    assert s["monthly"]["2026"][1] == 2 and s["monthly"]["2026"][2] is None
    assert s["monthly"]["2025"][1] == 1


def test_frequency_is_cumulative_days_over_elapsed_days_times_seven():
    ds = run("2025-01-01", 31) | days("2026-01-05", "2026-01-06")  # all Jan 2025; 2 days in 2026
    s = p.snapshot(ds, D(2026, 1, 14))
    assert s["frequency"]["2025"][0] == round(31 / 31 * 7, 3)           # month-end point
    assert s["frequency"]["2025"][1] == round(31 / 59 * 7, 3)           # cumulative through 28 Feb
    assert s["frequency"]["2026"][0] == round(2 / 14 * 7, 3)            # current point uses today
    assert s["frequency"]["2026"][1] is None


def test_last_year_comparison_through_equivalent_date_and_leap_clamp():
    assert p.equivalent_last_year(D(2028, 2, 29)) == D(2027, 2, 28)
    assert p.equivalent_last_year(D(2027, 3, 31)) == D(2026, 3, 31)
    ds = days("2025-11-01", "2025-11-12", "2025-11-13", "2026-11-02", "2026-11-05", "2026-11-12")
    m = p.snapshot(ds, D(2026, 11, 12))["month"]
    assert (m["count"], m["last_year_count"], m["ahead"]) == (3, 2, 1)  # 13 Nov last year is after the cut-off


def test_no_prior_data_means_no_comparison_or_previous_year_line():
    s = p.snapshot(days("2026-11-02"), D(2026, 11, 12))
    assert s["month"]["ahead"] is None and list(s["frequency"]) == ["2026"] and s["years"] == [2026]
