"""Write output/boc-data.js for the interactive chart on the project page: hold-day points and each period's correlation."""
import json

import pandas as pd

from data import OUTPUT
from estimate import spearman

PERIODS = {"2009-2026": ("2009", "2100"), "2009-2017": ("2009", "2018"), "2018-2026": ("2018", "2100"), "2001-2008": ("2001", "2009")}
WINDOWS = {"day": "y2_adj", "before": "y2_before", "after": "y2_after"}


def main():
    e = pd.read_csv(OUTPUT / "events.csv")
    e = e[(e.decision == "hold") & e.dtone.notna() & (e.date < "2026-11-02")]  # the freeze date; newer statements are kept out of this chart
    stats = {}
    for period, (a, b) in PERIODS.items():
        g = e[(e.date >= a) & (e.date < b)]
        stats[period] = {w: {k: round(v, 2) for k, v in spearman(g.dtone, g[col]).items()} for w, col in WINDOWS.items()}
    points = [[d, t, round(x, 3), a, b, c] for d, t, x, a, b, c in zip(e.date, e.title, e.dtone, e.y2_adj.round(1), e.y2_before.round(1), e.y2_after.round(1))]
    points = [[None if v != v else v for v in p] for p in points]
    text = "const BOC = " + json.dumps(dict(points=points, stats=stats), separators=(",", ":"), ensure_ascii=False) + ";\n"
    (OUTPUT / "boc-data.js").write_text(text, encoding="utf-8")
    print(len(text) // 1024, "KB", len(points), "points")


if __name__ == "__main__":
    main()
