"""Filter cinema listings to "old" films and match them against a watchlist.

See CONCEPT.md sections 3 and 4 for the reasoning behind the approach here.
"""

import re
from datetime import date

from rapidfuzz import fuzz

from config import FUZZY_MATCH_THRESHOLD, MIN_AGE_MONTHS

_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(title):
    """Lowercase, strip punctuation, strip a leading article, collapse
    whitespace. Used purely for matching, never for display."""
    if not title:
        return ""
    t = title.lower()
    t = _PUNCT_RE.sub("", t)
    t = _ARTICLE_RE.sub("", t)
    t = _WHITESPACE_RE.sub(" ", t).strip()
    return t


def filter_old_films(movies, today=None):
    """Keep films old enough to unambiguously satisfy MIN_AGE_MONTHS.

    We only have year-granularity release data, not exact dates, so we use
    a conservative rule: keep a film only if its release year ended more
    than MIN_AGE_MONTHS ago (i.e. `year + 1` is fully in the past relative
    to `today - MIN_AGE_MONTHS`). This can under-include early-in-the-year
    releases from last year for the first few months, but it never
    over-includes an actually-recent film, which is the safer failure mode
    for this use case. A film released in the *current* year is always
    excluded, since it can't be provably old by this rule. See CONCEPT.md
    section 4 for the reasoning and the planned v2 upgrade (per-title TMDb
    lookup to resolve these edge cases precisely).
    """
    today = today or date.today()
    cutoff_year = today.year - 1
    if today.month <= MIN_AGE_MONTHS:
        cutoff_year -= 1
    return [m for m in movies if m.get("year") is not None and m["year"] <= cutoff_year]


def _title_candidates(movie):
    """All title strings worth trying to match against, for a cinema
    listing entry."""
    candidates = [movie.get("title"), movie.get("originalTitle")]
    candidates.extend(movie.get("alternativeTitles") or [])
    return [normalize_title(c) for c in candidates if c]


def find_matches(cinema_movies, watchlist_films):
    """Fuzzy-match old cinema listings against the watchlist.

    Returns a list of dicts: {cinema_movie, watchlist_film, score}.
    """
    watchlist_normalized = [
        (normalize_title(f["title"]), f) for f in watchlist_films
    ]

    matches = []
    for movie in cinema_movies:
        candidates = _title_candidates(movie)
        if not candidates:
            continue

        best_score = 0
        best_watchlist_film = None

        for wl_title_norm, wl_film in watchlist_normalized:
            if not wl_title_norm:
                continue
            for cand in candidates:
                score = fuzz.token_sort_ratio(cand, wl_title_norm)

                # Year as tiebreaker: nudge score up on exact year match,
                # down on a clear mismatch, when both years are known.
                if movie.get("year") and wl_film.get("year"):
                    if movie["year"] == wl_film["year"]:
                        score += 3
                    elif abs(movie["year"] - wl_film["year"]) > 1:
                        score -= 10

                if score > best_score:
                    best_score = score
                    best_watchlist_film = wl_film

        if best_score >= FUZZY_MATCH_THRESHOLD and best_watchlist_film:
            matches.append({
                "cinema_movie": movie,
                "watchlist_film": best_watchlist_film,
                "score": round(best_score, 1),
            })

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches


if __name__ == "__main__":
    from fetch_cinema import fetch_movies
    from fetch_watchlist import fetch_watchlist

    movies = fetch_movies()
    old_movies = filter_old_films(movies)
    print(f"{len(movies)} films showing, {len(old_movies)} are old enough (pre-{date.today().year}).")

    watchlist = fetch_watchlist()
    print(f"{len(watchlist)} films on watchlist.")

    matches = find_matches(old_movies, watchlist)
    print(f"\n{len(matches)} matches:\n")
    for m in matches:
        cm = m["cinema_movie"]
        wf = m["watchlist_film"]
        cinemas = ", ".join(sorted({c["name"] for c in cm.get("cinemas", [])}))
        print(f"  [{m['score']}] {cm['title']} ({cm['year']}) <-> {wf['title']} ({wf['year']})")
        print(f"        playing at: {cinemas}")
