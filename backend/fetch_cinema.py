"""Fetch and cache the Berlin OV/OmU cinema listings.

Source: https://github.com/santistebanc/berlin-cinema (ovberlin.online),
a third-party project that scrapes critic.de + berlin.de, dedupes, and
enriches with TMDb/OMDb metadata. Auto-updates every ~6h. We just consume
its published movies.json (see CONCEPT.md section 2.1).
"""

import json
import os

import requests

from config import CINEMA_CACHE_PATH, DATA_DIR, HTTP_HEADERS, MOVIES_JSON_URL


def fetch_movies():
    """Fetch movies.json from the live source, falling back to the local
    cache if the request fails. Always refreshes the cache on success.

    Returns a list of movie dicts (the "movies" array from the source).
    """
    try:
        resp = requests.get(MOVIES_JSON_URL, headers=HTTP_HEADERS, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        movies = payload["movies"]

        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CINEMA_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return movies

    except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
        print(f"[fetch_cinema] Live fetch failed ({e}), trying local cache...")
        if os.path.exists(CINEMA_CACHE_PATH):
            with open(CINEMA_CACHE_PATH, encoding="utf-8") as f:
                payload = json.load(f)
            print(f"[fetch_cinema] Using cached data from {CINEMA_CACHE_PATH} "
                  f"(scraped at {payload.get('scrapedAt', 'unknown time')}).")
            return payload["movies"]
        raise RuntimeError(
            "Could not fetch live cinema data and no local cache exists."
        ) from e


if __name__ == "__main__":
    movies = fetch_movies()
    print(f"Fetched {len(movies)} films currently showing.")
    for m in movies[:5]:
        print(f"  - {m['title']} ({m['year']})")
