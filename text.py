"""Read Bank of Canada rate statements: parse a page, score tone, measure readability, compare two statements."""
import difflib
import html
import re

# Fixed on 2 November 2026 before any yield data were joined. See ANALYSIS_PLAN.md. Do not tune these.
LISTS = dict(
    up=r"rise|rises|rising|rose|increas\w*|higher|strong\w*|firm\w*|above|elevated|robust|pick\w* up|accelerat\w*|upward|upside|persist\w*".split("|"),
    down=r"fall|falls|falling|fell|decreas\w*|lower|weak\w*|soft\w*|below|subdued|moderat\w*|slow\w*|eas\w*|declin\w*|downward|downside|contract\w*".split("|"),
    hot=r"inflation|cpi|prices|wage\w*|growth|gdp|demand|consumption|spending|exports|investment|employment|activity|economy|housing".split("|"),
    slack=r"slack|excess supply|unemployment|uncertaint\w*|output gap".split("|"),  # more of these is dovish
)
NOTE = re.compile(r"Information note|[^.!?]*\bnext scheduled date", re.I)


def strip(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def decode(raw):
    """The Bank's older pages are not all UTF-8."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def parse(page):
    """Date, headline and body of one statement page, with the closing information note removed."""
    title = re.search(r'<h1 class="post-heading">(.*?)</h1>', page, re.S)
    date = re.search(r"post-date'>\s*([A-Z][a-z]+ \d+, \d{4})", page)
    if not title or not date:
        return None
    main = re.search(r"<main.*?</main>", page, re.S)
    main = main.group(0) if main else page
    main = main[main.find("post-date"):]
    full = " ".join(t for t in (strip(p) for p in re.findall(r"<p[ >].*?</p>", main, re.S)) if t)
    cut = NOTE.search(full)
    return dict(title=strip(title.group(1)), date=date.group(1), text=(full[:cut.start()] if cut else full).strip(), note=bool(cut))


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", text) if s.strip()]


def tone(text, lists=LISTS):
    """(hawkish - dovish) / all, counting direction words in sentences about the economy. Runs from -1 to +1."""
    up, down, hot, slack = ("|".join(lists[k]) for k in ("up", "down", "hot", "slack"))
    hawk = dove = 0
    for s in re.split(r"(?<=[.!?])\s+", text.lower()):
        ups, downs = len(re.findall(rf"\b(?:{up})\b", s)), len(re.findall(rf"\b(?:{down})\b", s))
        if re.search(rf"\b(?:{hot})\b", s):
            hawk += ups
            dove += downs
        if re.search(rf"\b(?:{slack})\b", s):
            hawk += downs
            dove += ups
    return (hawk - dove) / max(hawk + dove, 1)


def syllables(word):
    # ponytail: vowel-group count, good enough for a trend in reading level; swap for a dictionary if grades matter
    word = re.sub(r"e$", "", word.lower())
    return max(1, len(re.findall(r"[aeiouy]+", word)))


def reading_grade(text):
    """Flesch-Kincaid grade."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    return 0.39 * len(words) / max(len(sentences(text)), 1) + 11.8 * sum(map(syllables, words)) / max(len(words), 1) - 15.59


def compare(old, new):
    """Each sentence of `new` as [[kind, words], ...] with kind 0 kept, 1 added, plus the old sentences that went away.
    A sentence that mostly survives is shown word by word; one with no close match counts as all new."""
    old_s, new_s = sentences(old), sentences(new)
    left, out = list(old_s), []
    for s in new_s:
        best = max(left, key=lambda o: difflib.SequenceMatcher(None, o.split(), s.split(), autojunk=False).ratio(), default=None)
        score = difflib.SequenceMatcher(None, best.split(), s.split(), autojunk=False).ratio() if best else 0
        if score < 0.5:
            out.append([[1, s]])
            continue
        left.remove(best)
        parts, a, b = [], best.split(), s.split()
        for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if j2 > j1:
                parts.append([0 if tag == "equal" else 1, " ".join(b[j1:j2])])
        out.append(parts)
    return out, left
