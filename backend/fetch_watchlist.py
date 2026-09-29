"""Fetch a Letterboxd watchlist by scraping the plain HTML pages.

Note: Letterboxd's /rss/ feed is blocked by a Cloudflare bot challenge for
non-browser clients (confirmed during planning, see CONCEPT.md section 2.2).
The plain watchlist HTML pages work fine with a normal browser User-Agent,
so we scrape those instead, looping through /page/N/ until a page comes
back with no films.
"""

import re

import requests
from bs4 import BeautifulSoup

from config import HTTP_HEADERS, LETTERBOXD_USERNAME

WATCHLIST_URL = "https://letterboxd.com/{username}/watchlist/page/{page}/"

# "Title (Year)" -> ("Title", 1999)
_TITLE_YEAR_RE = re.compile(r"^(.*)\((\d{4})\)$")


def _parse_title_year(full_name):
    match = _TITLE_YEAR_RE.match(full_name.strip())
    if not match:
        return full_name.strip(), None
    title, year = match.groups()
    return title.strip(), int(year)


def fetch_watchlist(username=None, max_pages=50):
    """Scrape all pages of a Letterboxd watchlist.

    Returns a list of dicts: {title, year, slug, url}.
    """
    username = username or LETTERBOXD_USERNAME
    films = []

    for page in range(1, max_pages + 1):
        url = WATCHLIST_URL.format(username=username, page=page)
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        tiles = soup.select("[data-item-name]")

        if not tiles:
            break

        for tile in tiles:
            full_name = tile.get("data-item-name", "")
            title, year = _parse_title_year(full_name)
            slug = tile.get("data-item-slug")
            link = tile.get("data-item-link")
            films.append({
                "title": title,
                "year": year,
                "slug": slug,
                "url": f"https://letterboxd.com{link}" if link else None,
            })

    return films


if __name__ == "__main__":
    films = fetch_watchlist()
    print(f"Fetched {len(films)} films from the watchlist.")
    for f in films[:5]:
        print(f"  - {f['title']} ({f['year']}) [{f['slug']}]")
