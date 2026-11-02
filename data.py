"""Download the statements and market data.

statements/statements.csv is committed, so a rerun only fetches statements it doesn't have. The Bank's terms allow reuse
with attribution and a note of changes; the only change here is removing page formatting and the closing information
note. Market data stay in data/, which is not committed.

Run from the repository folder: python data.py
"""
from pathlib import Path
import datetime as dt
import re
import time
import urllib.request

import pandas as pd

from text import decode, parse, strip

ROOT = Path(__file__).parent
DATA, OUTPUT, FIGURES, SITE = ROOT / "data", ROOT / "output", ROOT / "figures", ROOT / "site"
STATEMENTS = ROOT / "statements" / "statements.csv"
BANK = "https://www.bankofcanada.ca"
AGENT = "Mozilla/5.0 (compatible; boc_statements research; +https://github.com/atamalfuzi/boc_statements)"
PAUSE = 2  # seconds between requests to one site

CA = dict(m3="TB.CDN.90D.MID", y2="BD.CDN.2YR.DQ.YLD", y5="BD.CDN.5YR.DQ.YLD", y10="BD.CDN.10YR.DQ.YLD")
US = dict(m3="3 Mo", y2="2 Yr", y5="5 Yr", y10="10 Yr")
TARGET, USDCAD = "V39079", "FXUSDCAD"
FIRST_YIELD = 2001
OFF_PATTERN = ["/2010/03/maintains-overnight-rate-target-reiterates-conditional-commitment-2/"]
EARLY_SLUG = re.compile(r"/(200[1-8])/\d\d/[^/]*(overnight|bank-rate|policy-interest|key-policy|keeps|lowers|raises|maintains|target)")
EARLY_NOT = re.compile(r"debt|consult|inflation|coordinated|statement|speech|minimum|spread|control|release-dates|schedule", re.I)
# Unscheduled moves are left out: they happened outside the fixed calendar and for reasons a calendar study can't compare.
UNSCHEDULED = {"2001-09-17", "2008-10-08", "2020-03-13", "2020-03-16", "2020-03-27"}
VERB = re.compile(r"\b(lower|lowers|lowered|cuts|reduces|raises|raised|increases|keeps|maintains|holds|leaves|hold|maintain|keep)\b", re.I)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def cached(name, url):
    path = DATA / name
    if not path.exists():
        DATA.mkdir(exist_ok=True)
        path.write_bytes(fetch(url))
        time.sleep(PAUSE)
    return path


def statement_urls():
    index = fetch(f"{BANK}/wp-sitemap.xml").decode()
    urls = []
    for part in re.findall(r"<loc>([^<]*wp-sitemap-posts-post-\d+\.xml)</loc>", index):
        urls += re.findall(r"<loc>([^<]+)</loc>", fetch(part).decode())
        time.sleep(PAUSE)
    keep = [u for u in urls if "fad-press-release" in u or any(u.endswith(o) for o in OFF_PATTERN)]
    keep += [u for u in urls if EARLY_SLUG.search(u) and not EARLY_NOT.search(u)]
    return sorted(set(keep))


def decision_word(title):
    """cut, hike or hold from a headline, or None for a page that isn't a rate decision."""
    m = VERB.search(title)
    if not m or not re.search(r"rate|target", title, re.I):
        return None
    word = m.group(1).lower()
    return "cut" if word in ("lower", "lowers", "lowered", "cuts", "reduces") else "hike" if word in ("raises", "raised", "increases") else "hold"


def update_statements():
    have = pd.read_csv(STATEMENTS, keep_default_na=False) if STATEMENTS.exists() else pd.DataFrame(columns=["date", "url", "title", "headline_decision", "text"])
    seen, rows = set(have.url), []
    for url in statement_urls():
        if url in seen:
            continue
        page = parse(decode(fetch(url)))
        time.sleep(PAUSE)
        if not page:
            print("no statement found at", url)
            continue
        date = pd.Timestamp(page["date"]).strftime("%Y-%m-%d")
        word = decision_word(page["title"])
        if date in UNSCHEDULED or word is None or len(page["text"]) < 400:
            print("skipped", date, page["title"][:80])
            continue
        rows.append(dict(date=date, url=url, title=page["title"], headline_decision=word, text=page["text"]))
    if rows:
        have = pd.concat([have, pd.DataFrame(rows)]).sort_values("date").drop_duplicates("date", keep="first")
        have.to_csv(STATEMENTS, index=False)
    print(len(rows), "new statements;", len(have), "in all, to", have.date.max())
    return have


