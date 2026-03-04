"""
End-to-end test for Lrclib lyrics + Groq analysis.
Usage: python -m scripts.test_analysis
"""

from src.lyrics import get_lyrics
from src.groq_client import analyze_track

track_name = "Galvanize"
artist_name = "The Chemical Brothers"

print(f"Fetching lyrics for '{track_name}' by '{artist_name}'...")
lyrics = get_lyrics(track_name, artist_name)

if lyrics:
    print(f"Lyrics found ({len(lyrics)} chars).\n")
else:
    print("No lyrics found, proceeding without.\n")

print("Generating analysis...\n")
analysis = analyze_track(track_name, artist_name, lyrics)

if analysis:
    print("=== Analysis ===")
    print(analysis)
else:
    print("Analysis failed.")
