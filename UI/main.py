# AIWeather – UI (weather • Guardian news • BERT NLU • YouTube music)

import os
import webbrowser
import html
import re
import csv
import json
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import requests
from requests.exceptions import RequestException
import yt_dlp

try:
    import vlc
except ModuleNotFoundError:
    vlc = None

from kivy.config import Config
Config.set("graphics", "width",  "800")
Config.set("graphics", "height", "480")
Config.set('graphics', 'show_cursor', '0')


from kivy.resources import resource_add_path
from kivy.core.text import LabelBase
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.animation import Animation

from BERT import infer as nlu_infer

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

# Thread pool
EXECUTOR = ThreadPoolExecutor(max_workers=4)

# Logging setup
log_dir = Path.home() / "aiweather"
log_dir.mkdir(exist_ok=True)
logger = logging.getLogger("nlu")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("[%(asctime)s] %(message)s")
sh = logging.StreamHandler()
sh.setFormatter(fmt)
logger.addHandler(sh)
fh = RotatingFileHandler(log_dir / "nlu.log", maxBytes=300_000,
                         backupCount=5, encoding="utf-8")
fh.setFormatter(fmt)
logger.addHandler(fh)

csv_path = log_dir / "nlu_log.csv"
if not csv_path.exists():
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp", "raw_text", "intent", "slots_json"])

# yt_dlp logger
ydl_logger = logging.getLogger("yt_dlp")
ydl_handler = logging.StreamHandler()
ydl_formatter = logging.Formatter("[yt_dlp] %(message)s")
ydl_handler.setFormatter(ydl_formatter)
ydl_logger.addHandler(ydl_handler)
ydl_logger.setLevel(logging.WARNING)

def _append_csv(ts, raw, intent, slots):
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts, raw, intent,
                                json.dumps(slots, ensure_ascii=False)])

# Register fonts
def _register_emoji_font() -> None:
    fonts_dir = Path(__file__).with_name("fonts")
    noto_sym = fonts_dir / "NotoSansSymbols2-Regular.ttf"
    if noto_sym.exists():
        LabelBase.register(name="Emoji", fn_regular=str(noto_sym))
        print(f"✅ Emoji glyphs → {noto_sym.name}")
    else:
        print("⚠️  NotoSansSymbols2-Regular.ttf missing – basic icons blank")

    fa_solid = fonts_dir / "fa-solid-900.ttf"
    if fa_solid.exists():
        LabelBase.register(name="FA", fn_regular=str(fa_solid))
        print(f"✅ FA icons      → {fa_solid.name}")
    else:
        print("⚠️  fa-solid-900.ttf missing – 🎵 🤖 🔍 icons blank")

