"""Draw the static charts from the tables in output/."""
import json
import textwrap

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data import FIGURES, OUTPUT

INK, MUTED, GREY, GRID = "#0b0b0b", "#52514e", "#a8a7a2", "#e6e5e1"
BLUE, ORANGE = "#2a78d6", "#eb6834"
COLOURS = {"hold": GREY, "hike": ORANGE, "cut": BLUE}
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False,
                     "axes.titlelocation": "left", "axes.titlecolor": INK, "axes.titlesize": 11.5})
SOURCE = "Source: Bank of Canada statements and Valet benchmark yields; US Treasury par yields."
NAMES = {"m3": "3-month", "y2": "2-year", "y5": "5-year", "y10": "10-year"}


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 138)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(FIGURES / name, dpi=160, facecolor="white")
    plt.close(fig)


def maturities():
    d = pd.read_csv(OUTPUT / "maturity.csv")
    fig, axes = plt.subplots(1, 3, figsize=(10, 5.6), sharey=True)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.79, bottom=0.2, wspace=0.08)
    panels = [("main", "All announcements", "All announcements, 2009-2026"), ("main", "Holds", "Holds, 2009-2026"), ("early", "Holds", "Holds, 2001-2008 (unseen test)")]
    for ax, (sample, days, title) in zip(axes, panels):
        g = d[(d["sample"] == sample) & (d.days == days)].set_index("maturity").loc[list(NAMES)]
        x = np.arange(4)
        ax.bar(x, g.ratio, color=BLUE, width=0.62)
        ax.errorbar(x, g.ratio, yerr=[g.ratio - g.lo, g.hi - g.ratio], fmt="none", ecolor=INK, capsize=3, lw=1)
        ax.axhline(1, color=MUTED, lw=1, ls="--")
        ax.set_xticks(x, NAMES.values())
        ax.set_title(f"{title}\nn = {g.n.iloc[0]}")
        ax.grid(axis="x", visible=False)
        ax.set_yscale("log")
        ax.set_ylim(0.15, 16)
        ax.set_yticks([0.5, 1, 2, 4, 8, 16], ["0.5", "1", "2", "4", "8", "16"])
        ax.minorticks_off()
    axes[0].set_ylabel("Variance relative to ordinary days")
    save(fig, "maturity.png", "On holds, the 2-year yield moves most", "The same shape appears in 2009-2026 and in the 2001-2008 statements kept back as a test.",
         "Variance of the close-to-close move after removing the US move at the same maturity, relative to days without an announcement. 1 (dashed) means no different from an ordinary day. Lines are 95% bootstrap ranges. " + SOURCE)


