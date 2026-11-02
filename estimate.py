"""Text measures and the event study. Writes output/events.csv, tests.csv, maturity.csv, phrases.csv, topics.csv and
results.json. Yield levels are never written, only moves on announcement days and summaries.

Run from the repository folder, after data.py: python estimate.py
"""
import json

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

from data import CA, DATA, OUTPUT, STATEMENTS, TARGET, USDCAD, fed_dates, treasury, valet
from text import LISTS, reading_grade, sentences, tone

MAIN, EARLY = ("2009-01-01", "2100-01-01"), ("2001-01-01", "2008-12-31")
RECENT, SAME_DAY_REPORT, FROZEN = "2018-01-01", "2013-01-01", "2026-11-02"
REPORT_MONTHS = (1, 4, 7, 10)
PHRASES = ["tariff", "quantitative", "balance sheet", "uncertain", "policy rate", "housing", "wage", "commodity", "exchange rate", "geopolitical"]
TFIDF = dict(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)


def spearman(x, y, n=4000):
    """Rank correlation with a 95% bootstrap interval. Pairs with a missing value are dropped."""
    d = pd.DataFrame({"x": x, "y": y}).dropna()
    a, b = d.x.rank().values, d.y.rank().values
    rng = np.random.default_rng(0)
    with np.errstate(all="ignore"):
        draws = [np.corrcoef(a[i], b[i])[0, 1] for i in (rng.integers(0, len(a), len(a)) for _ in range(n))]
    return dict(n=len(a), rho=float(np.corrcoef(a, b)[0, 1]), lo=float(np.nanpercentile(draws, 2.5)), hi=float(np.nanpercentile(draws, 97.5)))


def variance_ratio(event, ordinary, n=4000):
    event, ordinary = np.asarray(event, float), np.asarray(ordinary, float)
    event = event[~np.isnan(event)]
    rng = np.random.default_rng(0)
    draws = [np.var(rng.choice(event, event.size)) / np.var(rng.choice(ordinary, ordinary.size)) for _ in range(n)]
    return dict(n=int(event.size), ratio=float(event.var() / ordinary.var()), lo=float(np.percentile(draws, 2.5)), hi=float(np.percentile(draws, 97.5)),
                median_abs=float(np.median(np.abs(event))), ordinary_median_abs=float(np.median(np.abs(ordinary))))


