"""The README says it lists every row of output/tests.csv, in groups by status. Hold it to that."""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
ROW = re.compile(r"^\| ([\d-]+) \| (.+?) \| ([+−][\d.]+) \(([+−][\d.]+) to ([+−][\d.]+)\) \| (\d+) \|$")
GROUPS = {"Planned test": "planned test", "First look": "first look", "After seeing results": "after seeing results"}


def number(text):
    return float(text.replace("−", "-"))


def listed():
    """(sample, comparison) -> status and numbers, for each table row in the section on wording."""
    section = (ROOT / "README.md").read_text(encoding="utf-8").split("### 4.")[1].split("## Why daily data")[0]
    rows, status = {}, None
    for line in section.splitlines():
        heading = next((s for g, s in GROUPS.items() if line.startswith(f"**{g}:")), None)
        status = heading or status
        m = ROW.match(line.replace("**", ""))
        if m:
            rows[m[1], m[2]] = (status, number(m[3]), number(m[4]), number(m[5]), int(m[6]))
    return rows


def test_first_median_word_count_matches_the_results():
    words = json.loads((ROOT / "output" / "results.json").read_text())["statements"]["median_words"]["2009"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"{words} median words" in readme
    assert f"a median of {words} words in 2009" in readme


def test_every_row_is_listed_under_its_status_with_its_numbers():
    tests, rows = pd.read_csv(ROOT / "output" / "tests.csv"), listed()
    assert len(rows) == len(tests)
    for t in tests.itertuples():
        status, rho, lo, hi, n = rows[t.sample, t.comparison]
        assert status == t.status, t.comparison
        assert n == t.n, t.comparison
        for shown, value in ((rho, t.rho), (lo, t.lo), (hi, t.hi)):
            assert abs(shown - value) <= .0051, t.comparison  # the README has two decimals, from the unrounded value
