"""Quick smoke test for Lrclib API — no API key needed, no browser, no scraping."""

import requests

LRCLIB_BASE = "https://lrclib.net/api"


def get_lyrics(track_name: str, artist_name: str) -> str | None:
    """Fetch plain lyrics from Lrclib. Returns None if not found."""
    response = requests.get(
        f"{LRCLIB_BASE}/get",
        params={"track_name": track_name, "artist_name": artist_name},
        headers={"User-Agent": "Stalkify/1.0"},
        timeout=10,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data.get("plainLyrics")


if __name__ == "__main__":
    tests = [
        ("Galvanize", "The Chemical Brothers"),
        ("Bohemian Rhapsody", "Queen"),
        ("Numb", "Linkin Park"),
        ("nonexistent_track_xyz", "fake_artist_abc"),
    ]

    for track, artist in tests:
        print(f"\n{'='*50}")
        print(f"Track: {track} — Artist: {artist}")
        print("=" * 50)

        lyrics = get_lyrics(track, artist)

        if lyrics:
            preview = lyrics[:200] + "..." if len(lyrics) > 200 else lyrics
            print(f"OK — {len(lyrics)} chars")
            print(preview)
        else:
            print("NOT FOUND (None)")

    print(f"\n{'='*50}")
    print("Done.")