def _install_global_unicode_font() -> None:
    search = [
        "NotoSansCJK-Regular.ttc", "NotoSansKR-Regular.otf",
        "NanumGothic.ttf", "NanumGothic.otf", "NotoSansSC-Regular.otf",
        "NotoSans-Regular.ttf", "DejaVuSans.ttf", "msyh.ttc",
        r"C:\Windows\Fonts\malgun.ttf",  r"C:\Windows\Fonts\nanum.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in search:
        if Path(p).exists():
            resource_add_path(str(Path(p).parent))
            LabelBase.register(name="Roboto", fn_regular=str(Path(p)))
            LabelBase.register(name="UI",     fn_regular=str(Path(p)))
            print(f"✓ Unicode font installed: {Path(p).name}")
            return
    print("⚠️  No wide-Unicode font found; non-Latin glyphs may show □")

_register_emoji_font()
_install_global_unicode_font()

class ReminderManager:
    def __init__(self):
        self.reminder_list = self._create_reminder_list()

    def _create_reminder_list(self):
        reminder_list = {}
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            reminder_list[day] = {
                "Morning": [None, None, None],
                "Afternoon": [None, None, None],
                "Evening": [None, None, None]
            }
        return reminder_list

    def add_one_time(self, day, time, reminder):
        for i in range(3):
            if self.reminder_list[day][time][i] is None:
                self.reminder_list[day][time][i] = reminder
                break

    def add_everyday(self, time, reminder):
        for day in self.reminder_list:
            for i in range(3):
                if self.reminder_list[day][time][i] is None:
                    self.reminder_list[day][time][i] = reminder
                    break

    def delete(self, day, time, reminder):
        try:
            index = self.reminder_list[day][time].index(reminder)
            self.reminder_list[day][time][index] = None
            self.reminder_list[day][time] = (
                [x for x in self.reminder_list[day][time] if x is not None]
                + [None] * (3 - len(self.reminder_list[day][time]))
            )
        except ValueError:
            pass

    def get_all(self):
        return self.reminder_list

class GuardianNewsAPI:
    BASE_URL = "https://content.guardianapis.com/search"
    def __init__(self, key=None):
        self.key = key or os.getenv("GUARDIAN_KEY")
        if not self.key:
            raise ValueError("GUARDIAN_KEY missing")

    @staticmethod
    def _clean(raw):
        return html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()

    def fetch_news(self, *, amount=10, keyword=None):
        p = {
            "api-key": self.key,
            "show-fields": "trailText",
            "order-by": "newest",
            "page-size": min(max(amount, 1), 200)
        }
        if keyword:
            p["q"] = keyword
        r = requests.get(self.BASE_URL, params=p, timeout=10)
        r.raise_for_status()
        news = []
        for it in r.json()["response"]["results"]:
            raw_html = it.get("fields", {}).get("trailText", "")
            preview_full = self._clean(raw_html)
            # Truncate to 400 characters as before
            if len(preview_full) > 400:
                preview_full = preview_full[:400].rstrip() + "…"
            news.append({
                "title": it["webTitle"],
                "url": it["webUrl"],
                "preview": preview_full,
                "date": datetime.fromisoformat(
                    it["webPublicationDate"].replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
            })
        return news

class MainUI(BoxLayout):
    def show_error(self, msg):
        # On error, clear title/footer and place msg into preview (in red)
        self.ids.news_title.text = ""
        self.ids.news_preview.text = f"[color=ff3333]{msg}[/color]"
        self.ids.news_footer.text = ""

class AIWeatherApp(App):
    def build(self):
        self.reminder_manager = ReminderManager()
        self.news_api      = GuardianNewsAPI()
        self.current_city  = "London"
        self._news_keyword = None
        self._news_buffer  = deque()
        self._recent_urls  = deque(maxlen=50)
        self._init_player()
        return MainUI()

    def on_start(self):
        self.get_weather()
        self.refresh_news()
        self.update_today_reminder_summary()
        Clock.schedule_interval(self.get_weather, 600)
        Clock.schedule_interval(self.refresh_news, 300)

    # ─── Weather ───────────────────────────────────────────────────────────────
    def get_weather(self, city=None, *_):
        city = city or self.current_city or "London"
        def task():
            key = os.getenv("OPENWEATHER_KEY")
            if not key:
                Clock.schedule_once(lambda *_:
                    self._upd_weather("❌", "OPENWEATHER_KEY missing")
                )
                return
            try:
                r = requests.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params=dict(q=city, appid=key, units="metric", lang="en"),
                    timeout=8
                )
                r.raise_for_status()
                d = r.json()
                desc  = d["weather"][0]["main"]
                temp  = d["main"]["temp"]
                emoji = {
                    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Snow": "❄️",
                    "Thunderstorm": "⚡", "Drizzle": "🌦️",
                    "Mist": "🌫️", "Haze": "🌫️", "Fog": "🌁"
                }.get(desc, "🌈")
                Clock.schedule_once(lambda *_:
                    self._upd_weather(emoji, f"{city}: {desc}, {temp:.1f} °C")
                )
            except Exception:
                Clock.schedule_once(lambda *_:
                    self._upd_weather("❌", "API error")
                )
        EXECUTOR.submit(task)

    def _upd_weather(self, icon, line):
        self.root.ids.weather_icon.text = icon
        self.root.ids.weather_label.text = line

    # ─── News ──────────────────────────────────────────────────────────────────
    def refresh_news(self, *_):
        if self._news_buffer:
            art = self._news_buffer.popleft()
            self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))
        else:
            EXECUTOR.submit(self._fill_buffer)

    def _fill_buffer(self):
        try:
            items = self.news_api.fetch_news(amount=50, keyword=self._news_keyword)
            fresh = [a for a in items if a["url"] not in self._recent_urls]
            if not fresh:
                self._recent_urls.clear()
                fresh = items
            self._news_buffer.extend(fresh)
        except (RequestException, ValueError) as e:
            Clock.schedule_once(lambda *_:
                self.root.show_error(f"Guardian API error: {e}")
            )
            return
        if self._news_buffer:
            art = self._news_buffer.popleft()
            self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))

    def _show_headline(self, art):
        """
        Split the “preview” text into sentences and take at most the first 5.
        Then assign raw strings to news_title, news_preview, news_footer.
        All font sizes and bolding live in KV, not here.
        """
        def first_n_sentences(text, n=5):
            # A very simple sentence‐splitter by punctuation.
            parts = re.split(r'(?<=[.!?])\s+', text)
            if len(parts) <= n:
                return text
            return " ".join(parts[:n]).rstrip(" .!?,;:") + "…"

        lbl_title   = self.root.ids.news_title
        lbl_preview = self.root.ids.news_preview
        lbl_footer  = self.root.ids.news_footer

        lbl_title.opacity   = 0
        lbl_preview.opacity = 0
        lbl_footer.opacity  = 0

        # Title is raw
        lbl_title.text = art["title"]

        # Preview: only first 5 sentences
        preview_text = first_n_sentences(art["preview"], n=5)
        lbl_preview.text = preview_text

        # Footer as before
        lbl_footer.text = f"via The Guardian · {art['date']}"

        Animation(opacity=1, d=0.25).start(lbl_title)
        Animation(opacity=1, d=0.25).start(lbl_preview)
        Animation(opacity=1, d=0.25).start(lbl_footer)

    def open_article(self, instance, url):
        webbrowser.open(url)

    # ─── NLU routing ────────────────────────────────────────────────────────────
    def process_request(self, *_):
        t = self.root.ids.request_input.text.strip()
        if not t:
            return
        EXECUTOR.submit(nlu_infer, t)\
                .add_done_callback(partial(self._route_from_nlu, raw=t))

    def _route_from_nlu(self, fut, raw):
        ts = datetime.utcnow().isoformat(timespec="seconds")
        try:
            intent, slots = fut.result()
        except Exception:
            Clock.schedule_once(lambda *_: self.root.show_error("NLU error"))
            return

        buckets = defaultdict(list)
        for w, t in slots:
            if t and t != "O":
                buckets[t.split("-")[-1].lower()].append(w)
        slot_json = {k: " ".join(v) for k, v in buckets.items()}
        logger.info('INTENT=%s  SLOTS=%s  RAW="%s"', intent, slot_json, raw)
        _append_csv(ts, raw, intent, slot_json)
        Clock.schedule_once(lambda *_: self._apply_nlu_result(intent, buckets))

    def _apply_nlu_result(self, intent, buckets):
        loc   = " ".join(buckets.get("location", [])).title()
        topic = " ".join(buckets.get("topic", []))
        words = " ".join(sum(buckets.values(), []))
        if intent == "get_weather":
            if loc:
                self.current_city = loc
            self.get_weather()
        elif intent == "get_news":
            self._news_keyword = topic or words or None
            self._news_buffer.clear()
            self.refresh_news()
        elif intent == "play_music":
            query = (topic or words).strip()
            self.get_music(query=query or None)
        else:
            self.root.ids.request_input.hint_text = (
                "Try “weather in Berlin” or “news about rugby”."
            )
            return
        self.root.ids.request_input.text = ""
        self.root.ids.request_input.focus = False

    # ─── YouTube music ─────────────────────────────────────────────────────────
    def _init_player(self):
        if vlc is None:
            self._vlc = self.player = None
            return
        self._vlc   = vlc.Instance("--no-xlib", "--quiet", "--novideo")
        self.player = self._vlc.media_player_new()

    def get_music(self, query=None, *_):
        if not query:
            self._music_error("No music keywords found")
            return
        ids = self.root.ids
        ids.music_icon.text  = "🔍"
        ids.music_label.text = f"Searching “{query}”…"
        EXECUTOR.submit(self._yt_search, query).add_done_callback(self._after_search)

    @staticmethod
    def _yt_search(query, max_results=5):
        opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "default_search": f"ytsearch{max_results}",
            "noplaylist": True,
            "logger": ydl_logger,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            entries = (ydl.extract_info(query, download=False)
                       .get("entries", []) or [])
        out = []
        for e in entries:
            url = e.get("url") or e.get("webpage_url")
            if url:
                out.append({
                    "url": url,
                    "title": e.get("title", "No title"),
                    "uploader": e.get("uploader") or "YouTube"
                })
        return out

    @staticmethod
    def _yt_fetch_url(video_url):
        opts = {
            "quiet": True,
            "skip_download": True,
            "forceurl": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "logger": ydl_logger,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(video_url, download=False)["url"]

    def _music_error(self, msg):
        Clock.schedule_once(lambda *_: (
            setattr(self.root.ids.music_icon,  "text", "❌"),
            setattr(self.root.ids.music_label, "text", msg)
        ))

    def _after_search(self, fut):
        try:
            results = fut.result()
        except Exception as e:
            self._music_error(str(e))
            return
        if not results:
            self._music_error("No results")
            return
        Clock.schedule_once(lambda *_: self._show_results(results))

    def _show_results(self, results):
        ROW_H = dp(40)
        inner = GridLayout(
            cols=1, spacing=dp(5),
            padding=[dp(8), dp(8), dp(8), dp(8)],
            size_hint_y=None
        )
        inner.bind(minimum_height=inner.setter("height"))

        # ↓ Make each track‐button slightly smaller (18sp)
        for r in results:
            btn = Button(
                text=r["title"],
                size_hint_y=None,
                height=ROW_H,
                font_size="18sp",   # was "20sp"
                halign="center",
                valign="middle"
            )
            btn.bind(
                size=lambda b, *_: setattr(b, "text_size", (b.width - dp(20), None))
            )
            btn.bind(on_release=lambda b, res=r: (
                popup.dismiss(),
                EXECUTOR.submit(self._prepare_and_play, res)
            ))
            inner.add_widget(btn)

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(inner)
        popup = Popup(
            title="Select a track",
            content=scroll,
            size_hint=(0.8, None),
            height=dp(300),
            auto_dismiss=True
        )
        popup.open()

    def _prepare_and_play(self, res):
        try:
            stream = self._yt_fetch_url(res["url"])
            Clock.schedule_once(lambda *_: self._play(stream, res["title"]))
        except Exception as e:
            self._music_error(str(e))

    def _play(self, stream_url, title):
        if self.player is None:
            self._music_error("python-vlc not installed")
            return
        media = self._vlc.media_new(stream_url)
        self.player.set_media(media)
        self.player.play()
        ids = self.root.ids
        ids.music_icon.text  = "🎵"
        ids.music_label.text = title
        ids.btn_play.text    = "⏸️"

    def music_play_pause(self, *_):
        if not self.player:
            return
        if self.player.is_playing():
            self.player.pause()
            self.root.ids.btn_play.text = "▶️"
        else:
            self.player.play()
            self.root.ids.btn_play.text = "⏸️"

    def music_stop(self, *_):
        if self.player:
            self.player.stop()
        ids = self.root.ids
        ids.music_icon.text  = "🎵"
        ids.music_label.text = "Stopped"
        ids.btn_play.text    = "▶️"

    def _seek(self, sec):
        if not self.player:
            return
        pos = self.player.get_time() / 1000
        self.player.set_time(int(max(pos + sec, 0) * 1000))

    def music_back(self, *_):
        self._seek(-10)

    def music_forward(self, *_):
        self._seek(+10)

    # ─── Reminders ─────────────────────────────────────────────────────────────
    def open_reminder_popup(self):
        popup = Popup(title="Weekly Reminders", size_hint=(0.95, 0.95))
        scroll = ScrollView()
        grid = GridLayout(cols=8, spacing=dp(5), padding=dp(10),
                          size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        grid.add_widget(Label(text="", bold=True, font_size="18sp"))  # was 20sp
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            grid.add_widget(Label(
                text=f"[b]{day}[/b]",
                markup=True,
                font_name="UI",
                font_size="18sp",  # was 20sp
                size_hint_y=None,
                height=dp(30)
            ))

        times = ["Morning", "Afternoon", "Evening"]
        data = self.reminder_manager.get_all()
        for time in times:
            grid.add_widget(Label(
                text=f"[b]{time}[/b]",
                markup=True,
                font_name="UI",
                font_size="18sp",  # was 20sp
                size_hint_y=None,
                height=dp(60)
            ))
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                reminders = data[day][time]
                msg = "\n".join(r for r in reminders if r) or "—"
                grid.add_widget(Label(
                    text=msg,
                    font_name="UI",
                    font_size="18sp",  # was 20sp
                    halign="left",
                    valign="top",
                    size_hint_y=None,
                    height=dp(60),
                    text_size=(dp(100), None)
                ))

        scroll.add_widget(grid)
        popup.content = scroll
        popup.open()

    def open_add_reminder_popup(self):
        popup = Popup(title="Add Reminder", size_hint=(0.8, 0.6))
        layout = GridLayout(
            cols=2, spacing=dp(10), padding=dp(20),
            row_default_height=dp(40), size_hint_y=None
        )
        layout.bind(minimum_height=layout.setter("height"))

        layout.add_widget(Label(text="Day:", font_name="UI", font_size="18sp"))  # was 20sp
        day_spinner = Spinner(
            text="Monday",
            values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            font_size="18sp"  # was 20sp
        )
        layout.add_widget(day_spinner)

        layout.add_widget(Label(text="Time:", font_name="UI", font_size="18sp"))  # was 20sp
        time_spinner = Spinner(
            text="Morning",
            values=["Morning", "Afternoon", "Evening"],
            font_size="18sp"  # was 20sp
        )
        layout.add_widget(time_spinner)

        layout.add_widget(Label(text="Reminder:", font_name="UI", font_size="18sp"))  # was 20sp
        reminder_input = TextInput(multiline=False, font_name="UI", font_size="18sp")  # was 20sp
        layout.add_widget(reminder_input)

        def submit_reminder(*_):
            day  = day_spinner.text
            time = time_spinner.text
            text = reminder_input.text.strip()
            if text:
                self.reminder_manager.add_one_time(day, time, text)
                popup.dismiss()
            self.update_today_reminder_summary()

        layout.add_widget(Widget())
        layout.add_widget(Button(text="Add", font_size="18sp", on_release=submit_reminder))  # was 20sp

        scroll = ScrollView()
        scroll.add_widget(layout)
        popup.content = scroll
        popup.open()

    def update_today_reminder_summary(self):
        today = datetime.now().strftime("%A")
        reminders = self.reminder_manager.get_all().get(today, {})
        summary_lines = []
        for time in ["Morning", "Afternoon", "Evening"]:
            entries = [r for r in reminders.get(time, []) if r]
            if entries:
                summary_lines.append(f"{time}: {', '.join(entries)}")
        summary = "\n".join(summary_lines) if summary_lines else "No reminders today"
        self.root.ids.reminder_summary.text = summary

if __name__ == "__main__":
    AIWeatherApp().run()
