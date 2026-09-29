"""Configuration for the Berlin Rerelease Finder."""

import os

LETTERBOXD_USERNAME = os.environ.get("LETTERBOXD_USERNAME")
if not LETTERBOXD_USERNAME:
    raise RuntimeError(
        "Set the LETTERBOXD_USERNAME environment variable to your "
        "Letterboxd username before running."
    )

MOVIES_JSON_URL = "https://ovberlin.online/movies.json"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CINEMA_CACHE_PATH = os.path.join(DATA_DIR, "movies_cache.json")

# A browser-like UA avoids Letterboxd's bot challenge on plain HTML pages
# (their /rss/ endpoint blocks non-browser clients entirely; see CONCEPT.md).
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# Films with year == current_year are ambiguous (we only have year, not a
# real release date), so they're excluded from the "old" filter by default.
# See CONCEPT.md section 4.
MIN_AGE_MONTHS = 6

FUZZY_MATCH_THRESHOLD = 87
