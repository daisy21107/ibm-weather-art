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
import vlc
import yt_dlp
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
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from kivy.uix.button import Button


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
    
# ----------- Stream Resolver -----------

def format_duration(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{int(minutes)}:{int(secs):02d}"

def resolve_stream_url(webpage_url):
    ydl_opts = {
        'quiet': True,
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(webpage_url, download=False)
        return info['url']
    
class MusicPlayer:
    def __init__(self):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.media = None
        self.progress_thread = None
        self._stop_progress = False
        self.is_paused = False

    def load_and_play(self, stream_url):
        self.media = self.instance.media_new(
            stream_url,
            ":http-user-agent=Mozilla/5.0",
            ":http-referrer=https://www.youtube.com/"
        )
        self.player.set_media(self.media)
        self.player.play()
        print("🎵 Media loaded.")
        
    def toggle_pause(self):
        if self.player.is_playing():
            self.player.pause()
            self.is_paused = True
            print("⏸️ Paused.")
        elif self.is_paused:
            self.player.play()
            self.is_paused = False
            print("▶️ Resumed.")
            
    def stop(self):
        self.player.stop()
        self._stop_progress = True
        print("⏹️ Stopped.")

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

    # MUSIC ----------------------------------------------------------
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.music_player = MusicPlayer()
    
    def search_youtube(self, query, max_results=5):
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'default_search': f'ytsearch{max_results}',
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
        entries = info.get('entries', []) or []

        results = []
        for entry in entries:
            # some entries use 'url', others 'webpage_url'
            url   = entry.get('url') or entry.get('webpage_url')
            title = entry.get('title', 'Unknown')
            if url:
                results.append((url, title))
        return results

    def _update_music_label(self, icon: str, title: str):
        self.root.ids.music_icon.text = icon
        self.root.ids.music_label.text = f"Now Playing: {title}"

    def get_music(self, *args):
        query = self.root.ids.music_query.text.strip()
        if not query:
            return

        results = self.search_youtube(query)
        if not results:
            # Optionally: show a toast or popup “No results found”
            return

        # 1) make a vertical GridLayout to hold Buttons
        layout = GridLayout(cols=1,
                            spacing=dp(5),
                            padding=dp(10),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # 2) wrap it in a ScrollView
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(layout)

        # 3) create the Popup
        popup = Popup(title="Select a track",
                      content=scroll,
                      size_hint=(0.8, None),
                      height=dp(300))

        # 4) for each result, add a Button that captures url & title
        for url, title in results:
            btn = Button(text=title,
                         size_hint_y=None,
                         height=dp(40))
            # capture url/title/popup into the handler
            btn.bind(on_release=lambda inst, u=url, t=title: self._on_pick(u, t, popup))
            layout.add_widget(btn)

        popup.open()


    def _on_pick(self, url, title, popup):
        popup.dismiss()
        try:
            stream = resolve_stream_url(url)
        except Exception as e:
            print(f"Stream error: {e}")
            return
        self.music_player.load_and_play(stream)
        Clock.schedule_once(lambda dt: self._update_music_label("🎵", title))

    # CHATBOT ----------------------------------------------------------
    def ask_chatbot(self, *_):
        self.root.ids.chatbot_icon.text   = "🤖"
        self.root.ids.chatbot_output.text = "Don’t forget your umbrella!"

# ───────── bootstrap ─────────
if __name__ == "__main__":
    AIWeatherApp().run()