def report_days():
    d = pd.read_csv(OUTPUT / "maturity.csv")
    d = d[d.maturity == "y2"]
    rows = [("main", "Holds, no report that month", "2009-2026: no report that month"), ("main", "Holds, report a day or more later", "2009-2012: report came a day or more later"),
            ("main", "Holds, report the same day", "2013-2026: report the same day"),
            ("early", "Holds, no report that month", "2001-2008: no report that month"), ("early", "Holds, report a day or more later", "2001-2008: report came later")]
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.subplots_adjust(left=0.37, right=0.97, top=0.76, bottom=0.25)
    for y, (sample, days, label) in enumerate(rows[::-1]):
        r = d[(d["sample"] == sample) & (d.days == days)].iloc[0]
        ax.plot([r.lo, r.hi], [y, y], color=INK if sample == "main" else GREY, lw=1.4)
        ax.scatter(r.ratio, y, color=BLUE if sample == "main" else GREY, s=70, zorder=3)
        ax.text(r.hi + 0.12, y, f"{r.ratio:.1f}  (n = {r.n})", va="center", color=INK, fontsize=10)
    ax.axvline(1, color=MUTED, lw=1, ls="--")
    ax.set_yticks(range(5), [r[2] for r in rows[::-1]])
    ax.set_xlim(0, 10.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Variance of the 2-year move relative to ordinary days")
    save(fig, "report_days.png", "Which holds move the 2-year yield changes over time", "Since 2009 holds in report months stand out. In 2001-2008, the pattern reverses.",
         "Holds only, after removing the US move. Report months are January, April, July and October. Lines are 95% bootstrap ranges, and with n near 13 they are wide. " + SOURCE)


def priced_in():
    e = pd.read_csv(OUTPUT / "events.csv").dropna(subset=["dtarget", "y2_raw"])
    r = json.loads((OUTPUT / "results.json").read_text())["priced"]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.075, right=0.97, top=0.82, bottom=0.21)
    e["x"] = e.dtarget + np.random.default_rng(0).uniform(-2.5, 2.5, len(e))
    for kind, colour in COLOURS.items():
        g = e[e.decision == kind]
        ax.scatter(g.x, g.y2_raw, s=34, color=colour, edgecolor="white", linewidth=0.6, label=f"{kind.capitalize()} ({len(g)})", zorder=3)
    for date, text, dx, dy in [("2022-10-26", "26 Oct 2022: 50 bp hike,\n2-year falls 28 bp", 8, 3), ("2015-01-21", "21 Jan 2015: 25 bp cut,\n2-year falls 29 bp", 8, 3), ("2023-06-07", "7 Jun 2023: 25 bp hike,\n2-year rises 22 bp", 8, 0), ("2026-10-28", "28 Oct 2026: 25 bp hike,\n2-year rises 5 bp", 30, 13)]:
        p = e[e.date == date].iloc[0]
        ax.annotate(text, (p.x, p.y2_raw), xytext=(p.x + dx, p.y2_raw + dy), fontsize=9.5, color=INK, va="center", arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkB=3))
    ax.axhline(0, color=MUTED, lw=1)
    ax.axvline(0, color=MUTED, lw=1)
    ax.set_xlabel("Change in the policy rate (bp), spread out slightly so points don't overlap")
    ax.set_ylabel("2-year yield move on the day (bp)")
    ax.legend(loc="upper left", ncol=3)
    save(fig, "priced_in.png", "The size of a decision says little about the market's reaction", f"The size of the decision explains {r['decision_r2']:.0%} of the 2-year move, after removing the US move.",
         "Each point is a scheduled decision since April 2009. The move in the 3-month bill on the day raises the share explained to " + f"{r['with_bill_r2']:.0%}, which suggests surprise matters more than size, though both respond to the same news. " + SOURCE)


def wording():
    e = pd.read_csv(OUTPUT / "events.csv")
    t = pd.read_csv(OUTPUT / "tests.csv")
    hold = e[e.decision == "hold"]
    main, early = hold[hold["sample"] == "main"], hold[hold["sample"] == "early"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 5.6), sharey=True, sharex=True)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.75, bottom=0.2, wspace=0.08)
    def stat(sample, words):
        r = t[(t["sample"] == sample) & (t.comparison == words)].iloc[0]
        return f"{r.rho:+.2f} ({r.lo:+.2f} to {r.hi:+.2f}), n = {r.n}".replace("-", "−")
    panels = [(main, "y2_adj", "2009-2026, on the day", stat("2009-2026", "Holds: tone change vs 2-year move")),
              (main, "y2_before", "2009-2026, the day before (placebo)", stat("2009-2026", "Holds: tone change vs move the day before (placebo)")),
              (early, "y2_adj", "2001-2008, on the day (unseen test)", stat("2001-2008", "Holds: tone change vs 2-year move"))]
    for ax, (g, col, title, note) in zip(axes, panels):
        ax.scatter(g.dtone, g[col], s=26, color=BLUE, edgecolor="white", linewidth=0.5)
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.axvline(0, color=MUTED, lw=0.8)
        ax.set_title(f"{title}\n{note}", fontsize=9.5)
        ax.set_xlabel("Change in tone score")
    axes[0].set_ylabel("2-year move after removing the US move (bp)")
    save(fig, "wording.png", "Wording lines up with yields only loosely", "No test clears the bar set in advance. The unseen 2001-2008 test comes close, on just 29 holds.",
         "Holds only. Higher tone means more words about rising prices and activity. Numbers are Spearman rank correlations with 95% bootstrap ranges. The score is a fixed word list, not a validated measure. " + SOURCE)