def valet(series):
    return read_valet(cached(f"{series}.csv", f"{BANK}/valet/observations/{series}/csv").read_bytes().decode("utf-8-sig"), series)


def read_valet(body, series):
    lines = body.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('"date"'))
    rows = (line.replace('"', "").split(",") for line in lines[start + 1:] if line.strip())
    values = {pd.Timestamp(r[0]): float(r[1]) for r in rows if len(r) > 1 and re.fullmatch(r"-?[\d.]+", r[1])}
    return pd.Series(values, name=series).sort_index()


def treasury():
    """US par yields, one file a year, from the US Treasury."""
    frames = []
    for year in range(FIRST_YIELD, dt.date.today().year + 1):
        url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all"
               f"?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")
        frames.append(pd.read_csv(cached(f"treasury_{year}.csv", url)))
    d = pd.concat(frames)
    d.index = pd.to_datetime(d.Date, format="%m/%d/%Y")
    return d.sort_index()[list(US.values())].rename(columns={v: k for k, v in US.items()})


def read_fed(page):
    """Fed decision dates from its calendar or a historical page: the last day of each scheduled meeting."""
    dates = []
    for block in re.split(r'class="panel-heading"', page)[1:]:
        year = re.search(r"(20\d\d) FOMC Meetings", block)
        if not year:
            continue
        for month, days in re.findall(r"fomc-meeting__month[^>]*><strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<", block, re.S):
            n = re.findall(r"\d+", days)
            if n and "notation" not in days.lower():
                dates.append(pd.Timestamp(f"{month.split('/')[-1]} {n[-1]} {year.group(1)}"))
    for month, days, year in re.findall(r">\s*([A-Z][a-z]+(?:/[A-Z][a-z]+)?) ([\d-]+)(?: \(\w+\))? Meeting - (\d{4})\s*<", page):
        dates.append(pd.Timestamp(f"{month.split('/')[-1]} {days.split('-')[-1]} {year}"))
    return dates


def fed_dates():
    dates = read_fed(decode(cached("fed_calendar.html", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm").read_bytes()))
    for year in range(FIRST_YIELD, 2021):
        dates += read_fed(decode(cached(f"fed_{year}.html", f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm").read_bytes()))
    return pd.DatetimeIndex(sorted(set(dates)))


MONTHS = "January February March April May June July August September October November December".split()


def read_survey(page):
    """Median expected policy rate by meeting month from one Market Participants Survey, with the page's date."""
    date = pd.Timestamp(re.search(r"post-date'>\s*([A-Z][a-z]+ \d+, \d{4})", page).group(1))
    for table in re.findall(r"<table.*?</table>", page, re.S):
        rows = [[strip(c) for c in re.findall(r"<t[dh].*?</t[dh]>", r, re.S)] for r in re.findall(r"<tr.*?</tr>", table, re.S)]
        if len(rows) > 2 and rows[0] and "Policy interest rate" in " ".join(rows[0]) and rows[1][0].isdigit():
            year, previous, out = int(rows[1][0]), 0, []
            for row in rows[2:]:
                if row[0] not in MONTHS:
                    break  # quarterly rows further out are not meetings
                month = MONTHS.index(row[0]) + 1
                year += month < previous
                previous = month
                out.append(dict(published=date, year=year, month=month, median=float(row[2])))
            return out
    return []


def surveys():
    """Every Market Participants Survey in the Bank's sitemap. Tables that don't match the usual layout are skipped."""
    index = fetch(f"{BANK}/wp-sitemap.xml").decode()
    urls = []
    for part in re.findall(r"<loc>([^<]*wp-sitemap-posts-post-\d+\.xml)</loc>", index):
        urls += re.findall(r"<loc>([^<]*market-participants-survey-[a-z]+-quarter[^<]*)</loc>", fetch(part).decode())
        time.sleep(PAUSE)
    rows = []
    for url in sorted(set(urls)):
        rows += read_survey(decode(cached("survey_" + url.rstrip("/").split("/")[-1][-28:] + ".html", url).read_bytes()))
    return pd.DataFrame(rows)


def main():
    update_statements()
    for series in [*CA.values(), TARGET, USDCAD]:
        valet(series)
    treasury()
    print(len(fed_dates()), "Fed dates")
    survey = surveys()
    DATA.mkdir(exist_ok=True)
    survey.to_csv(DATA / "surveys.csv", index=False)
    print(survey.published.nunique() if len(survey) else 0, "surveys")


if __name__ == "__main__":
    main()
