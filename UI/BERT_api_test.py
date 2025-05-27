"""
This is a test script for the Joint-BERT APIs.
It uses the BERT model to infer the intent and slots from user input.
Run this file along with .env for testing.
"""

# ───────── std-lib ─────────
import os, sys, html, re, textwrap
from pathlib import Path
from datetime import datetime

# ───────── 3rd-party ───────
import requests
from dotenv import load_dotenv
from BERT import infer                    # Joint-BERT

# optional music helpers (unchanged)
from src.youtube import (search_youtube,
                         resolve_stream_url,
                         MusicPlayer,
                         get_single_key)

# ──────── env / keys ───────
load_dotenv()                        # expects .env in the same folder / project root
G_KEY = os.getenv("GUARDIAN_KEY")    # Guardian API
W_KEY = os.getenv("OPENWEATHER_KEY") # OpenWeather API
if not (G_KEY and W_KEY):
    sys.exit("❌  GUARDIAN_KEY or OPENWEATHER_KEY missing in .env")

# ──────── Guardian helper (copied from main.py) ────────
def _clean_html(txt: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", txt)).strip()

def fetch_news(topic: str, n: int = 5):
    params = {"api-key": G_KEY,
              "show-fields": "trailText",
              "order-by": "newest",
              "page-size": n,
              "q": topic}
    url = "https://content.guardianapis.com/search"
    items = requests.get(url, params=params, timeout=10)\
                    .json()["response"]["results"]
    for it in items:
        prev = textwrap.shorten(_clean_html(it["fields"]["trailText"]), 120, "…")
        date = datetime.fromisoformat(
            it["webPublicationDate"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
        print(f"• {it['webTitle']} ({date})\n  {prev}\n  {it['webUrl']}\n")

# ──────── weather helper (same logic as main.py) ────────
def fetch_weather(city: str):
    params = dict(q=city, appid=W_KEY, units="metric", lang="en")
    url = "https://api.openweathermap.org/data/2.5/weather"
    try:
        d = requests.get(url, params=params, timeout=8).json()
        desc, temp = d["weather"][0]["main"], d["main"]["temp"]
        emoji = {"Clear":"☀️","Clouds":"☁️","Rain":"🌧️","Snow":"❄️",
                 "Thunderstorm":"⚡","Drizzle":"🌦️","Mist":"🌫️",
                 "Haze":"🌫️","Fog":"🌁"}.get(desc, "🌈")
        print(f"{emoji}  {city.title()}: {desc}, {temp:.1f} °C\n")
    except Exception as e:
        print("❌ Weather API error:", e)

# ───────── main loop ─────────
if __name__ == "__main__":
    print("🤖  Joint-BERT CLI.  Ctrl-C to quit.")
    while True:
        try:
            text = input("\n🗣  Say something: ").strip()
            if not text:
                continue

            intent, slots = infer(text)
            print(f"→ intent: {intent}\n→ slots : {slots}")

            # gather all labelled words
            bucket = {}
            for w, t in slots:
                if t != "O":
                    bucket.setdefault(t.split("-")[-1].lower(), []).append(w)
            keyword = " ".join(sum(bucket.values(), []))

            if intent == "get_news":
                if bucket.get("topic"):
                    fetch_news(" ".join(bucket["topic"]))
                else:
                    print("⚠️  No topic detected for news.")
            elif intent == "get_weather":
                city = " ".join(bucket.get("location", [])) or "London"
                fetch_weather(city)
            elif intent == "play_music":
                if keyword:
                    print(f"🎵  Searching YouTube for “{keyword}” …")
                    url, title = search_youtube(keyword)
                    if not url:
                        print("❌  No video found."); continue
                    stream = resolve_stream_url(url)
                    player = MusicPlayer(); player.open(stream); player.play()
                    print("🎛️  Controls: space=Pause  ←/→=Seek  Enter=Quit")
                    while player.play():
                        k = get_single_key()
                        if k == "space": player.pause_resume()
                        elif k == "left": player.seek_backward()
                        elif k == "right": player.seek_forward()
                        elif k == "enter": player.stop(); break
                else:
                    print("⚠️  No song/artist detected.")
            else:
                print("✅  Intent not mapped to an API.")

        except KeyboardInterrupt:
            print("\n👋  Bye!"); break