def phrases():
    p = pd.read_csv(OUTPUT / "phrases.csv", index_col=0)
    order = ["tariff", "quantitative", "balance sheet", "geopolitical", "uncertain", "policy rate", "housing", "wage", "commodity", "exchange rate"]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.135, right=0.97, top=0.82, bottom=0.17)
    ramp = matplotlib.colors.LinearSegmentedColormap.from_list("blue", ["#ffffff", "#8fb8e8", "#2a78d6", "#123b70"])
    ax.imshow(p[order].T.values, aspect="auto", cmap=ramp, vmin=0, vmax=1)
    ax.set_xticks(range(len(p)), [str(y)[2:] if i else str(y) for i, y in enumerate(p.index)])
    ax.set_yticks(range(len(order)), order)
    ax.grid(False)
    ax.tick_params(length=0)
    ax.set_xticks(np.arange(-.5, len(p)), minor=True)
    ax.set_yticks(np.arange(-.5, len(order)), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    save(fig, "phrases.png", "What the Bank talks about changes with events", "Share of each year's statements using a phrase. Quantitative easing and tightening fill 2021-2023, and tariffs fill 2025-2026.",
         "Darker means more of the year's statements, from none (white) to all (darkest). Words are matched by their start, so 'wage' includes 'wages'. 2026 has seven statements so far. Source: Bank of Canada statements.")


def length():
    r = json.loads((OUTPUT / "results.json").read_text())["statements"]
    panels = [("median_words", "Words"), ("median_grade", "Reading grade (Flesch-Kincaid)"), ("median_similarity", "Similarity to last statement")]
    fig, axes = plt.subplots(1, 3, figsize=(10, 4.4))
    fig.subplots_adjust(left=0.05, right=0.985, top=0.74, bottom=0.2, wspace=0.2)
    for ax, (key, title) in zip(axes, panels):
        s = pd.Series({int(k): v for k, v in r[key].items()}).sort_index()
        ax.plot(s.index, s.values, color=BLUE, lw=2)
        ax.scatter(s.index[[0, -1]], s.values[[0, -1]], color=BLUE, s=36, zorder=3)
        ax.set_title(title)
        ax.set_ylim(0, s.max() * 1.2)
        ax.set_xticks([2010, 2018, 2026])
        ax.grid(axis="x", visible=False)
    save(fig, "language.png", "Statements got longer and easier to read", "Medians by year, for scheduled statements since 2009.",
         "Similarity is cosine similarity on word and two-word counts weighted by rarity (TF-IDF). Source: Bank of Canada statements.")


def topics():
    t = pd.read_csv(OUTPUT / "topics.csv", index_col=0)
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.6), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.79, bottom=0.17, hspace=0.32, wspace=0.08)
    for ax, column in zip(axes.flat, t.columns):
        ax.plot(t.index, t[column] * 100, color=BLUE, lw=2)
        ax.set_title(column, fontsize=10)
        ax.set_xticks([2010, 2018, 2026])
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, 45)
    for ax in axes[:, 0]:
        ax.set_ylabel("Share (%)")
    save(fig, "topics.png", "Inflation took up more space after 2021", "Six themes the model found in the statements' sentences, named by their three strongest words.",
         "Non-negative matrix factorisation on TF-IDF of every sentence, 2009 to October 2026. Average share of each sentence by year. The model picks the themes; the 'held, deposit' theme is standard wording about the rate corridor. Source: Bank of Canada statements.")


def main():
    FIGURES.mkdir(exist_ok=True)
    for draw in (maturities, report_days, priced_in, wording, phrases, length, topics):
        draw()


if __name__ == "__main__":
    main()
