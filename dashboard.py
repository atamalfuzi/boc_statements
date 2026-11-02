"""Statement explorer: every scheduled statement since 2001 compared with the one before, beside the 2-year yield's move
that day. It shows no tone score and no estimate of the next decision. Writes a static site to site/.

Run from the repository folder, after data.py and estimate.py: python dashboard.py
"""
import datetime as dt
import html
import json
import shutil

import numpy as np
import pandas as pd

from data import OUTPUT, ROOT, SITE, STATEMENTS
from text import compare


def problems(events, statements):
    """Reasons not to publish. The live page stays up if any of these is true."""
    found = []
    if len(events) != len(statements):
        found.append(f"{len(events)} events for {len(statements)} statements")
    if statements.date.duplicated().any():
        found.append("duplicate statement dates")
    if (statements.text.str.len() < 400).any():
        found.append("a statement shorter than 400 characters")
    per_year = pd.to_datetime(statements.date).dt.year.value_counts()
    if (per_year > 9).any():
        found.append(f"too many statements in a year: {per_year[per_year > 9].to_dict()}")
    recent = events[events.date < (pd.Timestamp.today() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")]
    if recent.y2_adj.isna().sum() > 2:  # 5 December 2018 has no US yield; allow one more market holiday
        found.append(f"{int(recent.y2_adj.isna().sum())} statements older than a month have no yield move")
    if set(events.decision) - {"hold", "hike", "cut"}:
        found.append("an unknown decision")
    return found


def records(events, statements):
    text = dict(zip(statements.date, statements.text))
    rows, previous = [], None
    for _, e in events.sort_values("date").iterrows():
        current = text[e.date]
        parts, lost = compare(previous, current) if previous else ([[[0, s]] for s in [current]], [])
        rows.append(dict(date=e.date, title=e.title, url=e.url, decision=e.decision, change=None if pd.isna(e.dtarget) else int(e.dtarget),
                         move=None if pd.isna(e.y2_adj) else float(e.y2_adj), raw=None if pd.isna(e.y2_raw) else float(e.y2_raw),
                         fed=bool(e.fed_day), report=bool(e.report_same_day), parts=parts, lost=lost))
        previous = current
    return rows


def page(updated, count, first, last):
    def e(x):
        return html.escape(str(x))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'self'; form-action 'none'" />
  <title>Bank of Canada statement explorer | Ata Malfuzi</title>
  <meta name="description" content="Every scheduled Bank of Canada rate statement since 2001, compared sentence by sentence with the one before, beside the 2-year yield's move that day." />
  <link rel="canonical" href="https://atamalfuzi.github.io/boc_statements/" />
  <link rel="stylesheet" href="style.css" />
</head>
<body>
<main class="wrap">
  <p><a href="https://atamalfuzi.github.io/bank-of-canada-statements.html">Back to the project page</a></p>
  <h1>Bank of Canada statement explorer</h1>
  <p class="lead">Pick any scheduled rate statement since 2001 to see what changed from the one before and how far the 2-year yield moved that day.</p>
  <p class="notes">{e(count)} statements, {e(first)} to {e(last)}. Rebuilt weekly; last built {e(updated)}. Personal project: my own analysis of publicly available data. It is not associated with my work for any current or past employer and does not represent their views. This describes communication and markets. It is not investment advice and gives no trading signals.</p>

  <section aria-labelledby="timeline-title">
    <h2 id="timeline-title">The 2-year yield on each announcement day</h2>
    <ul class="key" aria-label="Decision colours">
      <li><span class="swatch swatch-hold"></span>Hold</li>
      <li><span class="swatch swatch-hike"></span>Hike</li>
      <li><span class="swatch swatch-cut"></span>Cut</li>
      <li><span class="swatch swatch-band"></span>Ordinary-day range</li>
    </ul>
    <canvas id="timeline" role="img" aria-label="Bars for each statement since 2001 showing the 2-year yield's move in basis points that day, coloured by decision. Use the list below to choose a statement."></canvas>
    <p class="hint">Hover or tap a bar. The move leaves out the part explained by the US 2-year yield that day. The band holds 90% of days without an announcement in 2009-2026.</p>
    <div class="controls">
      <button type="button" id="previous">Earlier</button>
      <label for="choose">Statement</label>
      <select id="choose"></select>
      <button type="button" id="next">Later</button>
    </div>
  </section>

  <section aria-live="polite">
    <h2 id="title"></h2>
    <p class="facts" id="facts"></p>
    <p class="flag" id="flag" hidden></p>
    <p class="hint"><span class="added">Highlighted and underlined</span> words are new since the previous statement.</p>
    <div id="body"></div>
    <div id="lost-block" hidden>
      <h3>Sentences no longer there</h3>
      <ul id="lost"></ul>
    </div>
    <p><a id="source" target="_blank" rel="noopener">The statement on the Bank of Canada's site</a></p>
  </section>

  <section class="notes">
    <h2>How to read this</h2>
    <p>Daily data can't tie one move to one statement. A close-to-close window also holds the Monetary Policy Report, press conferences, data releases and sometimes a Fed decision. <a href="https://atamalfuzi.github.io/bank-of-canada-statements.html">The write-up</a> says what can and can't be concluded.</p>
    <p>Statements from the Bank of Canada, with page formatting and the closing information note removed and the comparison added; reused under the Bank's terms, which do not imply its endorsement. Yield moves are derived from the Bank of Canada's Valet service (sources: CanDeal Data and Analytics and the Bank of Canada) and US Treasury par yields. Unscheduled moves such as March 2020 are not included. <a href="https://github.com/atamalfuzi/boc_statements" target="_blank" rel="noopener">Code on GitHub</a>.</p>
  </section>
</main>
<script src="data.js"></script>
<script src="explorer.js"></script>
</body>
</html>
"""


def main():
    events = pd.read_csv(OUTPUT / "events.csv")
    statements = pd.read_csv(STATEMENTS, keep_default_na=False)
    statements = statements[statements.date >= "2001-01-01"]
    found = problems(events, statements)
    if found:
        raise SystemExit("Not publishing: " + "; ".join(found))
    band = json.loads((OUTPUT / "results.json").read_text())["noise"]["ordinary_p90"]
    SITE.mkdir(exist_ok=True)
    data = json.dumps(dict(band=round(band, 1), statements=records(events, statements)), separators=(",", ":"), ensure_ascii=False)
    (SITE / "data.js").write_text(f"const STATEMENTS = {data};\n", encoding="utf-8")
    for name in ("explorer.js", "style.css"):
        shutil.copy(ROOT / "explorer" / name, SITE / name)
    today = dt.date.today()
    span = pd.to_datetime(events.date)
    (SITE / "index.html").write_text(page(f"{today.day} {today:%B %Y}", len(events), f"{span.min():%B %Y}", f"{span.max():%B %Y}"), encoding="utf-8")
    print("site written:", len(events), "statements,", (SITE / "data.js").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
