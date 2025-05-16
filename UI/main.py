"""
AI Weather / News UI 
──────────────────────────────────────────────────────
• GUARDIAN_KEY       and  OPENWEATHER_KEY  come from the same .env file
• Four-row layout (Weather · News · Music · AI) defined in aiweather.kv
"""

# ───────── standard libs ─────────
import os
import platform
import threading
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
import textwrap

# ───────── third-party ───────────
import requests
from requests.exceptions import RequestException
from dotenv import load_dotenv

# ───────── Kivy setup ────────────
from kivy.config import Config
Config.set("graphics", "width", "800")
Config.set("graphics", "height", "480")

from kivy.core.text import LabelBase
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation

# ───────── load .env (both keys) ─────────
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# ───────── helper: register a colour-emoji font ─────────
def _register_emoji_font() -> None:
    for local in ("NotoColorEmoji.ttf", "seguiemj.ttf"):
        if Path(local).exists():
            LabelBase.register(name="Emoji", fn_regular=str(Path(local)))
            return
    fallbacks = {
        "Windows": r"C:\Windows\Fonts\seguiemj.ttf",
        "Darwin":  "/System/Library/Fonts/Apple Color Emoji.ttc",
        "Linux":   "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    }
    p = fallbacks.get(platform.system())
    if p and Path(p).exists():
        LabelBase.register(name="Emoji", fn_regular=p)

_register_emoji_font()

# ───────── Guardian API helper  ─────────
class GuardianNewsAPI:
    """Tiny wrapper around the Guardian Content API (search endpoint)."""

    BASE_URL = "https://content.guardianapis.com/search"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GUARDIAN_KEY")
        if not self.api_key:
            raise ValueError("Guardian API key not supplied (GUARDIAN_KEY)")

    def fetch_news(self, amount: int = 10) -> list[dict]:
        """Return a list of dicts: title · url · preview · date (YYYY-MM-DD)."""
        params = {
            "api-key":     self.api_key,
            "show-fields": "trailText",
            "order-by":    "newest",
            "page-size":   max(1, min(amount, 200)),  # Guardian cap is 200
        }
        r = requests.get(self.BASE_URL, params=params, timeout=10)
        r.raise_for_status()
        items = r.json()["response"]["results"]

        news = []
        for it in items:
            title = it["webTitle"]
            url   = it["webUrl"]
            raw_preview = it.get("fields", {}).get("trailText", "")
            preview = textwrap.shorten(
                textwrap.dedent(raw_preview).replace("\n", " "),
                width=140, placeholder="…"
            )
            pub_date = datetime.fromisoformat(
                it["webPublicationDate"].replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")
            news.append({"title": title,
                         "url": url,
                         "preview": preview,
                         "date": pub_date})
        return news

# ───────── UI root helper ─────────
class MainUI(BoxLayout):
    def show_error(self, msg: str) -> None:
        self.ids.news_label.text = f"[color=ff3333]{msg}[/color]"

# ───────── Main Application ───────
class AIWeatherApp(App):

    # build ---------------------------------------------------------------
    def build(self):
        try:
            self.news_api = GuardianNewsAPI()
        except ValueError as err:
            ui = MainUI()
            Clock.schedule_once(lambda *_: ui.show_error(str(err)))
            return ui

        # headline buffer & de-dupe store
        self._news_buffer: deque[dict] = deque()
        self._recent_urls: deque[str] = deque(maxlen=50)  # remember last 50
        return MainUI()

    # life-cycle ----------------------------------------------------------
    def on_start(self):
        self.get_weather()      # immediate weather
        self.refresh_news()     # immediate headline
        # auto headline every 5 min (manual button still works)
        Clock.schedule_interval(self.refresh_news, 300)

    # WEATHER -------------------------------------------------------------
    def get_weather(self, *_):
        def task():
            api_key = os.getenv("OPENWEATHER_KEY")
            if not api_key:
                Clock.schedule_once(
                    lambda *_: self._update_weather("❌", "OPENWEATHER_KEY missing"))
                return
            try:
                rsp = requests.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params=dict(q="London", appid=api_key,
                                units="metric", lang="en"),
                    timeout=8)
                rsp.raise_for_status()
                data = rsp.json()
                desc = data["weather"][0]["main"]
                temp = data["main"]["temp"]

                emoji = {
                    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️",
                    "Snow": "❄️",  "Thunderstorm": "⚡", "Drizzle": "🌦️",
                    "Mist": "🌫️", "Haze": "🌫️", "Fog": "🌁",
                }.get(desc, "🌈")

                icon, line = emoji, f"{desc}, {temp:.1f} °C"
            except Exception as exc:
                print(f"Weather API error: {exc}")
                icon, line = "❌", "API error"
            Clock.schedule_once(lambda *_: self._update_weather(icon, line))

        threading.Thread(target=task, daemon=True).start()

    def _update_weather(self, icon: str, line: str):
        self.root.ids.weather_icon.text  = icon
        self.root.ids.weather_label.text = line

    # NEWS  ---------------------------------------------------------------
    def refresh_news(self, *_):
        """Button & timer entry-point: pops the next unseen headline."""
        if self._news_buffer:
            art = self._news_buffer.popleft()
            self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))
        else:
            threading.Thread(target=self._fill_buffer, daemon=True).start()

    def _fill_buffer(self):
        try:
            items = self.news_api.fetch_news(amount=50)       # newest 50
            fresh = [a for a in items if a["url"] not in self._recent_urls]
            if not fresh:                  # if we’ve already shown them all
                self._recent_urls.clear()  # reset history once
                fresh = items
            self._news_buffer.extend(fresh)
        except (RequestException, ValueError) as err:
            Clock.schedule_once(lambda *_: self.root.show_error(f"Guardian API error: {err}"))
            return

        if self._news_buffer:
            art = self._news_buffer.popleft()
            self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))

    def _show_headline(self, art: dict):
        lbl = self.root.ids.news_label
        lbl.opacity = 0
        lbl.text = (
            f"[ref={art['url']}][b]{art['title']}[/b]\n"
            f"{art['preview']}[/ref]\n"
            f"[size=24]via The Guardian · {art['date']}[/size]"
        )
        Animation(opacity=1, duration=0.25).start(lbl)

    def open_article(self, url, *_):
        webbrowser.open(url)

    # MUSIC & AI ----------------------------------------------------------
    def get_music(self, *_):
        self.root.ids.music_icon.text  = "🎵"
        self.root.ids.music_label.text = "Jazz FM"

    def ask_chatbot(self, *_):
        self.root.ids.chatbot_icon.text   = "🤖"
        self.root.ids.chatbot_output.text = "Don’t forget your umbrella!"

# ───────── bootstrap ─────────
if __name__ == "__main__":
    AIWeatherApp().run()
