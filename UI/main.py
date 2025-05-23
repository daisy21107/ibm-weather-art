"""
AI Weather / News UI  ·  4-row layout
──────────────────────────────────────────────────────
Wide-Unicode font support:
    • We register a large-coverage TTF/OTF
      (Noto Sans CJK, DejaVu Sans, Microsoft YaHei, …)
      **using the name “Roboto”** – the same logical face every Kivy widget
      falls back to by default.  As a result, Chinese, Japanese, Arabic,
      Cyrillic… now render everywhere instead of little squares.
"""

# ───────── std-lib ─────────
import os, platform, threading, textwrap, webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path

# ───────── 3rd-party ───────
import requests, vlc, yt_dlp
from requests.exceptions import RequestException
from dotenv import load_dotenv

# ───────── Kivy setup ──────
from kivy.config import Config
Config.set("graphics", "width", "800")
Config.set("graphics", "height", "480")

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.animation import Animation
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy import resources

# ───────── load .env ───────
load_dotenv(Path(__file__).with_name(".env"))

# ───────── register fonts ─────────────────────────────────────────────
def _register_emoji_font() -> None:
    """Colour-emoji face used only for icons and buttons."""
    local = next((p for p in ("NotoColorEmoji.ttf", "seguiemj.ttf")
                  if Path(p).exists()), None)
    if not local:
        fallbacks = {
            "Windows": r"C:\Windows\Fonts\seguiemj.ttf",
            "Darwin":  "/System/Library/Fonts/Apple Color Emoji.ttc",
            "Linux":   "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        }
        local = fallbacks.get(platform.system(), "")
    if local and Path(local).exists():
        LabelBase.register(name="Emoji", fn_regular=str(Path(local)))

def _install_global_unicode_font() -> None:
    search = [
        "NotoSansKR-Regular.otf", "NotoSansCJK-Regular.ttc",
        "NanumGothic.ttf", "NanumGothic.otf",
        "NotoSansSC-Regular.otf", "NotoSans-Regular.ttf", "DejaVuSans.ttf",
        "msyh.ttc",
        # – Windows –
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\nanum.ttf", 
        # – macOS –
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        # – Linux common locations –
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in search:
        if Path(p).exists():
            LabelBase.register(name="Roboto", fn_regular=str(Path(p)))
            print(f"✓ Unicode font installed: {Path(p).name}")
            return
    print("⚠️  No wide-Unicode font found; non-Latin glyphs may show □")

# call once before any widgets are built
_register_emoji_font()
_install_global_unicode_font()
# ──────────────────────────────────────────────────────────────────────


# ───────── Guardian API ─────
class GuardianNewsAPI:
    BASE_URL = "https://content.guardianapis.com/search"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GUARDIAN_KEY")
        if not self.api_key:
            raise ValueError("Guardian API key not supplied")

    def fetch_news(self, amount=10):
        p = {"api-key": self.api_key,
             "show-fields": "trailText",
             "order-by": "newest",
             "page-size": max(1, min(amount, 200))}
        r = requests.get(self.BASE_URL, params=p, timeout=10).json()
        out = []
        for it in r["response"]["results"]:
            preview = textwrap.shorten(
                textwrap.dedent(it.get("fields", {}).get("trailText", ""))
                        .replace("\n", " "),
                width=140, placeholder="…")
            out.append({"title": it["webTitle"],
                        "url": it["webUrl"],
                        "preview": preview,
                        "date": datetime.fromisoformat(
                            it["webPublicationDate"].replace("Z", "+00:00")
                        ).strftime("%Y-%m-%d")})
        return out

# ───────── yt-dlp helper ─────
def resolve_stream_url(webpage_url: str) -> str:
    class QuietLogger:
        def debug(self, *_):   pass
        def warning(self, *_): pass
        def error(self, msg):  print(f"[yt-dlp] {msg}")
    opts = {"format": "bestaudio[ext=m4a]/bestaudio/best",
            "quiet": True, "no_warnings": True, "logger": QuietLogger()}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(webpage_url, download=False)["url"]

# ───────── VLC wrapper ──────
class MusicPlayer:
    def __init__(self):
        self.instance  = vlc.Instance()
        self.player    = self.instance.media_player_new()
        self.media     = None
        self.is_paused = False

    def load_and_play(self, stream_url: str):
        self.media = self.instance.media_new(
            stream_url,
            ":http-user-agent=Mozilla/5.0",
            ":http-referrer=https://www.youtube.com/")
        self.player.set_media(self.media)
        self.player.play()
        self.is_paused = False
        print("🎵 Playing")

    def toggle_pause(self):
        if self.player.is_playing() and not self.is_paused:
            self.player.pause(); self.is_paused = True;  print("⏸️ Paused")
        else:
            self.player.play();  self.is_paused = False; print("▶️ Resumed")

    def stop(self):
        self.player.stop(); self.is_paused = False; print("⏹️ Stopped")

    def seek(self, offset_sec: int):
        pos = self.player.get_time()
        if pos == -1:
            return
        new = max(0, pos + offset_sec * 1000)
        if self.player.get_length() > 0:
            new = min(new, self.player.get_length())
        self.player.set_time(int(new))

# ───────── UI root ──────────
class MainUI(BoxLayout):
    def show_error(self, msg):
        self.ids.news_label.text = f"[color=ff3333]{msg}[/color]"

# ───────── Main App ─────────
class AIWeatherApp(App):

    # build ---------------------------------------------------
    def build(self):
        self.music_player   = MusicPlayer()
        self._music_bar: ModalView | None = None
        self.news_api       = GuardianNewsAPI()

        self._news_buffer:  deque[dict] = deque()
        self._recent_urls:  deque[str]  = deque(maxlen=50)
        return MainUI()

    # life-cycle ---------------------------------------------
    def on_start(self):
        self.get_weather(); self.refresh_news()
        Clock.schedule_interval(self.refresh_news, 300)

    # WEATHER -------------------------------------------------
    def get_weather(self, *_):
        def task():
            k = os.getenv("OPENWEATHER_KEY")
            if not k:
                Clock.schedule_once(lambda *_:
                    self._update_weather("❌", "OPENWEATHER_KEY missing"))
                return
            try:
                r = requests.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params=dict(q="London", appid=k, units="metric", lang="en"),
                    timeout=8).json()
                desc, temp = r["weather"][0]["main"], r["main"]["temp"]
                emoji = {"Clear":"☀️","Clouds":"☁️","Rain":"🌧️","Snow":"❄️",
                         "Thunderstorm":"⚡","Drizzle":"🌦️","Mist":"🌫️",
                         "Haze":"🌫️","Fog":"🌁"}.get(desc,"🌈")
                icon, line = emoji, f"{desc}, {temp:.1f} °C"
            except Exception as e:
                print("Weather error:", e); icon, line = "❌", "API error"
            Clock.schedule_once(lambda *_: self._update_weather(icon, line))
        threading.Thread(target=task, daemon=True).start()

    def _update_weather(self, icon, line):
        self.root.ids.weather_icon.text  = icon
        self.root.ids.weather_label.text = line

    # NEWS ----------------------------------------------------
    def refresh_news(self, *_):
        if self._news_buffer:
            a = self._news_buffer.popleft(); self._recent_urls.append(a["url"])
            Clock.schedule_once(lambda *_: self._show_headline(a))
        else:
            threading.Thread(target=self._fill_buffer, daemon=True).start()

    def _fill_buffer(self):
        try:
            items  = self.news_api.fetch_news(50)
            fresh  = [a for a in items if a["url"] not in self._recent_urls]
            if not fresh: self._recent_urls.clear(); fresh = items
            self._news_buffer.extend(fresh)
        except Exception as e:
            Clock.schedule_once(
                lambda *_: self.root.show_error(f"Guardian API error: {e}"))
            return
        self.refresh_news()

    def _show_headline(self, art):
        lbl = self.root.ids.news_label; lbl.opacity = 0
        lbl.text = ("[ref={url}][b]{title}[/b]\n{preview}[/ref]\n"
                    "[size=24]via The Guardian · {date}[/size]").format(**art)
        Animation(opacity=1, duration=0.25).start(lbl)

    def open_article(self, url, *_): webbrowser.open(url)

    # MUSIC – threaded search --------------------------------
    def get_music(self, *_):
        q = self.root.ids.music_query.text.strip()
        if not q: return
        threading.Thread(target=self._search_and_show, args=(q,), daemon=True).start()

    def _search_and_show(self, query):
        results = self._search_youtube(query)
        Clock.schedule_once(lambda *_: self._open_search_popup(results))

    def _search_youtube(self, query, max_results=5):
        opts = {"quiet": True, "extract_flat": "in_playlist",
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "default_search": f"ytsearch{max_results}", "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            entries = (ydl.extract_info(query, download=False)
                       .get("entries", []) or [])
        return [(e.get("url") or e.get("webpage_url"), e.get("title","No title"))
                for e in entries if (e.get("url") or e.get("webpage_url"))]

    def _open_search_popup(self, results):
        if not results: return
        layout = GridLayout(cols=1, spacing=dp(5), padding=dp(10),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        scroll = ScrollView(); scroll.add_widget(layout)
        popup  = Popup(title="Select a track", content=scroll,
                       size_hint=(0.8, None), height=dp(300))
        for url, title in results:
            btn = Button(text=title, size_hint_y=None, height=dp(40),
                         on_release=lambda b,u=url,t=title: self._pick_track(u,t,popup))
            layout.add_widget(btn)
        popup.open()

    # MUSIC – threaded resolve & play ------------------------
    def _pick_track(self, url, title, popup):
        popup.dismiss()
        threading.Thread(target=self._resolve_and_play,
                         args=(url, title), daemon=True).start()

    def _resolve_and_play(self, url, title):
        try:  stream = resolve_stream_url(url)
        except Exception as e:
            print("Stream error:", e); return
        Clock.schedule_once(lambda *_: self._play_stream(stream, title))

    def _play_stream(self, stream, title):
        self.music_player.load_and_play(stream)
        self.root.ids.music_icon.text  = "🎵"
        self.root.ids.music_label.text = f"Now Playing: {title}"
        self._show_music_bar()

    # MUSIC – floating bar -----------------------------------
    def _show_music_bar(self):
        if self._music_bar: return
        bar = BoxLayout(orientation="horizontal", spacing=dp(8), padding=dp(10))
        make = lambda txt, cb: Button(text=txt, font_name="Emoji",
                                      font_size="24sp",
                                      size_hint=(None,None), size=(dp(60),dp(60)),
                                      background_normal="", background_color=(.3,.3,.3,.9),
                                      on_release=cb)
        bar.add_widget(make("⏮️", lambda *_: self.music_back()))
        self._btn_pause = make("⏸️", lambda *_: self.music_pause_resume()); bar.add_widget(self._btn_pause)
        bar.add_widget(make("⏭️", lambda *_: self.music_forward()))
        bar.add_widget(make("⏹️", lambda *_: self.music_stop()))

        mv = ModalView(size_hint=(None,None), size=(dp(340), dp(80)),
                       background_color=(0,0,0,0), auto_dismiss=False)
        mv.add_widget(bar)
        mv.open()
        mv.center_x, mv.y = self.root.center_x, dp(10)
        self._music_bar = mv

    def _close_music_bar(self):
        if self._music_bar: self._music_bar.dismiss(); self._music_bar = None

    # BUTTON callbacks ---------------------------------------
    def music_pause_resume(self):
        self.music_player.toggle_pause()
        if self._music_bar:
            self._btn_pause.text = "▶️" if self.music_player.is_paused else "⏸️"

    def music_forward(self):  self.music_player.seek(+10)
    def music_back(self):     self.music_player.seek(-10)
    def music_stop(self):
        self.music_player.stop(); self._close_music_bar()
        self.root.ids.music_icon.text  = ""
        self.root.ids.music_label.text = "Stopped."

    # CHATBOT -------------------------------------------------
    def ask_chatbot(self, *_):
        self.root.ids.chatbot_icon.text = "🤖"
        self.root.ids.chatbot_output.text = "Don’t forget your umbrella!"

# ───────── run ─────────
if __name__ == "__main__":
    AIWeatherApp().run()
