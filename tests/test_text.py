import numpy as np
import pandas as pd

from data import STATEMENTS, decision_word, read_fed, read_survey, read_valet
from estimate import adjusted_moves, spearman, variance_ratio
from text import compare, decode, parse, reading_grade, sentences, tone

PAGE = """<h1 class="post-heading">Bank of Canada holds rate at 2&frac14;%</h1>
<main id="main-content"><div class='post-date'>October 28, 2026</div>
<p>Inflation is rising. Growth is strong.</p><p>Information note</p><p>The next scheduled date is December 9.</p></main>"""


def test_parse_drops_the_information_note():
    p = parse(PAGE)
    assert p["title"] == "Bank of Canada holds rate at 2¼%"
    assert p["date"] == "October 28, 2026"
    assert p["text"] == "Inflation is rising. Growth is strong."
    assert p["note"]


def test_parse_returns_nothing_for_other_pages():
    assert parse("<main><p>A speech</p></main>") is None


def test_decode_handles_older_pages():
    assert decode("Bank’s".encode("cp1252")) == "Bank’s"
    assert decode("2½%".encode("utf-8")) == "2½%"


def test_tone_signs():
    assert tone("Inflation is rising and growth is strong.") == 1
    assert tone("Inflation is falling and growth is weak.") == -1
    assert tone("Unemployment is rising.") == -1  # more slack is dovish
    assert tone("The Bank met today.") == 0


def test_tone_ignores_direction_words_about_other_things():
    assert tone("The Governor rose to speak.") == 0


def test_sentences_keep_decimals_together():
    assert sentences("Inflation was 2.5% in May. It fell.") == ["Inflation was 2.5% in May.", "It fell."]


def test_reading_grade_rises_with_harder_text():
    assert reading_grade("The cat sat. The dog ran.") < reading_grade("Macroeconomic considerations necessitate considerable deliberation regarding inflationary developments.")


def test_compare_marks_changed_words_and_lost_sentences():
    parts, lost = compare("Inflation is two per cent today. Exports are weak this year.", "Inflation is three per cent today. Tariffs arrived.")
    assert parts[0] == [[0, "Inflation is"], [1, "three"], [0, "per cent today."]]
    assert parts[1] == [[1, "Tariffs arrived."]]
    assert lost == ["Exports are weak this year."]


def test_decision_word():
    assert decision_word("Bank of Canada lowers overnight rate target to 3/4 per cent") == "cut"
    assert decision_word("Bank of Canada raises the policy rate by 25 basis points") == "hike"
    assert decision_word("Bank of Canada maintains overnight rate target") == "hold"
    assert decision_word("Bank of Canada publishes its schedule") is None


def test_read_valet_skips_notes_and_blanks():
    body = '"TERMS"\n"x"\n\n"OBSERVATIONS"\n"date","A"\n"2026-01-02","1.50"\n"2026-01-05",""\n"2026-01-06","1.60"\n'
    s = read_valet(body, "A")
    assert list(s.values) == [1.5, 1.6]


def test_read_fed_both_layouts():
    calendar = """<div class="panel-heading"><h4>2026 FOMC Meetings</h4></div>
    <div class="fomc-meeting__month x"><strong>Apr/May</strong></div><div class="fomc-meeting__date x">30-1</div>"""
    assert read_fed(calendar) == [pd.Timestamp("2026-05-01")]
    assert read_fed('<h5 class="panel-heading">January 29-30 Meeting - 2019</h5>') == [pd.Timestamp("2019-01-30")]


def test_read_survey_rolls_the_year():
    page = """<div class='post-date'>August 1, 2024</div><table><tr><th></th><th>Policy interest rate (%)</th></tr>
    <tr><th>2024</th><th>25th</th><th>Median</th><th>75th</th><th>n</th></tr>
    <tr><td>December</td><td>4.00</td><td>4.25</td><td>4.25</td><td>25</td></tr>
    <tr><td>January</td><td>3.75</td><td>4.00</td><td>4.00</td><td>25</td></tr></table>"""
    assert [(r["year"], r["month"], r["median"]) for r in read_survey(page)] == [(2024, 12, 4.25), (2025, 1, 4.0)]


def test_adjusted_moves_removes_the_us_part():
    days = pd.bdate_range("2020-01-01", periods=300)
    rng = np.random.default_rng(1)
    us = pd.Series(np.cumsum(rng.normal(0, 0.05, 300)), index=days)
    ca = us * 0.5 + np.cumsum(rng.normal(0, 0.001, 300))
    d, beta = adjusted_moves(ca, us, [days[50]], ("2020-01-01", "2021-12-31"))
    assert abs(beta - 0.5) < 0.02
    assert d.event.sum() == 1
    assert d.res.std() < d.ca.std() / 5


def test_spearman_and_variance_ratio_on_known_cases():
    x = np.arange(50.0)
    assert abs(spearman(x, x * 2)["rho"] - 1) < 1e-9
    assert abs(spearman(x, -x)["rho"] + 1) < 1e-9
    rng = np.random.default_rng(2)
    r = variance_ratio(rng.normal(0, 2, 2000), rng.normal(0, 1, 2000))
    assert 3 < r["ratio"] < 5 and r["lo"] < r["ratio"] < r["hi"]


def test_committed_statements_are_complete():
    s = pd.read_csv(STATEMENTS, keep_default_na=False, parse_dates=["date"])
    assert s.date.is_unique and (s.text.str.len() > 400).all() and set(s.headline_decision) <= {"cut", "hike", "hold"}
    by_year = s[s.date.dt.year.between(2009, 2025)].groupby(s.date.dt.year).size()
    assert (by_year == 8).all(), by_year[by_year != 8]
    assert not s.text.str.contains("Information note|next scheduled date").any()
