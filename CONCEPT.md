# Berlin Rerelease Finder — Concept & Build Plan

## 1. Problem

Berlin cinemas (mostly the arthouse/OV circuit) regularly screen films that
aren't new releases — rereleases, retrospectives, original-language runs of
older titles. There's no easy way to see which of those overlap with a
personal Letterboxd watchlist. This project closes that gap:

> Show me: films playing in Berlin right now that are **older than 6 months**
> AND **on my Letterboxd watchlist**.

Local tool, single user, run on demand. Not a deployed product.

## 2. Data sources

### 2.1 Cinema listings — `berlin-cinema` / OV Berlin

- Upstream project: https://github.com/santistebanc/berlin-cinema
- Live site: https://ovberlin.online
- Data file: `public/movies.json`, hosted on GitHub Pages, **auto-regenerated
  every 6 hours** via GitHub Actions (scrape critic.de + berlin.de → merge/
  dedupe → enrich with TMDb + OMDb → publish JSON).
- Scope: **OV/OmU (original-version / subtitled) screenings only** — this is
  a feature, not a limitation, since it's presumably the language format you
  actually want anyway.
- We do **not** scrape anything ourselves. We just fetch and consume this
  JSON. This eliminates the scraping + TMDb-enrichment work entirely.

**Confirmed schema** (root object, `movies` key holding an array):

```json
{
  "movies": [
    {
      "title": "Gentle Monster",
      "director": "Marie Kreutzer",
      "cast": ["Léa Seydoux", "..."],
      "year": 2026,
      "posterUrl": "https://image.tmdb.org/...",
      "url": "https://www.critic.de/...",
      "variants": ["OmeU", "OmenglU"],
      "cinemas": [
        { "name": "B-Ware Ladenkino", "address": "...", "websiteUrl": "..." }
      ],
      "showings": {
        "2026-09-21": {
          "17:20": [
            { "cinema": "Passage Kinos", "variants": ["OmeU"] }
          ]
        }
      },
      "originalTitle": "Gentle Monster",
      "alternativeTitles": ["..."],
      "plot": "...",
      "runtime": 114,
      "genres": ["Drama"],
      "imdbRating": 5.5,
      "imdbId": "tt37020296",
      "ageRating": "16",
      "slug": "gentle-monster"
    }
  ]
}
```

Fields we actually need: `title`, `originalTitle`, `alternativeTitles`,
`year`, `showings`, `imdbId`, `posterUrl`, `slug`/`url`.

**Known limitation:** `year` is year-granularity only, not a full release
date. "Older than 6 months" therefore can't be computed exactly from this
field alone — see §4 for how we handle it.

### 2.2 Watchlist — Letterboxd, scraped HTML (not RSS)

**Verified against your actual account** (`svenelyes`), 2026-09-22.

- **RSS is not usable.** `https://letterboxd.com/svenelyes/watchlist/rss/`
  returns HTTP 403 from any non-browser client — it's sitting behind a
  Cloudflare bot challenge ("Just a moment..." JS challenge page), not a
  normal auth wall. This held for both the WebFetch tool and a plain `curl`
  with a spoofed browser user agent. Plan §2.2 in the original doc assumed
  RSS would just work; it doesn't, at least not without a headless
  browser/Cloudflare-solving layer, which is overkill for this project.
- **The plain watchlist HTML page works fine**, same user agent, no
  challenge: `https://letterboxd.com/svenelyes/watchlist/` returns HTTP 200
  with the full page server-rendered, no JS execution needed.
- Each film on the page is a poster tile with a
  `data-item-name="Title (Year)"` attribute directly on it — clean,
  structured, no parsing tricks needed beyond splitting the trailing
  `(YYYY)` off the title. Example real entries pulled from your watchlist:
  `"In the Mood for Love (2000)"`, `"Being John Malkovich (1999)"`,
  `"After Hours (1985)"`, `"Close Encounters of the Third Kind (1977)"`.
- **Pagination confirmed:** the page shows 28 films per page, and pagination
  links go at least up to `page/9` — your watchlist is a few hundred films,
  spread across ~9 pages. The scraper needs to loop
  `https://letterboxd.com/svenelyes/watchlist/page/N/` until a page returns
  no film tiles, not just fetch page 1.

**Revised approach:** scrape the HTML watchlist pages directly (plain
`requests` + a simple attribute grep or `BeautifulSoup`), not RSS. Use a
normal browser-like `User-Agent` header — that alone was sufficient to avoid
the Cloudflare challenge on the plain HTML page (only `/rss/` triggered it
in testing). If Letterboxd ever starts challenging the HTML page too, this
becomes the one part of the project that could need a heavier tool
(`playwright`/`selenium`); not needed today.

## 3. Matching logic

1. Normalize both sides' titles: lowercase, strip punctuation, strip leading
   articles ("the", "a", "der/die/das" if relevant), collapse whitespace.
2. Compare cinema-listing titles against watchlist titles using fuzzy string
   matching (e.g. `rapidfuzz.fuzz.token_sort_ratio`), threshold ~90.
3. Use `originalTitle` and `alternativeTitles` as additional candidates per
   film, since Letterboxd entries and Berlin OV listings may use different
   localized titles for the same film.
