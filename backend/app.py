"""Minimal local webapp: fetch, match, display. Run with `python3 app.py`
and open http://127.0.0.1:5000
"""

from datetime import date

from flask import Flask, render_template

from fetch_cinema import fetch_movies
from fetch_watchlist import fetch_watchlist
from match import filter_old_films, find_matches

app = Flask(__name__, template_folder="../templates")


def _showings_summary(cinema_movie):
    """Flatten the nested showings dict into a simple sorted list of
    {date, time, cinema} for display."""
    rows = []
    for showing_date, times in (cinema_movie.get("showings") or {}).items():
        for time_str, entries in times.items():
            for entry in entries:
                rows.append({
                    "date": showing_date,
                    "time": time_str,
                    "cinema": entry.get("cinema"),
                })
    rows.sort(key=lambda r: (r["date"], r["time"]))
    return rows


@app.route("/")
def index():
    movies = fetch_movies()
    old_movies = filter_old_films(movies)
    watchlist = fetch_watchlist()
    matches = find_matches(old_movies, watchlist)

    results = []
    for m in matches:
        cm = m["cinema_movie"]
        results.append({
            "title": cm["title"],
            "year": cm["year"],
            "poster_url": cm.get("posterUrl"),
            "info_url": cm.get("url"),
            "watchlist_title": m["watchlist_film"]["title"],
            "watchlist_url": m["watchlist_film"].get("url"),
            "showings": _showings_summary(cm),
        })

    return render_template(
        "index.html",
        results=results,
        total_showing=len(movies),
        total_old=len(old_movies),
        total_watchlist=len(watchlist),
        today=date.today().isoformat(),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
