# Analysis plan

Committed before the 2001-2008 statements are scored against yields. The git history shows the order.

## What was already seen

A first look on 2 November 2026 used every scheduled statement from 2009 to October 2026. Its results shaped the questions, so they can't confirm themselves. In particular, the lead that wording tracks the 2-year yield from 2018 onward came from splitting the sample after seeing the full result.

For 2001-2008, I read the format of a few pages. I have not compared any of those statements with yields.

## What is fixed

- **Tone score:** the word lists in `text.py`, unchanged from the first look, computed on each statement's body without the closing information note.
- **Measure:** change in tone from the previous statement, against the 2-year yield's close-to-close move on the announcement day, less the part explained by the same day's US 2-year move. The US beta comes from days without an announcement in the same sample.
- **Statistic:** Spearman rank correlation with a 95% bootstrap interval, seed 0.
- **Sample:** scheduled decisions only.

## Tests on 2001-2008

1. Holds: tone change against the yield move on the day.
2. Holds: the same against the day before and the day after, as placebos.
3. Holds: novelty (one minus similarity to the previous statement) against the size of the move.
4. Variance on announcement days relative to ordinary days, by maturity (3-month, 2, 5, 10-year), for all announcements and for holds.
5. Holds in report months (January, April, July, October) against other holds. The report came out after the statement in those years, so this asks whether the quarterly statement matters without the report on the same day.

## How the results will be read

- Test 1 supports the wording idea only if the interval excludes zero with a positive sign and the placebos in test 2 are clearly smaller.
- The 2018-2026 lead stays a lead. Only statements after 2 November 2026 can test it, at eight a year.
- Every comparison goes in `output/tests.csv`, whatever it shows.
- A sentence classifier would need labels from someone other than the author of the test, so it is left out. The TF-IDF model is reported only to show the size of the overfitting problem.
- The project describes communication and markets. It gives no trading signals, no forecasts of decisions and no verdict on whether policy was right.