def r_squared(y, *xs):
    X = np.column_stack([np.ones(len(y)), *xs])
    return float(1 - ((y - X @ np.linalg.lstsq(X, y, rcond=None)[0]) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def adjusted_moves(ca, us, dates, span):
    """Close-to-close moves in basis points and the part not explained by the US move, with beta from days without an announcement."""
    d = pd.concat([ca.rename("ca"), us.rename("us")], axis=1, sort=True).dropna()[span[0]:span[1]].diff().dropna() * 100
    event = d.index.isin(dates)
    fit = np.linalg.lstsq(np.column_stack([np.ones((~event).sum()), d.us[~event]]), d.ca[~event], rcond=None)[0]
    d["res"] = d.ca - fit[0] - fit[1] * d.us
    d["event"] = event
    return d, float(fit[1])


def rate_change(dates):
    """Change in the target from the day before to two business days after, which allows for a next-day start. None before April 2009."""
    t = valet(TARGET)
    t = t.reindex(pd.bdate_range(t.index.min(), t.index.max())).ffill()
    day = pd.tseries.offsets.BDay
    return [float(round((t.asof(x + day(2)) - t.asof(x - day(1))) * 100)) if x - day(1) >= t.index[0] and x <= t.index[-1] else np.nan for x in dates]


def load_events():
    s = pd.read_csv(STATEMENTS, keep_default_na=False, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    s = s[s.date >= EARLY[0]].reset_index(drop=True)
    s["sample"] = np.where(s.date >= MAIN[0], "main", "early")
    s["tone"] = s.text.map(tone)
    s["dtone"] = s.groupby("sample").tone.diff()
    s["words"] = s.text.str.split().str.len()
    s["grade"] = s.text.map(reading_grade)
    s["similarity"] = np.nan
    for _, g in s.groupby("sample"):
        m = TfidfVectorizer(**TFIDF).fit_transform(g.text)
        s.loc[g.index[1:], "similarity"] = [float((m[i] @ m[i - 1].T).toarray()[0, 0]) for i in range(1, m.shape[0])]
    s["novelty"] = 1 - s.similarity
    s["dtarget"] = rate_change(s.date)
    s["decision"] = np.where(s.dtarget.isna(), s.headline_decision, np.where(s.dtarget > 0, "hike", np.where(s.dtarget < 0, "cut", "hold")))
    s["report_month"] = s.date.dt.month.isin(REPORT_MONTHS)
    s["report_same_day"] = s.report_month & (s.date >= SAME_DAY_REPORT)
    s["fed_day"] = s.date.isin(fed_dates())
    return s


def attach_moves(events):
    """Add each maturity's move, and the 2-year move the day before and after, for the sample each event belongs to."""
    us = treasury()
    events = events.copy()
    ordinary, betas, frames = {}, {}, {}
    for sample, span in (("main", MAIN), ("early", EARLY)):
        dates = events.date[events["sample"] == sample]
        for m, series in CA.items():
            d, beta = adjusted_moves(valet(series), us[m], dates, span)
            betas[f"{sample}_{m}"], ordinary[f"{sample}_{m}"], frames[f"{sample}_{m}"] = beta, d.res[~d.event].values, d
            on = events["sample"] == sample
            events.loc[on, f"{m}_raw"] = events.date[on].map(d.ca).values
            events.loc[on, f"{m}_adj"] = events.date[on].map(d.res).values
            if m == "y2":
                position = pd.Series(range(len(d)), index=d.index)
                for label, shift in (("before", -1), ("after", 1)):
                    def at(x, k=shift):
                        i = position.get(x)
                        return np.nan if i is None or not 0 <= i + k < len(d) else d.res.iloc[i + k]
                    events.loc[on, f"y2_{label}"] = events.date[on].map(at).values
    fx = valet(USDCAD)
    def fx_move(x, a, b):
        i = fx.index.searchsorted(x)
        if i >= len(fx) or fx.index[i] != x or i + a < 0 or i + b >= len(fx):
            return np.nan
        return (fx.iloc[i + b] / fx.iloc[i + a] - 1) * 1e4
    events["usdcad_same"] = events.date.map(lambda x: fx_move(x, -1, 0))
    events["usdcad_wide"] = events.date.map(lambda x: fx_move(x, -1, 1))
    return events, ordinary, betas, frames


def day_types(g):
    hold = g.decision == "hold"
    return {"All announcements": g.index, "Hikes": g.index[g.decision == "hike"], "Cuts": g.index[g.decision == "cut"], "Holds": g.index[hold],
            "Holds, report the same day": g.index[hold & g.report_same_day], "Holds, report a day or more later": g.index[hold & g.report_month & ~g.report_same_day],
            "Holds, no report that month": g.index[hold & ~g.report_month]}


def maturity_table(events, ordinary):
    rows = []
    for sample, g in events.groupby("sample"):
        for label, idx in day_types(g).items():
            for m in CA:
                if len(idx) > 1:
                    rows.append(dict(sample=sample, days=label, maturity=m, **variance_ratio(g.loc[idx, f"{m}_adj"], ordinary[f"{sample}_{m}"])))
    return pd.DataFrame(rows)


def correlation_tests(e):
    main, early = e[e["sample"] == "main"], e[e["sample"] == "early"]
    hold, ehold = main[main.decision == "hold"], early[early.decision == "hold"]
    recent = hold[hold.date >= RECENT]
    no_fed = hold[(hold.date >= "2021-01-01") & ~hold.fed_day]
    tests = [("2001-2008", "planned test", "Holds: tone change vs 2-year move", ehold.dtone, ehold.y2_adj),
             ("2001-2008", "planned test", "Holds: tone change vs move the day before (placebo)", ehold.dtone, ehold.y2_before),
             ("2001-2008", "planned test", "Holds: tone change vs move the day after (placebo)", ehold.dtone, ehold.y2_after),
             ("2001-2008", "planned test", "Holds: novelty vs size of move", ehold.novelty, ehold.y2_adj.abs()),
             ("2009-2026", "first look", "Holds: tone change vs 2-year move", hold.dtone, hold.y2_adj),
             ("2009-2026", "first look", "Holds: tone change vs move the day before (placebo)", hold.dtone, hold.y2_before),
             ("2009-2026", "first look", "Holds: tone change vs move the day after (placebo)", hold.dtone, hold.y2_after),
             ("2009-2017", "after seeing results", "Holds: tone change vs 2-year move", hold[hold.date < RECENT].dtone, hold[hold.date < RECENT].y2_adj),
             ("2018-2026", "after seeing results", "Holds: tone change vs 2-year move", recent.dtone, recent.y2_adj),
             ("2018-2026", "after seeing results", "Holds: tone change vs move the day before (placebo)", recent.dtone, recent.y2_before),
             ("2018-2026", "after seeing results", "Holds: tone change vs move the day after (placebo)", recent.dtone, recent.y2_after),
             ("2021-2026", "after seeing results", "Holds without a Fed decision that day: tone change vs 2-year move", no_fed.dtone, no_fed.y2_adj),
             ("2009-2026", "first look", "All decisions: tone change vs 2-year move", main.dtone, main.y2_adj),
             ("2009-2026", "first look", "All decisions: novelty vs size of move", main.novelty, main.y2_adj.abs()),
             ("2017-2026", "first look", "Same-day move in USD/CAD vs 2-year move", main.usdcad_same, main.y2_adj),
             ("2017-2026", "first look", "Two-day move in USD/CAD vs 2-year move", main.usdcad_wide, main.y2_adj)]
    return pd.DataFrame([dict(sample=a, status=b, comparison=c, **spearman(x, y)) for a, b, c, x, y in tests])


def walk_forward(hold, start="2016-01-01"):
    """How well last statements' wording predicts later reactions, against guessing the running average. Only to show overfitting."""
    h = hold.dropna(subset=["y2_adj", "dtone"]).sort_values("date").reset_index(drop=True)
    first = int((h.date < start).sum())
    y = h.y2_adj.values
    mean = np.array([y[:i].mean() for i in range(first, len(h))])
    words = TfidfVectorizer(**TFIDF).fit_transform(h.text)
    sample_fit = Ridge(alpha=0.1).fit(words, y).predict(words)
    model, score = [], []
    for i in range(first, len(h)):
        v = TfidfVectorizer(**TFIDF).fit(h.text[:i])
        model.append(Ridge(alpha=0.1).fit(v.transform(h.text[:i]), y[:i]).predict(v.transform(h.text[i:i + 1]))[0])
        b = np.polyfit(h.dtone[:i], y[:i], 1)
        score.append(np.polyval(b, h.dtone[i]))
    baseline = ((y[first:] - mean) ** 2).sum()
    return dict(n=len(y) - first, words_in_sample=float(1 - ((y - sample_fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
                words_walk_forward=float(1 - ((y[first:] - np.array(model)) ** 2).sum() / baseline),
                tone_walk_forward=float(1 - ((y[first:] - np.array(score)) ** 2).sum() / baseline))


def drop_one(e):
    """Hold-day correlation with each listed term removed in turn, to show how much one word matters."""
    main = e[e["sample"] == "main"]
    out = dict(all=[], recent=[])
    for key, terms in LISTS.items():
        for word in terms:
            lists = {**LISTS, key: [t for t in terms if t != word]}
            d = pd.DataFrame(dict(date=main.date, change=main.text.map(lambda t: tone(t, lists)).diff(), y=main.y2_adj))[main.decision == "hold"].dropna()
            out["all"].append(d.change.corr(d.y, method="spearman"))
            d = d[d.date >= RECENT]
            out["recent"].append(d.change.corr(d.y, method="spearman"))
    return dict(variants=len(out["all"]), all_low=min(out["all"]), all_high=max(out["all"]), recent_low=min(out["recent"]), recent_high=max(out["recent"]))


def phrase_table(main):
    t = main.assign(year=main.date.dt.year, low=main.text.str.lower())
    return pd.DataFrame({p: t.groupby("year").low.apply(lambda x: x.str.contains(rf"\b{p}", regex=True).mean()) for p in PHRASES}).round(3)


def topics(main, k=6):
    """Topic model on sentences up to the date the analysis was fixed, so new statements don't reshuffle it."""
    t = main[main.date < FROZEN]
    rows = [(d.year, s) for d, text in zip(t.date, t.text) for s in sentences(text)]
    v = TfidfVectorizer(stop_words=list(set(TfidfVectorizer(stop_words="english").get_stop_words()) | {"bank", "canada", "per", "cent", "rate", "target", "overnight", "percent"}), min_df=5)
    x = v.fit_transform(s for _, s in rows)
    model = NMF(n_components=k, random_state=0, max_iter=600)
    weights = model.fit_transform(x)
    names = np.array(v.get_feature_names_out())
    labels = [", ".join(names[np.argsort(c)[-3:][::-1]]) for c in model.components_]
    d = pd.DataFrame(weights, columns=labels)
    d = d.div(d.sum(axis=1).replace(0, np.nan), axis=0)
    d["year"] = [y for y, _ in rows]
    return d.groupby("year").mean().round(3)


def survey_check(main):
    """Did the median respondent of the latest Market Participants Survey have the rate right, and how far did the 2-year move?"""
    s = pd.read_csv(DATA / "surveys.csv", parse_dates=["published"])
    target = valet(TARGET)
    rows = []
    for _, e in main[main.date >= s.published.min()].iterrows():
        last = s[(s.published < e.date) & (s.year == e.date.year) & (s.month == e.date.month)].sort_values("published")
        if len(last) and pd.notna(e.dtarget):
            before = target.asof(e.date - pd.tseries.offsets.BDay(1))
            actual = before + e.dtarget / 100
            rows.append(dict(date=e.date, survey_median=last.iloc[-1]["median"], actual=actual, y2_adj=e.y2_adj))
    d = pd.DataFrame(rows)
    d["gap"] = (d.actual - d.survey_median) * 100
    hit, miss = d[d.gap.abs() < 1], d[d.gap.abs() >= 1]
    return dict(meetings=len(d), matched=len(hit), median_abs_move_when_matched=float(hit.y2_adj.abs().median()),
                median_abs_move_when_missed=float(miss.y2_adj.abs().median()), rho_gap_move=spearman(d.gap, d.y2_adj))


def main():
    e, ordinary, betas, frames = attach_moves(load_events())
    m, early = e[e["sample"] == "main"], e[e["sample"] == "early"]
    hold = m[m.decision == "hold"]
    OUTPUT.mkdir(exist_ok=True)
    keep = ["date", "title", "url", "sample", "decision", "dtarget", "report_month", "report_same_day", "fed_day", "tone", "dtone", "similarity", "words", "grade",
            "m3_raw", "y2_raw", "y5_raw", "y10_raw", "y2_adj", "y2_before", "y2_after", "usdcad_same", "usdcad_wide"]
    e[keep].round(3).assign(date=e.date.dt.strftime("%Y-%m-%d")).to_csv(OUTPUT / "events.csv", index=False)
    tests = correlation_tests(e).round(3)
    tests.to_csv(OUTPUT / "tests.csv", index=False)
    maturity = maturity_table(e, ordinary).round(3)
    maturity.to_csv(OUTPUT / "maturity.csv", index=False)
    phrase_table(m).to_csv(OUTPUT / "phrases.csv")
    topics(m).to_csv(OUTPUT / "topics.csv")

    other = frames["main_y2"]
    ordinary_y2 = ordinary["main_y2"]
    limit = float(np.quantile(np.abs(ordinary_y2), 0.9))
    moves = hold.y2_adj.dropna()
    squares = (moves ** 2).sort_values(ascending=False)
    sized = m.dropna(subset=["dtarget", "y2_adj", "m3_adj"])
    fed = m[m.date >= "2021-01-01"]
    late = m[m.date >= "2025-01-01"]
    results = dict(
        statements=dict(main=len(m), early=len(early), first=str(e.date.min().date()), last=str(e.date.max().date()), decisions=m.decision.value_counts().to_dict(),
                        early_decisions=early.decision.value_counts().to_dict(), median_words=m.groupby(m.date.dt.year).words.median().to_dict(),
                        median_grade=m.groupby(m.date.dt.year).grade.median().round(1).to_dict(), median_similarity=m.groupby(m.date.dt.year).similarity.median().round(2).to_dict()),
        us=dict(beta=betas, share_of_variance=float(1 - other.res[~other.event].var() / other.ca[~other.event].var())),
        noise=dict(ordinary_p90=limit, holds_beyond=float((moves.abs() > limit).mean()), n_holds=len(moves), top5_share=float(squares.iloc[:5].sum() / squares.sum()),
                   ordinary_median=float(np.median(np.abs(ordinary_y2))), hold_median=float(moves.abs().median())),
        priced=dict(n=len(sized), decision_r2=r_squared(sized.y2_adj.values, sized.dtarget.values), with_bill_r2=r_squared(sized.y2_adj.values, sized.dtarget.values, sized.m3_adj.values)),
        fed=dict(since_2021=len(fed), same_day_since_2021=int(fed.fed_day.sum()), since_2025=len(late), same_day_since_2025=int(late.fed_day.sum())),
        tone_by_decision=m.groupby("decision").tone.mean().round(2).to_dict(),
        walk_forward=walk_forward(hold),
        drop_one=drop_one(e),
        survey=survey_check(m),
    )
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=1, default=str))
    print(json.dumps(results, indent=1, default=str))
    print(tests.to_string())
    print(maturity[maturity.maturity.isin(["m3", "y2", "y10"]) | (maturity.days == "Holds")].to_string())


if __name__ == "__main__":
    main()