4. Use `year` as a tiebreaker/disambiguator when multiple fuzzy candidates
   are close (e.g. remakes, films with identical titles).
5. `imdbId` is present on the cinema side — if Letterboxd's feed or film
   pages ever expose an IMDb/TMDb id cheaply, prefer exact ID match over
   fuzzy title match. (Not required for v1; note as a quality upgrade.)

## 4. "Older than 6 months" filter

Two options, pick based on how strict you want v1 to be:

- **Simple (v1 default):** compute cutoff year/month from today; exclude any
  film whose `year` is the current year, *unless* we're more than 6 months
  into the year in which case same-year films older than ~6 months are still
  ambiguous. In practice: `year <= current_year - 1` is unambiguous-old;
  `year == current_year` is ambiguous without a real release date.
- **Accurate (v2 upgrade):** for films with `year == current_year` (the
  ambiguous band), do a one-off TMDb lookup by `imdbId` or title+year to get
  the actual release date, then filter precisely. Only needed for a handful
  of edge-case titles per run, so cheap even if added later.

Recommendation: ship v1 with the simple year-based rule, add the TMDb
disambiguation only if it turns out to matter in practice (i.e. you keep
seeing current-year films in the results that are actually >6 months old).

## 5. Architecture

```
cinema_oldmovies/
├── CONCEPT.md              (this file)
├── data/
│   └── movies_cache.json   (last fetched copy of movies.json, gitignored or kept as fallback)
├── backend/
│   ├── fetch_cinema.py     # download + cache movies.json
│   ├── fetch_watchlist.py  # scrape + paginate Letterboxd watchlist HTML pages
│   ├── match.py            # normalize + fuzzy match + filter
│   ├── app.py              # Flask/FastAPI app, one route, serves results
│   └── config.py           # LETTERBOXD_USERNAME, cache paths, thresholds
├── templates/
│   └── index.html          # single page: matched films, poster, cinema, showtime
└── requirements.txt
```

### Data flow (single run)

1. `fetch_cinema.py`: GET `movies.json` → if request fails, fall back to
   last cached copy in `data/movies_cache.json` (with a staleness warning) →
   otherwise overwrite cache.
2. `fetch_watchlist.py`: GET Letterboxd watchlist HTML pages for configured
   username, looping `page/1`, `page/2`, ... until a page comes back empty
   → parse `data-item-name="Title (Year)"` attributes into `[{title, year}]`.
3. `match.py`: apply age filter to cinema list → fuzzy match remaining
   titles against watchlist → produce `[{film, cinema, showtime(s), matched_watchlist_entry}]`.
4. `app.py`: serve this result set on `localhost`, rendered via one Jinja
   template. Optionally also show the full "old films playing, unmatched"
   list as a secondary section, since that's a nice byproduct almost for
   free.

No database. No auth. No deployment target. Re-run fetches happen either
on-demand (page refresh triggers re-fetch) or via a manual "refresh" script
— your call, doesn't need deciding until build time.

## 6. Build order (suggested milestones)

1. ~~**Spike / verify data**~~ — **done.** Both sources fetched and inspected
   for real; schema and access-method decisions above are based on this, not
   assumptions. (See §2.1 and §2.2.)
2. **Watchlist parser** — script that walks all paginated watchlist pages and
   prints your watchlist as a clean list of `{title, year}`. Standalone,
   testable in isolation. Should land on ~250-ish films across ~9 pages
   based on the spike.
3. **Cinema fetch + cache** — script that pulls `movies.json`, caches it,
   prints count of films + how many pass the "older than 6 months" filter.
4. **Matcher** — combine outputs of 2 & 3, print matches to terminal. This
   is the core value of the whole project — get this right before touching
   any UI.
5. **Minimal webapp** — wrap step 4's output in one Flask/FastAPI route +
   one HTML template. No styling effort beyond readable.
6. **Polish (optional, only if step 5 feels worth extending):** show
   posters, sort by showtime, link out to Letterboxd/cinema booking pages,
   add the "unmatched old films" bonus list, add a manual refresh button.

## 7. Risks / open questions

- **Third-party data dependency:** `movies.json` is maintained by someone
  else's hobby project. Mitigation: local cache with fallback (§5 step 1),
  and keep scraping critic.de/berlin.de directly in reserve as a v2 fallback
  if this source goes stale or disappears.
- **OV/OmU-only coverage:** if you find yourself missing German-dubbed
  rereleases or cinemas outside this source's coverage, that's the trigger
  to revisit direct scraping (was the original plan, still viable, just more
  work).
- **Letterboxd access method:** RSS is blocked by Cloudflare's bot challenge
  on your account (confirmed, HTTP 403 on `/rss/`); the plain HTML watchlist
  page works and is what the scraper targets instead. If Letterboxd ever
  extends the Cloudflare challenge to the plain HTML pages too, the scraper
  breaks and would need a headless-browser fallback (`playwright`) — worth
  keeping in mind but not a v1 concern.
- **Year-only age filtering:** approximate by design (§4); acceptable unless
  it produces visibly wrong results in practice.

## 8. Explicit non-goals for v1

- No user accounts, no multi-user support.
- No notifications/scheduling — you run it when you want to check.
- No deployment/hosting — runs on localhost only.
- No editing of watchlist or cinema data from the UI — read-only display.
